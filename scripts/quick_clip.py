#!/usr/bin/env python3
"""
Quick clip generator: image + text → audio → lip-synced video.
Usage: python scripts/quick_clip.py
"""

import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

import httpx
import fal_client

# fal_client expects FAL_KEY
if "FAL_KEY" not in os.environ and "FAL_API_KEY" in os.environ:
    os.environ["FAL_KEY"] = os.environ["FAL_API_KEY"]

# --- Config ---
OUTPUT_DIR = Path("output/quick_clips")
CLIP_NAME = "bibi_caskets"

IMAGE_PATH = Path("output/episode1/images/bibi_scheming.png")
TEXT = "היי, בשביל מוכר ארונות חיילים שהותרו לפרסום זה ביזנס... אל תפריעו"
VOICE_ID = "aooUHbQzVbqHLJx3zbYH"  # Bibi cloned voice
EMOTION = "serious"
TEMPO = 1.25  # Bibi speaks faster


async def generate_audio(output_path: Path) -> Path:
    """Generate audio with ElevenLabs v3."""
    if output_path.exists():
        print(f"  SKIP audio (exists)")
        return output_path

    print(f"  Generating audio...")
    api_key = os.environ["ELEVENLABS_API_KEY"]

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}",
            headers={"xi-api-key": api_key},
            json={
                "text": TEXT,
                "model_id": "eleven_v3",
                "language_code": "he",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.8,
                    "style": 0.3,
                },
            },
        )
        response.raise_for_status()
        output_path.write_bytes(response.content)
        print(f"  ✓ Audio saved: {output_path}")
        return output_path


async def apply_tempo(input_path: Path, output_path: Path) -> Path:
    """Apply tempo adjustment with ffmpeg."""
    if output_path.exists():
        print(f"  SKIP tempo (exists)")
        return output_path

    print(f"  Applying {TEMPO}x tempo...")
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-i", str(input_path),
        "-filter:a", f"atempo={TEMPO}",
        str(output_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.wait()
    print(f"  ✓ Tempo adjusted: {output_path}")
    return output_path


async def generate_video(image_path: Path, audio_path: Path, output_path: Path) -> Path:
    """Generate lip-synced video with VEED Fabric 1.0."""
    if output_path.exists():
        print(f"  SKIP video (exists)")
        return output_path

    print(f"  Uploading assets to fal.ai...")
    image_url = await fal_client.upload_file_async(str(image_path))
    audio_url = await fal_client.upload_file_async(str(audio_path))

    print(f"  Submitting VEED Fabric job...")
    handler = await fal_client.submit_async(
        "veed/fabric-1.0",
        arguments={
            "image_url": image_url,
            "audio_url": audio_url,
            "resolution": "480p",
        },
    )

    # Poll for completion
    start = time.time()
    while True:
        status = await handler.status()
        elapsed = time.time() - start
        if isinstance(status, fal_client.Completed):
            print(f"  ✓ Video complete ({elapsed:.0f}s)")
            break
        elif isinstance(status, fal_client.InProgress):
            logs = status.logs or []
            if logs:
                print(f"    [{elapsed:.0f}s] {logs[-1].get('message', '')[:80]}")
        await asyncio.sleep(10)

    result = await handler.get()
    video_url = result["video"]["url"]

    # Download
    print(f"  Downloading video...")
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.get(video_url)
        response.raise_for_status()
        output_path.write_bytes(response.content)
        print(f"  ✓ Video saved: {output_path}")

    return output_path


async def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    audio_raw = OUTPUT_DIR / f"{CLIP_NAME}_raw.mp3"
    audio_final = OUTPUT_DIR / f"{CLIP_NAME}_audio.mp3"
    video_out = OUTPUT_DIR / f"{CLIP_NAME}.mp4"

    print(f"Image: {IMAGE_PATH}")
    print(f"Text: {TEXT}")
    print(f"Voice: Bibi ({VOICE_ID})")
    print()

    # Step 1: Audio
    await generate_audio(audio_raw)

    # Step 2: Tempo
    await apply_tempo(audio_raw, audio_final)

    # Step 3: Video
    await generate_video(IMAGE_PATH, audio_final, video_out)

    print(f"\n{'='*50}")
    print(f"DONE! Output: {video_out}")


if __name__ == "__main__":
    asyncio.run(main())
