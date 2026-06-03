#!/usr/bin/env python3
"""
Pilot v2: Anchors behind desk, faster/more energetic voices, improved Eden script.
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
from google import genai
from google.genai import types

if "FAL_KEY" not in os.environ and "FAL_API_KEY" in os.environ:
    os.environ["FAL_KEY"] = os.environ["FAL_API_KEY"]

OUTPUT_DIR = Path("output/pilot_v3")

# --- Improved anchor images ---

STYLE_SOUTHPARK = (
    "South Park cartoon style, flat 2D paper cutout animation, "
    "simple geometric shapes, thick black outlines, bright flat colors, "
    "construction-paper texture, Comedy Central South Park aesthetic"
)

ANCHOR_IMAGES = {
    "anchor_female_desk": (
        "Generate a 9:16 image of a young Israeli Sephardic/Mizrahi woman TV news anchor "
        "in her early 30s, sitting behind a professional TV news desk in a studio. "
        "Dark olive skin, big dark eyes with heavy dramatic makeup and fake eyelashes, "
        "long straight dark hair, full lips, sharp eyebrows, gold hoop earrings, "
        "wearing a tight black top with large number '14' printed on it. "
        "She is sitting at a curved modern TV news anchor desk with microphone on desk. "
        "Behind her a large screen showing '14' channel logo and 'חדשות' text. "
        "Aggressive confident expression, mouth open mid-sentence, gesturing with hand. "
        "Blue studio lighting. "
        f"Rendered in {STYLE_SOUTHPARK}."
    ),
    "anchor_male_desk": (
        "Generate a 9:16 image of a young Israeli Sephardic/Mizrahi man TV news anchor "
        "in his early 30s, sitting behind a professional TV news desk in a studio. "
        "Dark olive skin, short dark hair with gel slicked back, thick eyebrows, "
        "stubble beard, gold chain visible, muscular build, "
        "wearing a tight dark polo shirt with large number '14' printed on it. "
        "He is sitting at a curved modern TV news anchor desk with microphone on desk. "
        "Behind him a large screen showing '14' channel logo. "
        "Cocky aggressive smirk, leaning forward, one fist on desk. "
        "Blue studio lighting. "
        f"Rendered in {STYLE_SOUTHPARK}."
    ),
}

# --- Audio segments ---

SEGMENTS = {
    "anchor_female_1": {
        "text": (
            "אני מאוהבת, איזה מנהיג חזק, איזה מנהיג דגול יש לנו, קרה לנו נס!"
        ),
        "voice_id": "FGY2WhTYpPnrIDTdsKH5",  # Laura
        "stability": 0.25,
        "similarity": 0.75,
        "emotion_style": 0.85,
        "tempo": 1.25,
    },
    "anchor_male_1": {
        "text": (
            "לגמרי! באיראן השמדנו הכל! "
            "אומרים שאפילו חורשט סבזי ואושפלאו אי אפשר למצוא שם!"
        ),
        "voice_id": "IKne3meq5aSn9XLyUdCD",  # Charlie
        "stability": 0.20,
        "similarity": 0.75,
        "emotion_style": 0.90,
        "tempo": 1.25,
    },
    "anchor_female_2": {
        "text": (
            "ככה נראה ניצחון מוחלט! אין לנו יותר אויבים! איזה מנהיג!"
        ),
        "voice_id": "FGY2WhTYpPnrIDTdsKH5",  # Laura
        "stability": 0.25,
        "similarity": 0.75,
        "emotion_style": 0.85,
        "tempo": 1.25,
    },
    "anchor_male_2": {
        "text": (
            "ממש! אפילו החמוצים בשמאל חייבים להודות! "
            "מנהיג ענק, חד פעמי, בן גוריון אבל פי אלף!"
        ),
        "voice_id": "IKne3meq5aSn9XLyUdCD",  # Charlie
        "stability": 0.20,
        "similarity": 0.75,
        "emotion_style": 0.90,
        "tempo": 1.25,
    },
    "eden": {
        "text": (
            "אבל אמא, החמאס בעזה נשאר, לא? "
            "החיזבאללה ממשיכים עם הטילים וכל הצפון מופגז. "
            "גם באיראן לא קרה שום דבר. "
            "אמא, ככה נראה ניצחון מוחלט? ככה נראה ביטחון?"
        ),
        "voice_id": "cgSgspJ2msm6clMCkdW9",  # Jessica
        "stability": 0.55,
        "similarity": 0.7,
        "emotion_style": 0.25,   # Subtle, innocent
        "tempo": 1.0,            # Natural pace for the child
    },
}

EDEN_IMAGE = "output/girl_options_v2/girl_v2b.png"


async def generate_images():
    """Generate anchor images with desk."""
    api_key = os.environ.get("GOOGLE_API_KEY")
    client = genai.Client(api_key=api_key)
    img_dir = OUTPUT_DIR / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    for name, prompt in ANCHOR_IMAGES.items():
        output_path = img_dir / f"{name}.png"
        if output_path.exists():
            print(f"  SKIP {name} (exists)")
            continue

        print(f"  Generating {name}...")
        try:
            response = client.models.generate_content(
                model="nano-banana-pro-preview",
                contents=[prompt],
                config=types.GenerateContentConfig(response_modalities=["image", "text"]),
            )
            for part in response.candidates[0].content.parts:
                if hasattr(part, "inline_data") and part.inline_data:
                    output_path.write_bytes(part.inline_data.data)
                    print(f"  ✓ {output_path}")
                    break
        except Exception as e:
            print(f"  ✗ Error: {e}")
        await asyncio.sleep(2)


async def generate_audio():
    """Generate audio with ElevenLabs + tempo adjustment."""
    audio_dir = OUTPUT_DIR / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    api_key = os.environ["ELEVENLABS_API_KEY"]

    for seg_name, seg in SEGMENTS.items():
        final_path = audio_dir / f"{seg_name}.mp3"
        if final_path.exists():
            print(f"  SKIP audio {seg_name} (exists)")
            continue

        raw_path = audio_dir / f"{seg_name}_raw.mp3"

        # Generate TTS
        if not raw_path.exists():
            print(f"  Generating audio: {seg_name}...")
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"https://api.elevenlabs.io/v1/text-to-speech/{seg['voice_id']}",
                    headers={"xi-api-key": api_key},
                    json={
                        "text": seg["text"],
                        "model_id": "eleven_v3",
                        "language_code": "he",
                        "voice_settings": {
                            "stability": seg["stability"],
                            "similarity_boost": seg["similarity"],
                            "style": seg["emotion_style"],
                        },
                    },
                )
                response.raise_for_status()
                raw_path.write_bytes(response.content)
                print(f"  ✓ Raw audio: {raw_path}")

        # Apply tempo
        tempo = seg.get("tempo", 1.0)
        if tempo != 1.0:
            print(f"  Applying {tempo}x tempo: {seg_name}...")
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-y", "-i", str(raw_path),
                "-filter:a", f"atempo={tempo}",
                str(final_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.wait()
            print(f"  ✓ Tempo adjusted: {final_path}")
        else:
            # Just copy
            import shutil
            shutil.copy2(raw_path, final_path)
            print(f"  ✓ Audio (no tempo change): {final_path}")


async def generate_video(image_path: Path, audio_path: Path, output_path: Path, label: str) -> Path:
    """Generate lip-synced video with VEED Fabric 1.0."""
    if output_path.exists():
        print(f"  SKIP video {label} (exists)")
        return output_path

    print(f"  Uploading {label}...")
    image_url = await fal_client.upload_file_async(str(image_path))
    audio_url = await fal_client.upload_file_async(str(audio_path))

    print(f"  Submitting VEED Fabric: {label}...")
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
            print(f"  ✓ Video complete: {label} ({elapsed:.0f}s)")
            break
        elif isinstance(status, fal_client.InProgress):
            logs = status.logs or []
            if logs:
                last = logs[-1]
                msg = last.get("message", "") if isinstance(last, dict) else str(last)
                print(f"    [{elapsed:.0f}s] {msg[:60]}")
        await asyncio.sleep(8)

    result = await handler.get()
    video_url = result["video"]["url"]

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.get(video_url)
        response.raise_for_status()
        output_path.write_bytes(response.content)

    return output_path


async def generate_videos():
    """Generate lip-sync videos for all 3 segments."""
    video_dir = OUTPUT_DIR / "videos"
    video_dir.mkdir(parents=True, exist_ok=True)
    audio_dir = OUTPUT_DIR / "audio"

    image_map = {
        "anchor_female_1": OUTPUT_DIR / "images" / "anchor_female_desk.png",
        "anchor_male_1": OUTPUT_DIR / "images" / "anchor_male_desk.png",
        "anchor_female_2": OUTPUT_DIR / "images" / "anchor_female_desk.png",
        "anchor_male_2": OUTPUT_DIR / "images" / "anchor_male_desk.png",
        "eden": Path(EDEN_IMAGE),
    }

    for seg_name in ["anchor_female_1", "anchor_male_1", "anchor_female_2", "anchor_male_2", "eden"]:
        await generate_video(
            image_map[seg_name],
            audio_dir / f"{seg_name}.mp3",
            video_dir / f"{seg_name}.mp4",
            seg_name,
        )


async def concat():
    """Concatenate all segments into final video."""
    video_dir = OUTPUT_DIR / "videos"
    final_path = OUTPUT_DIR / "final.mp4"

    if final_path.exists():
        print(f"  SKIP concat (exists)")
        return

    video_paths = [
        video_dir / "anchor_female_1.mp4",
        video_dir / "anchor_male_1.mp4",
        video_dir / "anchor_female_2.mp4",
        video_dir / "anchor_male_2.mp4",
        video_dir / "eden.mp4",
    ]

    if not all(vp.exists() for vp in video_paths):
        missing = [str(vp) for vp in video_paths if not vp.exists()]
        print(f"  Missing videos: {missing}")
        return

    list_path = OUTPUT_DIR / "concat_list.txt"
    with open(list_path, "w") as f:
        for vp in video_paths:
            f.write(f"file '{vp.resolve()}'\n")

    print(f"  Concatenating final video...")
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_path), "-c", "copy", str(final_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        print(f"  Re-encoding (codec mismatch)...")
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(list_path),
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            str(final_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.wait()

    list_path.unlink(missing_ok=True)
    print(f"  ✓ Final: {final_path}")


async def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    step = sys.argv[1] if len(sys.argv) > 1 else "all"

    if step in ("all", "images"):
        print("=" * 50)
        print("STEP 1: Generating anchor images (at desk)")
        print("=" * 50)
        await generate_images()
        print()

    if step in ("all", "audio"):
        print("=" * 50)
        print("STEP 2: Generating audio (energetic + tempo)")
        print("=" * 50)
        await generate_audio()
        print()

    if step in ("all", "video"):
        print("=" * 50)
        print("STEP 3: Generating lip-sync videos")
        print("=" * 50)
        await generate_videos()
        print()

    if step in ("all", "concat"):
        print("=" * 50)
        print("STEP 4: Concatenating")
        print("=" * 50)
        await concat()
        print()

    print("DONE!")
    final = OUTPUT_DIR / "final.mp4"
    if final.exists():
        dur = os.popen(f"ffprobe -v quiet -show_entries format=duration -of csv=p=0 '{final}'").read().strip()
        print(f"  Output: {final} ({dur}s)")


if __name__ == "__main__":
    asyncio.run(main())
