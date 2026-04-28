#!/usr/bin/env python3
"""
Pilot episode: "בגדי המלך החדשים" — Netanyahu "No one left behind" episode.
Generates audio for 3 segments, then lip-syncs across multiple visual combos.
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

if "FAL_KEY" not in os.environ and "FAL_API_KEY" in os.environ:
    os.environ["FAL_KEY"] = os.environ["FAL_API_KEY"]

OUTPUT_DIR = Path("output/pilot_hostages")

# --- Script ---

SEGMENTS = {
    "anchor_female": {
        "text": "ועכשיו, למה שאמר המלך ביבי, המנהיג הדגול והנערץ, שמש העמים!",
        "voice_id": "FGY2WhTYpPnrIDTdsKH5",  # Laura - Enthusiast, Quirky
        "emotion_style": 0.6,
        "stability": 0.4,
        "similarity": 0.8,
    },
    "anchor_male": {
        "text": (
            "בעקבות חילוץ הטייס האמריקאי מאיראן, "
            "המנהיג הנפלא אמר: מבצע החילוץ מחזק את העיקרון המקודש, "
            "לא משאירים אף אחד מאחור!"
        ),
        "voice_id": "IKne3meq5aSn9XLyUdCD",  # Charlie - Deep, Confident, Energetic
        "emotion_style": 0.5,
        "stability": 0.4,
        "similarity": 0.8,
    },
    "eden": {
        "text": (
            "אמא... "
            "אבל מתו שם ארבעים ושישה חטופים, נכון? "
            "ואמא, הם במנהרות של חמאס כבר יותר משמונה מאות יום, נכון? "
            "ואמא, המון פעמים אמרת לי שהשבוע הם משתחררים, "
            "ואז אמרת מילה מוזרה כזאת, מממ... שוב הם טירפדו, נכון? "
            "אז מה, בעצם הפקרנו אותם שם?"
        ),
        "voice_id": "cgSgspJ2msm6clMCkdW9",  # Jessica - Playful, Bright, Warm
        "emotion_style": 0.2,
        "stability": 0.6,
        "similarity": 0.7,
    },
}

# --- Visual combos ---

COMBOS = {
    "combo1_all_sp": {
        "name": "All South Park",
        "images": {
            "anchor_female": "output/anchor_options/female_sp1.png",
            "anchor_male": "output/anchor_options/male_sp1.png",
            "eden": "output/girl_options_v2/girl_v2b.png",
        },
    },
    "combo2_puppet_anchors": {
        "name": "Puppet anchors + SP girl",
        "images": {
            "anchor_female": "output/anchor_options/female_puppet1.png",
            "anchor_male": "output/anchor_options/male_puppet1.png",
            "eden": "output/girl_options_v2/girl_v2b.png",
        },
    },
    "combo3_sp_confused": {
        "name": "SP anchors + confused Eden",
        "images": {
            "anchor_female": "output/anchor_options/female_sp1.png",
            "anchor_male": "output/anchor_options/male_sp1.png",
            "eden": "output/girl_options_v2/girl_v2c.png",
        },
    },
}


async def generate_audio(segment_name: str, segment: dict, output_path: Path) -> Path:
    """Generate audio with ElevenLabs v3 Hebrew."""
    if output_path.exists():
        print(f"  SKIP audio {segment_name} (exists)")
        return output_path

    print(f"  Generating audio: {segment_name}...")
    api_key = os.environ["ELEVENLABS_API_KEY"]

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{segment['voice_id']}",
            headers={"xi-api-key": api_key},
            json={
                "text": segment["text"],
                "model_id": "eleven_v3",
                "language_code": "he",
                "voice_settings": {
                    "stability": segment.get("stability", 0.5),
                    "similarity_boost": segment.get("similarity", 0.8),
                    "style": segment.get("emotion_style", 0.3),
                },
            },
        )
        response.raise_for_status()
        output_path.write_bytes(response.content)
        print(f"  ✓ Audio: {output_path}")
        return output_path


async def generate_video(image_path: Path, audio_path: Path, output_path: Path, label: str) -> Path:
    """Generate lip-synced video with VEED Fabric 1.0."""
    if output_path.exists():
        print(f"    SKIP video {label} (exists)")
        return output_path

    print(f"    Uploading {label}...")
    image_url = await fal_client.upload_file_async(str(image_path))
    audio_url = await fal_client.upload_file_async(str(audio_path))

    print(f"    Submitting VEED Fabric: {label}...")
    handler = await fal_client.submit_async(
        "veed/fabric-1.0",
        arguments={
            "image_url": image_url,
            "audio_url": audio_url,
            "resolution": "480p",
        },
    )

    start = time.time()
    while True:
        status = await handler.status()
        elapsed = time.time() - start
        if isinstance(status, fal_client.Completed):
            print(f"    ✓ Video complete: {label} ({elapsed:.0f}s)")
            break
        elif isinstance(status, fal_client.InProgress):
            logs = status.logs or []
            if logs:
                last = logs[-1]
                msg = last.get("message", "") if isinstance(last, dict) else str(last)
                print(f"      [{elapsed:.0f}s] {msg[:60]}")
        await asyncio.sleep(8)

    result = await handler.get()
    video_url = result["video"]["url"]

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.get(video_url)
        response.raise_for_status()
        output_path.write_bytes(response.content)

    return output_path


async def concat_videos(video_paths: list, output_path: Path, label: str) -> Path:
    """Concatenate videos with FFmpeg."""
    if output_path.exists():
        print(f"  SKIP concat {label} (exists)")
        return output_path

    # Write file list
    list_path = output_path.parent / f"{output_path.stem}_list.txt"
    with open(list_path, "w") as f:
        for vp in video_paths:
            f.write(f"file '{vp.resolve()}'\n")

    print(f"  Concatenating {label}...")
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_path), "-c", "copy", str(output_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        # Try re-encoding if copy fails
        print(f"  Re-encoding {label} (codec mismatch)...")
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(list_path),
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            str(output_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.wait()

    list_path.unlink(missing_ok=True)
    print(f"  ✓ Final: {output_path}")
    return output_path


async def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    audio_dir = OUTPUT_DIR / "audio"
    audio_dir.mkdir(exist_ok=True)

    step = sys.argv[1] if len(sys.argv) > 1 else "all"

    # =====================
    # STEP 1: Generate audio (shared across all combos)
    # =====================
    if step in ("all", "audio"):
        print("=" * 50)
        print("STEP 1: Generating audio")
        print("=" * 50)
        for seg_name, seg in SEGMENTS.items():
            audio_path = audio_dir / f"{seg_name}.mp3"
            await generate_audio(seg_name, seg, audio_path)
        print()

    # =====================
    # STEP 2: Generate videos for each combo
    # =====================
    if step in ("all", "video"):
        print("=" * 50)
        print("STEP 2: Generating lip-sync videos")
        print("=" * 50)
        for combo_name, combo in COMBOS.items():
            combo_dir = OUTPUT_DIR / combo_name
            combo_dir.mkdir(exist_ok=True)
            print(f"\n--- {combo['name']} ({combo_name}) ---")

            for seg_name in ["anchor_female", "anchor_male", "eden"]:
                image_path = Path(combo["images"][seg_name])
                audio_path = audio_dir / f"{seg_name}.mp3"
                video_path = combo_dir / f"{seg_name}.mp4"
                label = f"{combo_name}/{seg_name}"
                await generate_video(image_path, audio_path, video_path, label)
        print()

    # =====================
    # STEP 3: Concatenate each combo
    # =====================
    if step in ("all", "concat"):
        print("=" * 50)
        print("STEP 3: Concatenating")
        print("=" * 50)
        for combo_name, combo in COMBOS.items():
            combo_dir = OUTPUT_DIR / combo_name
            video_paths = [
                combo_dir / "anchor_female.mp4",
                combo_dir / "anchor_male.mp4",
                combo_dir / "eden.mp4",
            ]
            if all(vp.exists() for vp in video_paths):
                final_path = OUTPUT_DIR / f"final_{combo_name}.mp4"
                await concat_videos(video_paths, final_path, combo_name)
            else:
                missing = [str(vp) for vp in video_paths if not vp.exists()]
                print(f"  SKIP {combo_name} — missing: {missing}")

    print("\n" + "=" * 50)
    print("DONE! Compare these:")
    for combo_name, combo in COMBOS.items():
        final = OUTPUT_DIR / f"final_{combo_name}.mp4"
        if final.exists():
            print(f"  {combo['name']}: {final}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
