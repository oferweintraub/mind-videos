#!/usr/bin/env python3
"""
March 31 Style Comparison: Generate 4 art styles from Silman reference photo,
then create lip-synced talking head videos using Aurora and VEED Fabric.

Styles: anime, south_park, clay_puppet, pencil_strokes
Lip-sync: Aurora (creatify/aurora) + VEED Fabric (veed/fabric-1.0)
Audio: ElevenLabs v3, Silman voice, 2 Hebrew sentences

Usage:
    python scripts/march31_styles.py          # Full pipeline
    python scripts/march31_styles.py images   # Only generate images
    python scripts/march31_styles.py audio    # Only generate audio
    python scripts/march31_styles.py videos   # Only generate videos
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv

load_dotenv()

import fal_client
import httpx

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

OUTPUT_DIR = Path("output/march_31")
REFERENCE_IMG = OUTPUT_DIR / "reference_silman.png"

# Silman voice (ElevenLabs)
SILMAN_VOICE_ID = "LtYcxc0xwy3LHnPjIUBt"

# Hebrew sentences — joined with a pause
SENTENCE_1 = "אחרי שחרור כל החטופים, על מה יפגינו בכיכר החטופים בקפלן?"
SENTENCE_2 = "מי קבע מהי ועדת חקירה ממלכתית? החוק? ומי קבע את החוק?"
COMBINED_TEXT = f"{SENTENCE_1} ... {SENTENCE_2}"

# Expression direction: on the verge of a nervous breakdown, acute distress
EXPRESSION = (
    "She has an extremely stressed, unhinged expression — eyes wide open showing the whites, "
    "pupils dilated, eyebrows raised asymmetrically, visible tension in her face muscles, "
    "like someone one second before a nervous breakdown who is barely holding it together. "
    "Jaw clenched, forced smile that looks more like a grimace, sweat on her forehead, "
    "slightly disheveled appearance. Acute psychological distress. "
)

# Style prompts for Nano Banana Pro (reference-based)
STYLES = {
    "anime": (
        "Transform this woman into Japanese anime art style. "
        "Large expressive eyes, smooth cel-shaded skin, vibrant hair highlights, "
        "anime aesthetic. Keep the SAME face shape, curly dark hair with headband, "
        "and professional dark blazer. " + EXPRESSION +
        "9:16 portrait, studio background."
    ),
    "south_park": (
        "Transform this woman into South Park cartoon style. "
        "Simple 2D construction paper cutout look, round head, "
        "very simple geometric shapes, thick black outlines, flat colors. "
        "Keep the headband, curly dark hair, and dark blazer. "
        "IMPORTANT: must have a clearly visible open mouth with teeth. " + EXPRESSION +
        "South Park TV show aesthetic. 9:16 portrait."
    ),
    "clay_puppet": (
        "Transform this woman into a claymation puppet, stop-motion animation style. "
        "Smooth clay texture, rounded features, visible fingerprint marks on clay, "
        "Wallace and Gromit quality. Warm studio lighting. "
        "Keep the headband, curly dark hair, and dark blazer. " + EXPRESSION +
        "9:16 portrait."
    ),
    "pencil_strokes": (
        "Transform this woman into broad pencil strokes illustration style. "
        "Bold, expressive charcoal and pencil strokes, sketch-like quality, "
        "hatching and crosshatching, visible paper texture, editorial illustration. "
        "Keep the headband, curly dark hair, and dark blazer. " + EXPRESSION +
        "9:16 portrait."
    ),
}

# Lip-sync models on fal.ai
LIPSYNC_MODELS = {
    "aurora": "fal-ai/creatify/aurora",
    "veed": "veed/fabric-1.0",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_audio_duration(audio_path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(audio_path)],
        capture_output=True,
        text=True,
    )
    info = json.loads(result.stdout)
    return float(info["format"]["duration"])


async def upload_to_fal(data: bytes, content_type: str) -> str:
    url = await fal_client.upload_async(data, content_type=content_type)
    return url


# ---------------------------------------------------------------------------
# Step 1: Generate style images
# ---------------------------------------------------------------------------


async def generate_style_images():
    from google import genai
    from google.genai import types

    images_dir = OUTPUT_DIR / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    ref_bytes = REFERENCE_IMG.read_bytes()

    for style_name, style_prompt in STYLES.items():
        out_path = images_dir / f"{style_name}.png"
        if out_path.exists():
            print(f"  [images] {style_name}: exists, skipping")
            continue

        print(f"  [images] {style_name}: generating...")

        prompt = (
            f"Using this reference photo of the woman, {style_prompt} "
            "Maintain the SAME person's identity and features."
        )

        response = client.models.generate_content(
            model="nano-banana-pro-preview",
            contents=[
                types.Part.from_bytes(data=ref_bytes, mime_type="image/png"),
                prompt,
            ],
            config=types.GenerateContentConfig(response_modalities=["image", "text"]),
        )

        image_bytes = None
        if response.candidates:
            for c in response.candidates:
                if c.content and c.content.parts:
                    for p in c.content.parts:
                        if hasattr(p, "inline_data") and p.inline_data:
                            image_bytes = p.inline_data.data
                            break

        if not image_bytes:
            print(f"  [images] {style_name}: FAILED - no image in response")
            # Print any text response for debugging
            if response.candidates:
                for c in response.candidates:
                    if c.content and c.content.parts:
                        for p in c.content.parts:
                            if hasattr(p, "text") and p.text:
                                print(f"           Response: {p.text[:200]}")
            continue

        out_path.write_bytes(image_bytes)
        print(f"  [images] {style_name}: saved ({len(image_bytes):,} bytes)")

    # Summary
    generated = list((images_dir).glob("*.png"))
    print(f"\n  [images] {len(generated)}/{len(STYLES)} style images ready")


# ---------------------------------------------------------------------------
# Step 2: Generate audio
# ---------------------------------------------------------------------------


async def generate_audio():
    from elevenlabs import AsyncElevenLabs, VoiceSettings

    audio_dir = OUTPUT_DIR / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    out_path = audio_dir / "silman_combined.mp3"
    if out_path.exists():
        duration = get_audio_duration(out_path)
        print(f"  [audio] Combined audio exists ({duration:.1f}s), skipping")
        return

    print(f"  [audio] Generating combined Hebrew audio with ElevenLabs v3...")
    print(f"  [audio] Text: {COMBINED_TEXT}")

    client = AsyncElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

    voice_settings = VoiceSettings(
        stability=0.5,
        similarity_boost=0.75,
        style=0.5,
    )

    audio_generator = client.text_to_speech.convert(
        voice_id=SILMAN_VOICE_ID,
        model_id="eleven_v3",
        text=COMBINED_TEXT,
        voice_settings=voice_settings,
        language_code="he",
    )

    audio_chunks = []
    async for chunk in audio_generator:
        audio_chunks.append(chunk)

    audio_bytes = b"".join(audio_chunks)
    out_path.write_bytes(audio_bytes)

    duration = get_audio_duration(out_path)
    print(f"  [audio] Saved: {out_path} ({len(audio_bytes):,} bytes, {duration:.1f}s)")


# ---------------------------------------------------------------------------
# Step 3: Lip-sync videos
# ---------------------------------------------------------------------------


async def run_lipsync(
    model_key: str,
    model_id: str,
    image_url: str,
    audio_url: str,
    style_name: str,
    output_path: Path,
) -> dict:
    """Run a single lip-sync job on fal.ai."""
    label = f"{style_name}/{model_key}"

    if model_key == "veed":
        payload = {"image_url": image_url, "audio_url": audio_url, "resolution": "480p"}
    elif model_key == "aurora":
        payload = {"image_url": image_url, "audio_url": audio_url}
    else:
        payload = {"image_url": image_url, "audio_url": audio_url}

    print(f"  [{label}] Submitting to {model_id}...")
    t0 = time.time()

    handle = await fal_client.submit_async(model_id, arguments=payload)
    request_id = handle.request_id
    print(f"  [{label}] Job: {request_id}")

    # Poll until done
    elapsed = 0
    poll_interval = 5
    max_wait = 600

    while elapsed < max_wait:
        status = await fal_client.status_async(model_id, request_id, with_logs=True)
        if isinstance(status, fal_client.Completed):
            break
        if hasattr(status, "error") and status.error:
            wall_time = time.time() - t0
            print(f"  [{label}] FAILED: {status.error}")
            return {"style": style_name, "model": model_key, "error": str(status.error), "wall_time": wall_time}
        if elapsed % 30 == 0:
            print(f"  [{label}] Waiting... ({elapsed}s)")
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
    else:
        wall_time = time.time() - t0
        print(f"  [{label}] TIMEOUT after {max_wait}s")
        return {"style": style_name, "model": model_key, "error": "timeout", "wall_time": wall_time}

    wall_time = time.time() - t0
    print(f"  [{label}] Done in {wall_time:.0f}s")

    result = await fal_client.result_async(model_id, request_id)

    # Extract video URL
    video_url = None
    if isinstance(result, dict):
        vid = result.get("video", {})
        if isinstance(vid, dict):
            video_url = vid.get("url")
        else:
            video_url = result.get("video_url")
    elif hasattr(result, "video"):
        v = result.video
        video_url = v.url if hasattr(v, "url") else v

    if not video_url:
        print(f"  [{label}] No video URL in result: {str(result)[:200]}")
        return {"style": style_name, "model": model_key, "error": "no video URL", "wall_time": wall_time}

    # Download video
    async with httpx.AsyncClient(timeout=120) as http:
        resp = await http.get(video_url)
        resp.raise_for_status()
        video_bytes = resp.content

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(video_bytes)
    print(f"  [{label}] Saved: {output_path} ({len(video_bytes) / 1024:.0f} KB)")

    return {"style": style_name, "model": model_key, "path": str(output_path), "wall_time": wall_time}


async def generate_videos():
    """Generate lip-sync videos for all style images x lip-sync models."""
    videos_dir = OUTPUT_DIR / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)

    images_dir = OUTPUT_DIR / "images"
    audio_path = OUTPUT_DIR / "audio" / "silman_combined.mp3"

    if not audio_path.exists():
        print("  [videos] ERROR: audio file not found, run audio step first")
        return

    # Upload audio once
    print("  [videos] Uploading audio to fal.ai...")
    audio_url = await upload_to_fal(audio_path.read_bytes(), "audio/mpeg")
    print(f"  [videos] Audio URL: {audio_url[:80]}...")

    # Upload each style image and queue jobs
    tasks = []
    for style_name in STYLES:
        img_path = images_dir / f"{style_name}.png"
        if not img_path.exists():
            print(f"  [videos] SKIP {style_name}: no image found")
            continue

        print(f"  [videos] Uploading {style_name} image...")
        image_url = await upload_to_fal(img_path.read_bytes(), "image/png")

        for model_key, model_id in LIPSYNC_MODELS.items():
            out_path = videos_dir / f"{style_name}_{model_key}.mp4"
            if out_path.exists():
                print(f"  [videos] {style_name}_{model_key}: exists, skipping")
                continue

            tasks.append(
                run_lipsync(model_key, model_id, image_url, audio_url, style_name, out_path)
            )

    if not tasks:
        print("  [videos] No new videos to generate")
        return

    print(f"\n  [videos] Running {len(tasks)} lip-sync jobs in parallel...\n")
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Summary
    print(f"\n{'=' * 60}")
    print("VIDEO RESULTS")
    print(f"{'=' * 60}")
    for r in results:
        if isinstance(r, Exception):
            print(f"  ERROR: {r}")
        elif "error" in r:
            print(f"  FAIL: {r['style']}/{r['model']} - {r['error']}")
        else:
            print(f"  OK:   {r['style']}/{r['model']} - {r.get('wall_time', 0):.0f}s - {r['path']}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main():
    step = sys.argv[1] if len(sys.argv) > 1 else "all"

    # Setup fal.ai
    fal_key = os.getenv("FAL_KEY") or os.getenv("FAL_API_KEY")
    if fal_key:
        os.environ["FAL_KEY"] = fal_key
        fal_client.api_key = fal_key

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("MARCH 31 - STYLE COMPARISON PIPELINE")
    print(f"Output: {OUTPUT_DIR}")
    print(f"Step: {step}")
    print("=" * 60)

    if step in ("all", "images"):
        print("\n--- STEP 1: Generate Style Images (Nano Banana Pro) ---")
        await generate_style_images()

    if step in ("all", "audio"):
        print("\n--- STEP 2: Generate Audio (ElevenLabs v3 Hebrew) ---")
        await generate_audio()

    if step in ("all", "videos"):
        print("\n--- STEP 3: Generate Lip-Sync Videos (Aurora + VEED) ---")
        await generate_videos()

    # Final listing
    print(f"\n{'=' * 60}")
    print("PIPELINE COMPLETE")
    print(f"{'=' * 60}")
    for subdir in ["images", "audio", "videos"]:
        d = OUTPUT_DIR / subdir
        if d.exists():
            files = sorted(d.iterdir())
            print(f"\n  {subdir}/")
            for f in files:
                size = f.stat().st_size
                if size > 1024 * 1024:
                    print(f"    {f.name} ({size / 1024 / 1024:.1f} MB)")
                else:
                    print(f"    {f.name} ({size / 1024:.0f} KB)")


if __name__ == "__main__":
    asyncio.run(main())
