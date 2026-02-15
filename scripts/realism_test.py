#!/usr/bin/env python3
"""
Realism Test: Model Combo Comparison

Generates ~20-second videos (2 scenes each) using different
image+video model combinations. Same Kokoro TTS audio across all.

Combos:
  1. Nano Banana Pro + VEED Fabric    (baseline)
  2. Qwen-Image-2512 + VEED Fabric
  3. Qwen-Image-2512 + Kling v2.1 + Sync Lipsync
  4. FLUX.2 Pro + VEED Fabric
  5. Qwen-Image-2512 + Kling Avatar v2
  6. Qwen Image Max + VEED Fabric     (NEW — ref image support)
  7. Qwen Image Max + Kling 2.6 Pro + Sync Lipsync  (NEW)

Run:
  python scripts/realism_test.py audio      # Generate audio only
  python scripts/realism_test.py combo 6    # Run specific combo
  python scripts/realism_test.py combo 7    # Run specific combo
  python scripts/realism_test.py all        # Run everything
  python scripts/realism_test.py combos     # Run all combos (assumes audio exists)
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

# ─── Configuration ───────────────────────────────────────────────────────────

OUTPUT_DIR = Path("output/realism_test")

SEGMENT_TEXTS = [
    # Segment 1 (~10 sec) — setup
    "Imagine a kindergarten teacher who left the gate wide open. Every parent would demand answers. Every newspaper would run the story. Because when someone is responsible for others, accountability isn't optional.",
    # Segment 2 (~10 sec) — escalation
    "Now ask yourself — why do we accept less from those who govern millions? If we demand accountability from a teacher, surely we must demand it from those in power.",
]

KOKORO_VOICE = "af_heart"  # Grade A, confident

# Image prompts
REF_PROMPT = (
    "Portrait photo of a young Israeli woman, early 30s, olive skin, dark wavy "
    "shoulder-length hair, brown eyes, natural minimal makeup, warm confident "
    "expression, soft studio lighting, neutral background, 9:16 aspect ratio, "
    "photorealistic"
)

SCENE_PROMPTS = [
    (
        "This SAME woman (maintain exact face, hair, features from reference) "
        "sitting on a beige sofa in a modern living room, speaking directly to "
        "camera with a serious concerned expression, soft natural window light, "
        "9:16, photorealistic"
    ),
    (
        "This SAME woman (maintain exact face, hair, features from reference) "
        "standing near a window in the same living room, speaking with passionate "
        "conviction, gesturing slightly with one hand, warm afternoon light, "
        "9:16, photorealistic"
    ),
]

COMBO_NAMES = {
    1: "combo_1_nanobana_veed",
    2: "combo_2_qwen_veed",
    3: "combo_3_qwen_kling_sync",
    4: "combo_4_flux_veed",
    5: "combo_5_qwen_klinglipsync",
    6: "combo_6_qwenmax_veed",
    7: "combo_7_qwenmax_kling_sync",
    8: "combo_8_nanobana_kling3_sync",
    9: "combo_9_cartoonify_veed",
    10: "combo_10_ghiblify_veed",
    11: "combo_11_comic_veed",
}

# ─── Audio Generation ────────────────────────────────────────────────────────

def generate_audio():
    """Generate 2 audio segments using Kokoro TTS (Node.js bridge).

    Flow: Node.js generates WAV → ffmpeg converts to MP3.
    """
    print("\n" + "=" * 70)
    print("AUDIO: Generating with Kokoro TTS")
    print("=" * 70)

    audio_dir = OUTPUT_DIR / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    # Find kokoro_tts.js
    script_dir = Path(__file__).parent
    kokoro_script = script_dir / "kokoro_tts.js"
    if not kokoro_script.exists():
        print(f"ERROR: {kokoro_script} not found")
        sys.exit(1)

    product_videos_dir = Path("/Users/oferweintraub/OferW/product-videos")
    if not (product_videos_dir / "node_modules" / "kokoro-js").exists():
        print(f"ERROR: kokoro-js not found at {product_videos_dir}/node_modules")
        sys.exit(1)

    for i, text in enumerate(SEGMENT_TEXTS):
        mp3_path = audio_dir / f"segment_{i+1:02d}.mp3"
        wav_path = audio_dir / f"segment_{i+1:02d}.wav"

        if mp3_path.exists():
            print(f"  Segment {i+1}: already exists ({mp3_path.name}), skipping")
            continue

        print(f"\n  Segment {i+1}/{len(SEGMENT_TEXTS)}:")
        print(f"    Text: \"{text[:60]}...\"")
        print(f"    Voice: {KOKORO_VOICE}")

        # Step 1: Generate WAV via Kokoro (use absolute paths since cwd differs)
        cmd = [
            "node",
            str(kokoro_script.resolve()),
            "--text", text,
            "--voice", KOKORO_VOICE,
            "--output", str(wav_path.resolve()),
        ]

        result = subprocess.run(
            cmd,
            cwd=str(product_videos_dir),
            capture_output=True,
            text=True,
            timeout=120,
        )

        # Check if WAV was written (exit code may be non-zero due to wasm cleanup)
        if not wav_path.exists():
            print(f"    STDOUT: {result.stdout[:500]}")
            print(f"    STDERR: {result.stderr[:500]}")
            print(f"    ERROR: Kokoro TTS failed - no WAV file produced")
            sys.exit(1)

        wav_size = wav_path.stat().st_size
        print(f"    WAV: {wav_path.name} ({wav_size:,} bytes)")

        # Step 2: Convert WAV → MP3 via ffmpeg
        ffmpeg_result = subprocess.run(
            ["ffmpeg", "-y", "-i", str(wav_path),
             "-codec:a", "libmp3lame", "-b:a", "192k", str(mp3_path)],
            capture_output=True, text=True, timeout=30,
        )
        if ffmpeg_result.returncode != 0:
            print(f"    ERROR: ffmpeg conversion failed: {ffmpeg_result.stderr[-200:]}")
            sys.exit(1)

        # Remove WAV
        wav_path.unlink(missing_ok=True)

        # Get duration
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(mp3_path)],
            capture_output=True, text=True,
        )
        duration = float(probe.stdout.strip()) if probe.returncode == 0 else 0
        print(f"    MP3: {mp3_path.name} ({mp3_path.stat().st_size:,} bytes, {duration:.1f}s)")

    # Verify
    print("\n  Audio files:")
    for i in range(len(SEGMENT_TEXTS)):
        p = audio_dir / f"segment_{i+1:02d}.mp3"
        if not p.exists():
            print(f"  ERROR: {p.name} missing!")
            sys.exit(1)
        size = p.stat().st_size
        print(f"    {p.name}: {size:,} bytes")

    print("\nAudio generation complete.")


# ─── Image Generators ────────────────────────────────────────────────────────

async def generate_images_nanobana(combo_dir: Path) -> list[Path]:
    """Combo 1: Nano Banana Pro via Google AI."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

    # Generate reference
    ref_path = combo_dir / "reference.png"
    if not ref_path.exists():
        print("    Generating reference image...")
        response = client.models.generate_content(
            model="nano-banana-pro-preview",
            contents=[REF_PROMPT],
            config=types.GenerateContentConfig(response_modalities=['image', 'text']),
        )
        image_bytes = _extract_google_image(response)
        ref_path.write_bytes(image_bytes)
        print(f"    Reference: {ref_path.name} ({len(image_bytes):,} bytes)")
    else:
        print(f"    Reference: {ref_path.name} (exists)")

    ref_bytes = ref_path.read_bytes()

    # Generate scenes with reference
    scene_paths = []
    for i, prompt in enumerate(SCENE_PROMPTS):
        scene_path = combo_dir / f"scene_{i+1:02d}.png"
        if scene_path.exists():
            print(f"    Scene {i+1}: {scene_path.name} (exists)")
            scene_paths.append(scene_path)
            continue

        print(f"    Generating scene {i+1}...")
        response = client.models.generate_content(
            model="nano-banana-pro-preview",
            contents=[
                types.Part.from_bytes(data=ref_bytes, mime_type='image/png'),
                prompt,
            ],
            config=types.GenerateContentConfig(response_modalities=['image', 'text']),
        )
        image_bytes = _extract_google_image(response)
        scene_path.write_bytes(image_bytes)
        scene_paths.append(scene_path)
        print(f"    Scene {i+1}: {scene_path.name} ({len(image_bytes):,} bytes)")

    return scene_paths


