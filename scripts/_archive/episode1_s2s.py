#!/usr/bin/env python3
"""
Episode 1: Speech-to-Speech Voice Conversion

Converts user recordings to character voices using Chatterbox S2S on fal.ai.

Workflow:
    1. Record all lines into output/episode1/recordings/ (one file per scene)
    2. Run this script to convert them to character voices
    3. Run episode1_produce.py video + concat to regenerate the video

Usage:
    python scripts/episode1_s2s.py list         # Show all lines to record
    python scripts/episode1_s2s.py convert      # Convert all recordings
    python scripts/episode1_s2s.py convert 12   # Convert specific scene only
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

# Import scene definitions from the production script
from scripts.episode1_produce import SCENES, _scene_id, get_audio_path, OUTPUT_DIR

# ============================================================================
# CONFIGURATION
# ============================================================================

RECORDINGS_DIR = OUTPUT_DIR / "recordings"

# Best reference clips per character (from voice cloning source audio)
VOICE_REFS = {
    "bibi": Path("output/voice_cloning/bibi/clip2.mp3"),
    "kisch": Path("output/voice_cloning/kisch/clip2.mp3"),
    "silman": Path("output/voice_cloning/silman/clip2.mp3"),
}

# ============================================================================
# LIST LINES TO RECORD
# ============================================================================

def list_lines():
    """Print all speaking lines for recording."""
    print("\n" + "=" * 70)
    print("Episode 1 — Lines to Record")
    print("=" * 70)
    print(f"\nSave recordings to: {RECORDINGS_DIR}/")
    print("Filename format: scene_XX_CHARACTER.mp3 (or .m4a, .wav)\n")

    speaking = [s for s in SCENES if s["type"] == "speak"]
    for scene in speaking:
        sid = _scene_id(scene)
        char = scene["char"]
        text = scene["text"]
        rec_path = RECORDINGS_DIR / f"scene_{sid}_{char}.*"

        # Check if recording exists
        existing = list(RECORDINGS_DIR.glob(f"scene_{sid}_{char}.*")) if RECORDINGS_DIR.exists() else []
        status = "RECORDED" if existing else "NEED"

        print(f"  [{status:8s}] Scene {sid:>4s} ({char:6s}): {text[:80]}{'...' if len(text) > 80 else ''}")

    print(f"\n  {len(speaking)} lines total")
    print(f"\nTip: Record with correct pronunciation and emotion.")
    print(f"     The voice conversion will change the voice but keep your delivery.\n")


# ============================================================================
# CONVERT RECORDINGS
# ============================================================================

async def convert_recordings(scene_filter=None):
    """Convert user recordings to character voices using Chatterbox S2S."""
    import fal_client
    import httpx

    print("\n" + "=" * 70)
    print("Episode 1 — Speech-to-Speech Voice Conversion (Chatterbox)")
    print("=" * 70)

    api_key = os.getenv("FAL_KEY") or os.getenv("FAL_API_KEY")
    os.environ["FAL_KEY"] = api_key
    fal_client.api_key = api_key

    if not RECORDINGS_DIR.exists():
        print(f"\n  ERROR: No recordings directory found at {RECORDINGS_DIR}")
        print(f"  Create it and add your recordings first.")
        print(f"  Run: python scripts/episode1_s2s.py list")
        return

    # Upload reference voices once
    print("\n  Uploading character reference voices...")
    ref_urls = {}
    for char, ref_path in VOICE_REFS.items():
        if not ref_path.exists():
            print(f"  WARNING: Reference missing for {char}: {ref_path}")
            continue
        ref_bytes = ref_path.read_bytes()
        ref_urls[char] = await fal_client.upload_async(ref_bytes, content_type="audio/mpeg")
        print(f"    {char}: uploaded ({len(ref_bytes):,} bytes)")

    speaking = [s for s in SCENES if s["type"] == "speak"]
    converted = 0
    skipped = 0

    for scene in speaking:
        sid = _scene_id(scene)
        char = scene["char"]

        # Filter to specific scene if requested
        if scene_filter and sid != scene_filter:
            continue

        # Find recording file (any audio format)
        recordings = list(RECORDINGS_DIR.glob(f"scene_{sid}_{char}.*"))
        if not recordings:
            print(f"  Scene {sid:>4s} ({char:6s}): no recording found, skipping")
            skipped += 1
            continue

        recording_path = recordings[0]
        audio_path = get_audio_path(scene)

        # Skip if converted audio already exists (delete to reconvert)
        if audio_path.exists() and not scene_filter:
            print(f"  Scene {sid:>4s} ({char:6s}): audio exists, skipping (delete to reconvert)")
            skipped += 1
            continue

        if char not in ref_urls:
            print(f"  Scene {sid:>4s} ({char:6s}): no reference voice, skipping")
            skipped += 1
            continue

        # Upload recording
        print(f"  Scene {sid:>4s} ({char:6s}): converting {recording_path.name}...")
        rec_bytes = recording_path.read_bytes()
        content_type = "audio/mpeg"
        if recording_path.suffix == ".m4a":
            content_type = "audio/mp4"
        elif recording_path.suffix == ".wav":
            content_type = "audio/wav"
        rec_url = await fal_client.upload_async(rec_bytes, content_type=content_type)

        try:
            result = await fal_client.run_async("fal-ai/chatterbox/speech-to-speech", arguments={
                "source_audio_url": rec_url,
                "target_voice_audio_url": ref_urls[char],
            })

            audio_out = result.get("audio", {}).get("url") if isinstance(result, dict) else None
            if audio_out:
                async with httpx.AsyncClient(timeout=120.0) as http:
                    resp = await http.get(audio_out)
                    audio_path.write_bytes(resp.content)
                    converted += 1
                    print(f"           saved ({len(resp.content):,} bytes)")
            else:
                print(f"           ERROR: no audio in result: {result}")

        except Exception as e:
            print(f"           ERROR: {e}")

    print(f"\n  {converted} converted, {skipped} skipped")
    print(f"  Next: python scripts/episode1_produce.py video && python scripts/episode1_produce.py concat")


# ============================================================================
# MAIN
# ============================================================================

async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Episode 1: Speech-to-Speech")
    parser.add_argument("command", choices=["list", "convert"])
    parser.add_argument("scene", nargs="?", default=None, help="Specific scene number")
    args = parser.parse_args()

    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)

    if args.command == "list":
        list_lines()
    elif args.command == "convert":
        await convert_recordings(scene_filter=args.scene)


if __name__ == "__main__":
    asyncio.run(main())
