"""Make an episode end-to-end from a script.md.

Usage:
    # By slug (looks up episodes/<slug>/script.md):
    python scripts/make_episode.py example_hostages

    # By explicit path:
    python scripts/make_episode.py path/to/script.md
    python scripts/make_episode.py path/to/script.md --out episodes/my_run

Pipeline (idempotent — skips any output that already exists):
    1. Parse script.md
    2. For each segment: ElevenLabs TTS -> .mp3
    3. For each segment: VEED Fabric 1.0 lip-sync (image + audio) -> .mp4
    4. ffmpeg concat -> final.mp4
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from src.character import load as load_character, slugs as character_slugs
from src.script_format import parse_file, validate_against_characters
from src.pipeline.episode import generate_tts, lipsync, concat


def _audio_duration(path: Path) -> float:
    """Best-effort audio duration in seconds. Returns 0.0 on failure."""
    try:
        from mutagen.mp3 import MP3  # type: ignore
        return float(MP3(str(path)).info.length)
    except Exception:
        return 0.0


def resolve_script_path(arg: str) -> tuple[Path, Path]:
    """Resolve either a slug or a path. Returns (script_path, episode_dir)."""
    p = Path(arg)
    if p.is_file() and p.suffix == ".md":
        return p, p.parent
    candidate = ROOT / "episodes" / arg / "script.md"
    if candidate.is_file():
        return candidate, candidate.parent
    sys.exit(
        f"ERROR: could not resolve '{arg}' as a script.\n"
        f"  Tried: {p}\n"
        f"  Tried: {candidate.relative_to(ROOT)}\n"
        f"  Available: {[d.name for d in (ROOT / 'episodes').iterdir() if d.is_dir()] if (ROOT / 'episodes').exists() else []}"
    )


async def run(script_path: Path, episode_dir: Path):
    print(f"\n>> Reading {script_path.relative_to(ROOT)}")
    script = parse_file(script_path)

    available = character_slugs()
    errors = validate_against_characters(script, available)
    if errors:
        print("\nERROR: script references unknown characters:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    print(f">> Title:      {script.title or '(no title)'}")
    print(f">> Characters: {script.characters}")
    print(f">> Segments:   {len(script.segments)}")

    # Preflight env vars (CLI mode — keys from .env are fine here since
    # there's no multi-tenant concurrency)
    fal_key = os.environ.get("FAL_KEY") or os.environ.get("FAL_API_KEY")
    elevenlabs_key = os.environ.get("ELEVENLABS_API_KEY")
    if not fal_key:
        sys.exit("ERROR: FAL_KEY not set. Add it to .env or export it.")
    if not elevenlabs_key:
        sys.exit("ERROR: ELEVENLABS_API_KEY not set. Add it to .env or export it.")

    audio_dir = episode_dir / "audio"
    video_dir = episode_dir / "videos"
    audio_dir.mkdir(parents=True, exist_ok=True)
    video_dir.mkdir(parents=True, exist_ok=True)

    char_cache: dict = {}
    video_paths = []
    for i, seg in enumerate(script.segments):
        if seg.character not in char_cache:
            char_cache[seg.character] = load_character(seg.character)
        char = char_cache[seg.character]

        seg_id = f"seg{i:02d}_{seg.character}"
        audio_path = audio_dir / f"{seg_id}.mp3"
        video_path = video_dir / f"{seg_id}.mp4"

        print(f"\n>> Segment #{i+1}: @{seg.character} ({len(seg.text)} chars)")

        t0 = time.time()
        await generate_tts(
            text=seg.text,
            voice_id=char.voice.voice_id,
            output_path=audio_path,
            elevenlabs_api_key=elevenlabs_key,
            stability=char.voice.stability,
            similarity=char.voice.similarity,
            style=char.voice.style,
            tempo=char.voice.tempo,
        )
        gen_secs = time.time() - t0
        audio_secs = _audio_duration(audio_path)
        if audio_secs:
            print(f"   audio:   {audio_path.relative_to(ROOT)}  "
                  f"[{audio_secs:.1f}s of speech, generated in {gen_secs:.1f}s]")
        else:
            print(f"   audio:   {audio_path.relative_to(ROOT)}  "
                  f"[generated in {gen_secs:.1f}s]")

        t1 = time.time()
        last_print = [0.0]
        eta = max(audio_secs * 4, 30.0) if audio_secs else 60.0
        print(f"   lipsync: starting (typical wall-clock for {audio_secs:.1f}s of audio: ~{eta:.0f}s)")
        def cb(elapsed, msg, _last=last_print):
            if elapsed - _last[0] >= 5.0:
                print(f"   lipsync: waited {elapsed:5.0f}s — fal.ai status: {msg}")
                _last[0] = elapsed
        await lipsync(
            char.image_path, audio_path, video_path,
            fal_key=fal_key, progress_cb=cb,
        )
        print(f"   video:   {video_path.relative_to(ROOT)}  [rendered in {time.time()-t1:.0f}s]")

        video_paths.append(video_path)

    final_path = episode_dir / "final.mp4"
    print(f"\n>> Concatenating {len(video_paths)} clips -> {final_path.relative_to(ROOT)}")
    await concat(video_paths, final_path)
    print(f"\n>> DONE: {final_path}")
    print(f"   Open with: open '{final_path}'")
    return final_path


def main():
    p = argparse.ArgumentParser(description="Make an episode from a script.md")
    p.add_argument("target", nargs="?",
                   help="Episode slug (under episodes/) OR path to a script.md")
    p.add_argument("--episode", "-e", dest="episode",
                   help="Alias for the positional target (slug or path).")
    p.add_argument("--out", help="Override output dir (default: alongside the script)")
    args = p.parse_args()

    target = args.target or args.episode
    if not target:
        p.error("must provide an episode slug — either as a positional argument "
                "(`make_episode.py my_slug`) or via --episode (`make_episode.py --episode my_slug`)")

    script_path, default_out = resolve_script_path(target)
    out_dir = Path(args.out) if args.out else default_out
    out_dir.mkdir(parents=True, exist_ok=True)

    asyncio.run(run(script_path, out_dir))


if __name__ == "__main__":
    main()