async def generate_images_qwen(combo_dir: Path) -> list[Path]:
    """Combos 2, 3, 5: Qwen-Image-2512 via fal.ai."""
    import fal_client

    api_key = os.getenv("FAL_KEY") or os.getenv("FAL_API_KEY")
    os.environ["FAL_KEY"] = api_key
    fal_client.api_key = api_key

    # Generate reference (standalone, no ref support)
    ref_path = combo_dir / "reference.png"
    if not ref_path.exists():
        print("    Generating reference image...")
        result = await fal_client.run_async("fal-ai/qwen-image-2512", arguments={
            "prompt": REF_PROMPT,
            "image_size": {"width": 576, "height": 1024},
        })
        image_bytes = await _download_fal_image(result)
        ref_path.write_bytes(image_bytes)
        print(f"    Reference: {ref_path.name} ({len(image_bytes):,} bytes)")
    else:
        print(f"    Reference: {ref_path.name} (exists)")

    # Generate scenes (prompt-based consistency only)
    scene_paths = []
    for i, prompt in enumerate(SCENE_PROMPTS):
        scene_path = combo_dir / f"scene_{i+1:02d}.png"
        if scene_path.exists():
            print(f"    Scene {i+1}: {scene_path.name} (exists)")
            scene_paths.append(scene_path)
            continue

        print(f"    Generating scene {i+1}...")
        result = await fal_client.run_async("fal-ai/qwen-image-2512", arguments={
            "prompt": prompt,
            "image_size": {"width": 576, "height": 1024},
        })
        image_bytes = await _download_fal_image(result)
        scene_path.write_bytes(image_bytes)
        scene_paths.append(scene_path)
        print(f"    Scene {i+1}: {scene_path.name} ({len(image_bytes):,} bytes)")

    return scene_paths


