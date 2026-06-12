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
import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from src.character import load as load_character, slugs as character_slugs
from src.script_format import parse_file, validate_against_characters
from src.pipeline.episode import (
    generate_tts, lipsync, concat, generate_animation, mux_audio_over_video,
)


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

    overrides_path = episode_dir / "voice_overrides.json"
    voice_overrides: dict[str, str] = {}
    applied_path = episode_dir / ".voice_overrides_applied.json"
    if overrides_path.exists():
        try:
            voice_overrides = json.loads(overrides_path.read_text(encoding="utf-8"))
            if voice_overrides:
                print(f">> Voice overrides: {voice_overrides}")
        except (OSError, json.JSONDecodeError) as exc:
            print(f"WARN: failed to read {overrides_path.name}: {exc}")

    # If the override map differs from what was last applied, invalidate cached
    # audio + videos for any character whose voice changed, so the pipeline
    # actually re-runs TTS+lipsync with the new voice.
    previously_applied: dict[str, str] = {}
    if applied_path.exists():
        try:
            previously_applied = json.loads(applied_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            previously_applied = {}
    changed_characters = {
        slug for slug in set(voice_overrides) | set(previously_applied)
        if voice_overrides.get(slug) != previously_applied.get(slug)
    }
    if changed_characters:
        print(f">> Voice changed for {sorted(changed_characters)} — clearing cached audio/videos")
        for path in list(audio_dir.glob("seg*_*.mp3")) + list(audio_dir.glob("seg*_*.mp3_raw")):
            for slug in changed_characters:
                if path.stem.endswith(f"_{slug}") or path.name.endswith(f"_{slug}.mp3") or path.name.endswith(f"_{slug}.mp3_raw"):
                    path.unlink(missing_ok=True)
                    break
        for path in list(video_dir.glob("seg*_*.mp4")):
            for slug in changed_characters:
                if path.stem.endswith(f"_{slug}"):
                    path.unlink(missing_ok=True)
                    break
        (episode_dir / "final.mp4").unlink(missing_ok=True)
    applied_path.write_text(json.dumps(voice_overrides, indent=2), encoding="utf-8")

    char_cache: dict = {}
    video_paths = []

    def _resolve_voice(slug: str):
        """Load a character + its effective voice id. Only called when a segment
        actually needs a voice (dialogue, or a scene WITH narration) — silent
        scenes don't need a character at all."""
        if slug not in char_cache:
            char_cache[slug] = load_character(slug)
        c = char_cache[slug]
        return c, voice_overrides.get(slug, c.voice.voice_id)

    for i, seg in enumerate(script.segments):
        seg_id = f"seg{i:02d}_{seg.character or 'scene'}"
        audio_path = audio_dir / f"{seg_id}.mp3"
        video_path = video_dir / f"{seg_id}.mp4"

        def _progress(label):
            """Build a ~5s-throttled status printer for a fal.ai job."""
            _last = [0.0]
            def cb(elapsed, msg):
                if elapsed - _last[0] >= 5.0:
                    print(f"   {label}: waited {elapsed:5.0f}s — fal.ai status: {msg}")
                    _last[0] = elapsed
            return cb

        # ── Animation scene: generate a clip from a text prompt, narrate over it ──
        if seg.is_scene:
            print(f"\n>> Segment #{i+1}: 🎬 scene — \"{seg.animation}\"")
            anim_path = video_dir / f"{seg_id}_anim.mp4"
            t0 = time.time()
            print("   anim:    generating via fal.ai Kling (text-to-video)…")
            await generate_animation(
                seg.animation, anim_path,
                fal_key=fal_key, progress_cb=_progress("anim"),
            )
            print(f"   anim:    {anim_path.relative_to(ROOT)}  [rendered in {time.time()-t0:.0f}s]")

            if seg.text.strip():
                char, voice_id = _resolve_voice(seg.character)
                await generate_tts(
                    text=seg.text,
                    voice_id=voice_id,
                    output_path=audio_path,
                    elevenlabs_api_key=elevenlabs_key,
                    stability=char.voice.stability,
                    similarity=char.voice.similarity,
                    style=char.voice.style,
                    tempo=char.voice.tempo,
                )
                print(f"   narration: {audio_path.relative_to(ROOT)} "
                      f"[{_audio_duration(audio_path):.1f}s]")
                await mux_audio_over_video(anim_path, audio_path, video_path)
            else:
                # Silent scene — the animation clip is the segment as-is.
                if not video_path.exists():
                    shutil.copyfile(anim_path, video_path)
            print(f"   video:   {video_path.relative_to(ROOT)}")
            video_paths.append(video_path)
            continue

        # ── Dialogue: TTS the line, lip-sync it onto the character's still ──
        char, voice_id = _resolve_voice(seg.character)
        print(f"\n>> Segment #{i+1}: @{seg.character} ({len(seg.text)} chars)")
        if voice_id != char.voice.voice_id:
            print(f"   voice:   override -> {voice_id}")

        t0 = time.time()
        await generate_tts(
            text=seg.text,
            voice_id=voice_id,
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
        eta = max(audio_secs * 4, 30.0) if audio_secs else 60.0
        print(f"   lipsync: starting (typical wall-clock for {audio_secs:.1f}s of audio: ~{eta:.0f}s)")
        await lipsync(
            char.image_path, audio_path, video_path,
            fal_key=fal_key, progress_cb=_progress("lipsync"),
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