async def generate_images_flux(combo_dir: Path) -> list[Path]:
    """Combo 4: FLUX.2 Pro via fal.ai with reference image support."""
    import fal_client

    api_key = os.getenv("FAL_KEY") or os.getenv("FAL_API_KEY")
    os.environ["FAL_KEY"] = api_key
    fal_client.api_key = api_key

    # Generate reference
    ref_path = combo_dir / "reference.png"
    if not ref_path.exists():
        print("    Generating reference image...")
        result = await fal_client.run_async("fal-ai/flux-2-pro", arguments={
            "prompt": REF_PROMPT,
            "image_size": {"width": 576, "height": 1024},
            "num_images": 1,
            "safety_tolerance": "5",
        })
        image_bytes = await _download_fal_image(result)
        ref_path.write_bytes(image_bytes)
        print(f"    Reference: {ref_path.name} ({len(image_bytes):,} bytes)")
    else:
        print(f"    Reference: {ref_path.name} (exists)")

    ref_bytes = ref_path.read_bytes()

    # Upload reference for image_prompts
    ref_url = await fal_client.upload_async(ref_bytes, content_type="image/png")

    # Generate scenes with reference
    scene_paths = []
    for i, prompt in enumerate(SCENE_PROMPTS):
        scene_path = combo_dir / f"scene_{i+1:02d}.png"
        if scene_path.exists():
            print(f"    Scene {i+1}: {scene_path.name} (exists)")
            scene_paths.append(scene_path)
            continue

        print(f"    Generating scene {i+1}...")
        result = await fal_client.run_async("fal-ai/flux-2-pro", arguments={
            "prompt": prompt,
            "image_size": {"width": 576, "height": 1024},
            "num_images": 1,
            "safety_tolerance": "5",
            "image_prompts": [{"url": ref_url, "weight": 1.0}],
        })
        image_bytes = await _download_fal_image(result)
        scene_path.write_bytes(image_bytes)
        scene_paths.append(scene_path)
        print(f"    Scene {i+1}: {scene_path.name} ({len(image_bytes):,} bytes)")

    return scene_paths


async def generate_images_qwen_max(combo_dir: Path) -> list[Path]:
    """Combos 6, 7: Qwen Image Max via fal.ai WITH reference image support."""
    import fal_client

    api_key = os.getenv("FAL_KEY") or os.getenv("FAL_API_KEY")
    os.environ["FAL_KEY"] = api_key
    fal_client.api_key = api_key

    # Generate reference with text-to-image
    ref_path = combo_dir / "reference.png"
    if not ref_path.exists():
        print("    Generating reference image (Qwen Image Max)...")
        result = await fal_client.run_async("fal-ai/qwen-image-max/text-to-image", arguments={
            "prompt": REF_PROMPT,
            "image_size": "portrait_16_9",
            "num_images": 1,
            "output_format": "png",
        })
        image_bytes = await _download_fal_image(result)
        ref_path.write_bytes(image_bytes)
        print(f"    Reference: {ref_path.name} ({len(image_bytes):,} bytes)")
    else:
        print(f"    Reference: {ref_path.name} (exists)")

    # Upload reference for edit endpoint
    ref_url = await fal_client.upload_async(ref_path.read_bytes(), content_type="image/png")

    # Generate scenes using edit endpoint with reference
    scene_paths = []
    for i, prompt in enumerate(SCENE_PROMPTS):
        scene_path = combo_dir / f"scene_{i+1:02d}.png"
        if scene_path.exists():
            print(f"    Scene {i+1}: {scene_path.name} (exists)")
            scene_paths.append(scene_path)
            continue

        print(f"    Generating scene {i+1} (Qwen Max /edit with reference)...")
        result = await fal_client.run_async("fal-ai/qwen-image-max/edit", arguments={
            "prompt": prompt,
            "image_urls": [ref_url],
            "image_size": "portrait_16_9",
            "num_images": 1,
            "output_format": "png",
        })
        image_bytes = await _download_fal_image(result)
        scene_path.write_bytes(image_bytes)
        scene_paths.append(scene_path)
        print(f"    Scene {i+1}: {scene_path.name} ({len(image_bytes):,} bytes)")

    return scene_paths


# ─── Video Generators ────────────────────────────────────────────────────────

async def generate_videos_veed_fabric(
    combo_dir: Path, scene_paths: list[Path], audio_dir: Path
) -> list[Path]:
    """Combos 1, 2, 4: VEED Fabric 1.0 (image + audio → lip-sync video)."""
    import fal_client

    api_key = os.getenv("FAL_KEY") or os.getenv("FAL_API_KEY")
    os.environ["FAL_KEY"] = api_key
    fal_client.api_key = api_key

    video_paths = []
    for i, scene_path in enumerate(scene_paths):
        video_path = combo_dir / f"video_{i+1:02d}.mp4"
        audio_path = audio_dir / f"segment_{i+1:02d}.mp3"

        if video_path.exists():
            print(f"    Video {i+1}: {video_path.name} (exists)")
            video_paths.append(video_path)
            continue

        print(f"    Video {i+1}: uploading...")
        image_url = await fal_client.upload_async(scene_path.read_bytes(), content_type="image/png")
        audio_url = await fal_client.upload_async(audio_path.read_bytes(), content_type="audio/mpeg")

        print(f"    Video {i+1}: submitting to Fabric 1.0...")
        handle = await fal_client.submit_async("veed/fabric-1.0", arguments={
            "image_url": image_url,
            "audio_url": audio_url,
            "resolution": "480p",
        })
        print(f"    Video {i+1}: job {handle.request_id}")

        video_bytes = await _poll_and_download(
            "veed/fabric-1.0", handle.request_id, f"Video {i+1}"
        )
        video_path.write_bytes(video_bytes)
        video_paths.append(video_path)
        print(f"    Video {i+1}: saved ({len(video_bytes):,} bytes)")

    return video_paths


async def generate_videos_kling_sync(
    combo_dir: Path, scene_paths: list[Path], audio_dir: Path
) -> list[Path]:
    """Combo 3: Kling v2.5 Pro (motion) → Sync Lipsync 2 Pro."""
    import fal_client

    api_key = os.getenv("FAL_KEY") or os.getenv("FAL_API_KEY")
    os.environ["FAL_KEY"] = api_key
    fal_client.api_key = api_key

    video_paths = []
    for i, scene_path in enumerate(scene_paths):
        video_path = combo_dir / f"video_{i+1:02d}.mp4"
        audio_path = audio_dir / f"segment_{i+1:02d}.mp3"
        motion_path = combo_dir / f"motion_{i+1:02d}.mp4"

        if video_path.exists():
            print(f"    Video {i+1}: {video_path.name} (exists)")
            video_paths.append(video_path)
            continue

        # Step A: Kling v2.1 Standard — generate motion video (no audio)
        kling_model = "fal-ai/kling-video/v2.1/standard/image-to-video"
        if not motion_path.exists():
            print(f"    Video {i+1} Step A: Kling v2.1 motion...")
            image_url = await fal_client.upload_async(
                scene_path.read_bytes(), content_type="image/png"
            )

            handle = await fal_client.submit_async(kling_model, arguments={
                "image_url": image_url,
                "prompt": "subtle natural movement, professional presenter speaking to camera, minimal head motion",
                "aspect_ratio": "9:16",
                "duration": "10",
            })
            print(f"    Video {i+1} Step A: job {handle.request_id}")

            motion_bytes = await _poll_and_download(
                kling_model, handle.request_id, f"Video {i+1} motion"
            )
            motion_path.write_bytes(motion_bytes)
            print(f"    Video {i+1} Step A: motion saved ({len(motion_bytes):,} bytes)")
        else:
            print(f"    Video {i+1} Step A: motion exists")

        # Step B: Sync Lipsync 2 Pro — add lip-sync
        print(f"    Video {i+1} Step B: Sync Lipsync...")
        video_url = await fal_client.upload_async(
            motion_path.read_bytes(), content_type="video/mp4"
        )
        audio_url = await fal_client.upload_async(
            audio_path.read_bytes(), content_type="audio/mpeg"
        )

        handle = await fal_client.submit_async("fal-ai/sync-lipsync/v2", arguments={
            "video_url": video_url,
            "audio_url": audio_url,
        })
        print(f"    Video {i+1} Step B: job {handle.request_id}")

        video_bytes = await _poll_and_download(
            "fal-ai/sync-lipsync/v2", handle.request_id, f"Video {i+1} lipsync"
        )
        video_path.write_bytes(video_bytes)
        video_paths.append(video_path)
        print(f"    Video {i+1} Step B: saved ({len(video_bytes):,} bytes)")

    return video_paths


async def generate_videos_kling_avatar(
    combo_dir: Path, scene_paths: list[Path], audio_dir: Path
) -> list[Path]:
    """Combo 5: Kling Avatar v2 (image + audio → talking head, single step)."""
    import fal_client

    api_key = os.getenv("FAL_KEY") or os.getenv("FAL_API_KEY")
    os.environ["FAL_KEY"] = api_key
    fal_client.api_key = api_key

    model_id = "fal-ai/kling-video/ai-avatar/v2/standard"

    video_paths = []
    for i, scene_path in enumerate(scene_paths):
        video_path = combo_dir / f"video_{i+1:02d}.mp4"
        audio_path = audio_dir / f"segment_{i+1:02d}.mp3"

        if video_path.exists():
            print(f"    Video {i+1}: {video_path.name} (exists)")
            video_paths.append(video_path)
            continue

        print(f"    Video {i+1}: uploading...")
        image_url = await fal_client.upload_async(
            scene_path.read_bytes(), content_type="image/png"
        )
        audio_url = await fal_client.upload_async(
            audio_path.read_bytes(), content_type="audio/mpeg"
        )

        print(f"    Video {i+1}: submitting to Kling Avatar v2...")
        handle = await fal_client.submit_async(
            model_id,
            arguments={
                "image_url": image_url,
                "audio_url": audio_url,
            },
        )
        print(f"    Video {i+1}: job {handle.request_id}")

        video_bytes = await _poll_and_download(
            model_id,
            handle.request_id,
            f"Video {i+1}",
        )
        video_path.write_bytes(video_bytes)
        video_paths.append(video_path)
        print(f"    Video {i+1}: saved ({len(video_bytes):,} bytes)")

    return video_paths


async def generate_videos_kling26_sync(
    combo_dir: Path, scene_paths: list[Path], audio_dir: Path
) -> list[Path]:
    """Combo 7: Kling 2.6 Pro (motion) → Sync Lipsync v2."""
    import fal_client

    api_key = os.getenv("FAL_KEY") or os.getenv("FAL_API_KEY")
    os.environ["FAL_KEY"] = api_key
    fal_client.api_key = api_key

    kling_model = "fal-ai/kling-video/v2.6/pro/image-to-video"

    video_paths = []
    for i, scene_path in enumerate(scene_paths):
        video_path = combo_dir / f"video_{i+1:02d}.mp4"
        audio_path = audio_dir / f"segment_{i+1:02d}.mp3"
        motion_path = combo_dir / f"motion_{i+1:02d}.mp4"

        if video_path.exists():
            print(f"    Video {i+1}: {video_path.name} (exists)")
            video_paths.append(video_path)
            continue

        # Step A: Kling 2.6 Pro — generate motion video (no audio)
        if not motion_path.exists():
            print(f"    Video {i+1} Step A: Kling 2.6 Pro motion...")
            image_url = await fal_client.upload_async(
                scene_path.read_bytes(), content_type="image/png"
            )

            handle = await fal_client.submit_async(kling_model, arguments={
                "start_image_url": image_url,
                "prompt": "subtle natural movement, professional presenter speaking to camera, minimal head motion",
                "duration": "10",
            })
            print(f"    Video {i+1} Step A: job {handle.request_id}")

            motion_bytes = await _poll_and_download(
                kling_model, handle.request_id, f"Video {i+1} motion"
            )
            motion_path.write_bytes(motion_bytes)
            print(f"    Video {i+1} Step A: motion saved ({len(motion_bytes):,} bytes)")
        else:
            print(f"    Video {i+1} Step A: motion exists")

        # Step B: Sync Lipsync v2 — add lip-sync with our audio
        print(f"    Video {i+1} Step B: Sync Lipsync v2...")
        video_url = await fal_client.upload_async(
            motion_path.read_bytes(), content_type="video/mp4"
        )
        audio_url = await fal_client.upload_async(
            audio_path.read_bytes(), content_type="audio/mpeg"
        )

        handle = await fal_client.submit_async("fal-ai/sync-lipsync/v2", arguments={
            "video_url": video_url,
            "audio_url": audio_url,
        })
        print(f"    Video {i+1} Step B: job {handle.request_id}")

        video_bytes = await _poll_and_download(
            "fal-ai/sync-lipsync/v2", handle.request_id, f"Video {i+1} lipsync"
        )
        video_path.write_bytes(video_bytes)
        video_paths.append(video_path)
        print(f"    Video {i+1} Step B: saved ({len(video_bytes):,} bytes)")

    return video_paths


async def generate_images_reuse_combo1(combo_dir: Path) -> list[Path]:
    """Combo 8: Reuse Nano Banana Pro images from Combo 1."""
    combo1_dir = OUTPUT_DIR / "combo_1_nanobana_veed"

    # Copy reference
    ref_path = combo_dir / "reference.png"
    if not ref_path.exists():
        src = combo1_dir / "reference.png"
        if not src.exists():
            raise RuntimeError(f"Combo 1 reference not found: {src}. Run combo 1 first.")
        import shutil
        shutil.copy2(src, ref_path)
        print(f"    Reference: copied from combo 1 ({ref_path.stat().st_size:,} bytes)")
    else:
        print(f"    Reference: {ref_path.name} (exists)")

    # Copy scenes
    scene_paths = []
    for i in range(len(SCENE_PROMPTS)):
        scene_path = combo_dir / f"scene_{i+1:02d}.png"
        if not scene_path.exists():
            src = combo1_dir / f"scene_{i+1:02d}.png"
            if not src.exists():
                raise RuntimeError(f"Combo 1 scene not found: {src}. Run combo 1 first.")
            import shutil
            shutil.copy2(src, scene_path)
            print(f"    Scene {i+1}: copied from combo 1 ({scene_path.stat().st_size:,} bytes)")
        else:
            print(f"    Scene {i+1}: {scene_path.name} (exists)")
        scene_paths.append(scene_path)

    return scene_paths


async def generate_images_cartoonify(combo_dir: Path) -> list[Path]:
    """Combo 9: Cartoonify (Pixar/3D) — transform Combo 1 images."""
    import fal_client

    api_key = os.getenv("FAL_KEY") or os.getenv("FAL_API_KEY")
    os.environ["FAL_KEY"] = api_key
    fal_client.api_key = api_key

    combo1_dir = OUTPUT_DIR / "combo_1_nanobana_veed"

    # Cartoonify reference
    ref_path = combo_dir / "reference.png"
    if not ref_path.exists():
        src = combo1_dir / "reference.png"
        if not src.exists():
            raise RuntimeError(f"Combo 1 reference not found: {src}. Run combo 1 first.")
        print("    Cartoonifying reference...")
        image_url = await fal_client.upload_async(src.read_bytes(), content_type="image/png")
        result = await fal_client.run_async("fal-ai/cartoonify", arguments={
            "image_url": image_url,
        })
        image_bytes = await _download_fal_image(result)
        ref_path.write_bytes(image_bytes)
        print(f"    Reference: {ref_path.name} ({len(image_bytes):,} bytes)")
    else:
        print(f"    Reference: {ref_path.name} (exists)")

    # Cartoonify scenes
    scene_paths = []
    for i in range(len(SCENE_PROMPTS)):
        scene_path = combo_dir / f"scene_{i+1:02d}.png"
        if scene_path.exists():
            print(f"    Scene {i+1}: {scene_path.name} (exists)")
            scene_paths.append(scene_path)
            continue

        src = combo1_dir / f"scene_{i+1:02d}.png"
        if not src.exists():
            raise RuntimeError(f"Combo 1 scene not found: {src}. Run combo 1 first.")
        print(f"    Cartoonifying scene {i+1}...")
        image_url = await fal_client.upload_async(src.read_bytes(), content_type="image/png")
        result = await fal_client.run_async("fal-ai/cartoonify", arguments={
            "image_url": image_url,
        })
        image_bytes = await _download_fal_image(result)
        scene_path.write_bytes(image_bytes)
        scene_paths.append(scene_path)
        print(f"    Scene {i+1}: {scene_path.name} ({len(image_bytes):,} bytes)")

    return scene_paths


async def generate_images_ghiblify(combo_dir: Path) -> list[Path]:
    """Combo 10: Ghiblify (Studio Ghibli/anime) — transform Combo 1 images."""
    import fal_client

    api_key = os.getenv("FAL_KEY") or os.getenv("FAL_API_KEY")
    os.environ["FAL_KEY"] = api_key
    fal_client.api_key = api_key

    combo1_dir = OUTPUT_DIR / "combo_1_nanobana_veed"

    # Ghiblify reference
    ref_path = combo_dir / "reference.png"
    if not ref_path.exists():
        src = combo1_dir / "reference.png"
        if not src.exists():
            raise RuntimeError(f"Combo 1 reference not found: {src}. Run combo 1 first.")
        print("    Ghiblifying reference...")
        image_url = await fal_client.upload_async(src.read_bytes(), content_type="image/png")
        result = await fal_client.run_async("fal-ai/ghiblify", arguments={
            "image_url": image_url,
        })
        image_bytes = await _download_fal_image(result)
        ref_path.write_bytes(image_bytes)
        print(f"    Reference: {ref_path.name} ({len(image_bytes):,} bytes)")
    else:
        print(f"    Reference: {ref_path.name} (exists)")

    # Ghiblify scenes
    scene_paths = []
    for i in range(len(SCENE_PROMPTS)):
        scene_path = combo_dir / f"scene_{i+1:02d}.png"
        if scene_path.exists():
            print(f"    Scene {i+1}: {scene_path.name} (exists)")
            scene_paths.append(scene_path)
            continue

        src = combo1_dir / f"scene_{i+1:02d}.png"
        if not src.exists():
            raise RuntimeError(f"Combo 1 scene not found: {src}. Run combo 1 first.")
        print(f"    Ghiblifying scene {i+1}...")
        image_url = await fal_client.upload_async(src.read_bytes(), content_type="image/png")
        result = await fal_client.run_async("fal-ai/ghiblify", arguments={
            "image_url": image_url,
        })
        image_bytes = await _download_fal_image(result)
        scene_path.write_bytes(image_bytes)
        scene_paths.append(scene_path)
        print(f"    Scene {i+1}: {scene_path.name} ({len(image_bytes):,} bytes)")

    return scene_paths


async def generate_images_comic(combo_dir: Path) -> list[Path]:
    """Combo 11: FLUX Digital Comic Art LoRA — text-to-image."""
    import fal_client

    api_key = os.getenv("FAL_KEY") or os.getenv("FAL_API_KEY")
    os.environ["FAL_KEY"] = api_key
    fal_client.api_key = api_key

    # Comic-style prompts (trigger word: d1g1t4l)
    comic_ref_prompt = (
        "d1g1t4l, comic book style portrait of a young Israeli woman, early 30s, "
        "olive skin, dark wavy shoulder-length hair, brown eyes, warm confident "
        "expression, bold ink outlines, dramatic shading, graphic novel aesthetic, "
        "9:16 aspect ratio"
    )
    comic_scene_prompts = [
        (
            "d1g1t4l, comic book panel of this SAME dark-haired woman sitting on a "
            "beige sofa in a modern living room, speaking directly to viewer with a "
            "serious concerned expression, bold ink outlines, dramatic shading, "
            "graphic novel style, 9:16"
        ),
        (
            "d1g1t4l, comic book panel of this SAME dark-haired woman standing near "
            "a window in a living room, speaking with passionate conviction, gesturing "
            "slightly with one hand, warm light, bold outlines, graphic novel style, 9:16"
        ),
    ]

    # Generate reference
    ref_path = combo_dir / "reference.png"
    if not ref_path.exists():
        print("    Generating comic reference...")
        result = await fal_client.run_async(
            "fal-ai/flux-2-lora-gallery/digital-comic-art",
            arguments={
                "prompt": comic_ref_prompt,
                "image_size": {"width": 576, "height": 1024},
                "num_images": 1,
            },
        )
        image_bytes = await _download_fal_image(result)
        ref_path.write_bytes(image_bytes)
        print(f"    Reference: {ref_path.name} ({len(image_bytes):,} bytes)")
    else:
        print(f"    Reference: {ref_path.name} (exists)")

    # Generate scenes
    scene_paths = []
    for i, prompt in enumerate(comic_scene_prompts):
        scene_path = combo_dir / f"scene_{i+1:02d}.png"
        if scene_path.exists():
            print(f"    Scene {i+1}: {scene_path.name} (exists)")
            scene_paths.append(scene_path)
            continue

        print(f"    Generating comic scene {i+1}...")
        result = await fal_client.run_async(
            "fal-ai/flux-2-lora-gallery/digital-comic-art",
            arguments={
                "prompt": prompt,
                "image_size": {"width": 576, "height": 1024},
                "num_images": 1,
            },
        )
        image_bytes = await _download_fal_image(result)
        scene_path.write_bytes(image_bytes)
        scene_paths.append(scene_path)
        print(f"    Scene {i+1}: {scene_path.name} ({len(image_bytes):,} bytes)")

    return scene_paths


async def generate_videos_kling3_sync(
    combo_dir: Path, scene_paths: list[Path], audio_dir: Path
) -> list[Path]:
    """Combo 8: Kling 3.0 Standard (motion) → Sync Lipsync v2."""
    import fal_client

    api_key = os.getenv("FAL_KEY") or os.getenv("FAL_API_KEY")
    os.environ["FAL_KEY"] = api_key
    fal_client.api_key = api_key

    kling_model = "fal-ai/kling-video/v3/standard/image-to-video"

    video_paths = []
    for i, scene_path in enumerate(scene_paths):
        video_path = combo_dir / f"video_{i+1:02d}.mp4"
        audio_path = audio_dir / f"segment_{i+1:02d}.mp3"
        motion_path = combo_dir / f"motion_{i+1:02d}.mp4"

        if video_path.exists():
            print(f"    Video {i+1}: {video_path.name} (exists)")
            video_paths.append(video_path)
            continue

        # Step A: Kling 3.0 Standard — generate motion video (no audio)
        if not motion_path.exists():
            print(f"    Video {i+1} Step A: Kling 3.0 Standard motion...")
            image_url = await fal_client.upload_async(
                scene_path.read_bytes(), content_type="image/png"
            )

            handle = await fal_client.submit_async(kling_model, arguments={
                "start_image_url": image_url,
                "prompt": "subtle natural movement, professional presenter speaking directly to camera, minimal head motion, natural blinking",
                "duration": "10",
                "aspect_ratio": "9:16",
                "generate_audio": False,
            })
            print(f"    Video {i+1} Step A: job {handle.request_id}")

            motion_bytes = await _poll_and_download(
                kling_model, handle.request_id, f"Video {i+1} motion"
            )
            motion_path.write_bytes(motion_bytes)
            print(f"    Video {i+1} Step A: motion saved ({len(motion_bytes):,} bytes)")
        else:
            print(f"    Video {i+1} Step A: motion exists")

        # Step B: Sync Lipsync v2 — add lip-sync with our audio
        print(f"    Video {i+1} Step B: Sync Lipsync v2...")
        video_url = await fal_client.upload_async(
            motion_path.read_bytes(), content_type="video/mp4"
        )
        audio_url = await fal_client.upload_async(
            audio_path.read_bytes(), content_type="audio/mpeg"
        )

        handle = await fal_client.submit_async("fal-ai/sync-lipsync/v2", arguments={
            "video_url": video_url,
            "audio_url": audio_url,
        })
        print(f"    Video {i+1} Step B: job {handle.request_id}")

        video_bytes = await _poll_and_download(
            "fal-ai/sync-lipsync/v2", handle.request_id, f"Video {i+1} lipsync"
        )
        video_path.write_bytes(video_bytes)
        video_paths.append(video_path)
        print(f"    Video {i+1} Step B: saved ({len(video_bytes):,} bytes)")

    return video_paths


# ─── Concatenation ───────────────────────────────────────────────────────────

def concatenate_videos(combo_dir: Path, video_paths: list[Path]) -> Path:
    """Concatenate scene videos into final.mp4 using FFmpeg direct cuts."""
    final_path = combo_dir / "final.mp4"

    if final_path.exists():
        print(f"    Final: {final_path.name} (exists)")
        return final_path

    # Create concat list
    concat_list = combo_dir / "concat_list.txt"
    with open(concat_list, "w") as f:
        for vp in video_paths:
            f.write(f"file '{vp.absolute()}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_list),
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        str(final_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    concat_list.unlink(missing_ok=True)

    if result.returncode != 0:
        print(f"    FFmpeg ERROR: {result.stderr[-200:]}")
        return None

    # Get duration
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(final_path)],
        capture_output=True, text=True,
    )
    duration = float(probe.stdout.strip()) if probe.returncode == 0 else 0
    size = final_path.stat().st_size

    print(f"    Final: {final_path.name} ({duration:.1f}s, {size:,} bytes)")
    return final_path


# ─── Combo Runners ───────────────────────────────────────────────────────────

async def run_combo(combo_num: int):
    """Run a specific combo (1-5)."""
    name = COMBO_NAMES[combo_num]
    combo_dir = OUTPUT_DIR / name
    combo_dir.mkdir(parents=True, exist_ok=True)
    audio_dir = OUTPUT_DIR / "audio"

    # Verify audio exists
    for i in range(len(SEGMENT_TEXTS)):
        ap = audio_dir / f"segment_{i+1:02d}.mp3"
        if not ap.exists():
            print(f"  ERROR: {ap} not found. Run 'python scripts/realism_test.py audio' first.")
            return

    print(f"\n{'=' * 70}")
    print(f"COMBO {combo_num}: {name}")
    print(f"{'=' * 70}")

    start_time = time.time()

    # Generate images
    print(f"\n  [Images]")
    if combo_num == 1:
        scene_paths = await generate_images_nanobana(combo_dir)
    elif combo_num in (2, 3, 5):
        scene_paths = await generate_images_qwen(combo_dir)
    elif combo_num == 4:
        scene_paths = await generate_images_flux(combo_dir)
    elif combo_num in (6, 7):
        scene_paths = await generate_images_qwen_max(combo_dir)
    elif combo_num == 8:
        scene_paths = await generate_images_reuse_combo1(combo_dir)
    elif combo_num == 9:
        scene_paths = await generate_images_cartoonify(combo_dir)
    elif combo_num == 10:
        scene_paths = await generate_images_ghiblify(combo_dir)
    elif combo_num == 11:
        scene_paths = await generate_images_comic(combo_dir)

    if len(scene_paths) != len(SEGMENT_TEXTS):
        print(f"  ERROR: Expected {len(SEGMENT_TEXTS)} scenes, got {len(scene_paths)}")
        return

    # Generate videos
    print(f"\n  [Videos]")
    if combo_num in (1, 2, 4, 6, 9, 10, 11):
        video_paths = await generate_videos_veed_fabric(combo_dir, scene_paths, audio_dir)
    elif combo_num == 3:
        video_paths = await generate_videos_kling_sync(combo_dir, scene_paths, audio_dir)
    elif combo_num == 5:
        video_paths = await generate_videos_kling_avatar(combo_dir, scene_paths, audio_dir)
    elif combo_num == 7:
        video_paths = await generate_videos_kling26_sync(combo_dir, scene_paths, audio_dir)
    elif combo_num == 8:
        video_paths = await generate_videos_kling3_sync(combo_dir, scene_paths, audio_dir)

    if len(video_paths) != len(SEGMENT_TEXTS):
        print(f"  ERROR: Expected {len(SEGMENT_TEXTS)} videos, got {len(video_paths)}")
        return

    # Concatenate
    print(f"\n  [Concatenate]")
    final_path = concatenate_videos(combo_dir, video_paths)

    elapsed = time.time() - start_time
    print(f"\n  Combo {combo_num} complete in {elapsed:.0f}s")

    if final_path:
        # Save metadata
        meta = {
            "combo": combo_num,
            "name": name,
            "elapsed_seconds": round(elapsed, 1),
            "scenes": [str(p) for p in scene_paths],
            "videos": [str(p) for p in video_paths],
            "final": str(final_path),
        }
        (combo_dir / "metadata.json").write_text(json.dumps(meta, indent=2))

    return final_path


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _extract_google_image(response) -> bytes:
    """Extract image bytes from Google AI response."""
    if response.candidates:
        for c in response.candidates:
            if c.content and c.content.parts:
                for p in c.content.parts:
                    if hasattr(p, 'inline_data') and p.inline_data:
                        return p.inline_data.data
    raise RuntimeError("No image in Google AI response")


async def _download_fal_image(result) -> bytes:
    """Download image from fal.ai result."""
    image_url = None
    if isinstance(result, dict):
        images = result.get("images", [])
        if images:
            image_url = images[0].get("url") if isinstance(images[0], dict) else images[0]
        elif result.get("image"):
            img = result["image"]
            image_url = img.get("url") if isinstance(img, dict) else img
        elif result.get("output"):
            image_url = result["output"] if isinstance(result["output"], str) else result["output"].get("url")
    elif hasattr(result, "images") and result.images:
        image_url = result.images[0].url if hasattr(result.images[0], "url") else result.images[0]

    if not image_url:
        raise RuntimeError(f"No image URL in fal.ai response: {result}")

    import httpx
    async with httpx.AsyncClient(timeout=60.0) as http:
        resp = await http.get(image_url)
        resp.raise_for_status()
        return resp.content


async def _poll_and_download(model_id: str, request_id: str, label: str) -> bytes:
    """Poll fal.ai job until complete, then download video."""
    import fal_client
    import httpx

    for tick in range(360):  # 30 min max
        status = await fal_client.status_async(model_id, request_id, with_logs=True)

        if tick > 0 and tick % 12 == 0:
            elapsed_m = tick * 5 // 60
            elapsed_s = (tick * 5) % 60
            print(f"      [{elapsed_m}m{elapsed_s:02d}s] {label}: {type(status).__name__}")

        if isinstance(status, fal_client.Completed):
            break

        if hasattr(status, "error") and status.error:
            raise RuntimeError(f"{label} failed: {status.error}")

        await asyncio.sleep(5)
    else:
        raise RuntimeError(f"{label} timed out after 30 minutes")

    # Get result
    result = await fal_client.result_async(model_id, request_id)

    # Extract video URL
    video_url = None
    if isinstance(result, dict):
        vid = result.get("video", {})
        video_url = vid.get("url") if isinstance(vid, dict) else vid
        if not video_url:
            video_url = result.get("video_url")
        if not video_url:
            # Try output field
            out = result.get("output", {})
            video_url = out.get("url") if isinstance(out, dict) else out
    elif hasattr(result, "video"):
        video_url = result.video.url if hasattr(result.video, "url") else result.video

    if not video_url:
        raise RuntimeError(f"{label}: No video URL in result: {result}")

    # Download
    async with httpx.AsyncClient(timeout=60.0) as http:
        resp = await http.get(video_url)
        resp.raise_for_status()
        return resp.content


# ─── Main ────────────────────────────────────────────────────────────────────

async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Realism test: 5 model combos")
    parser.add_argument("command", choices=["audio", "combo", "combos", "all"],
                        help="What to run")
    parser.add_argument("combo_num", nargs="?", type=int, choices=list(range(1, 12)),
                        help="Combo number (for 'combo' command)")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("REALISM TEST: 5 Videos × 5 Model Combos")
    print(f"Output: {OUTPUT_DIR}")
    print("=" * 70)

    if args.command == "audio":
        generate_audio()

    elif args.command == "combo":
        if not args.combo_num:
            print("ERROR: Specify combo number (1-5)")
            sys.exit(1)
        await run_combo(args.combo_num)

    elif args.command == "combos":
        for n in sorted(COMBO_NAMES.keys()):
            await run_combo(n)

    elif args.command == "all":
        generate_audio()
        for n in sorted(COMBO_NAMES.keys()):
            await run_combo(n)

    print("\n" + "=" * 70)
    print("COMPLETE")
    print("=" * 70)

    # Summary
    print("\nResults:")
    for n in sorted(COMBO_NAMES.keys()):
        name = COMBO_NAMES[n]
        final = OUTPUT_DIR / name / "final.mp4"
        if final.exists():
            size = final.stat().st_size
            print(f"  Combo {n} ({name}): {size:,} bytes")
        else:
            print(f"  Combo {n} ({name}): NOT GENERATED")


if __name__ == "__main__":
    asyncio.run(main())
