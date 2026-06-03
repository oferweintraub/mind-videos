#!/usr/bin/env python3
"""
REGENERATE VIDEOS - Reuse existing text/audio, generate new images for different character.

This script supports partial regeneration:
- Steps 1-2: Generate new images for a NEW character description
- Steps 3-4: SKIP (reuse existing text and audio)
- Steps 5-6: Generate videos and concatenate

Usage:
    # Generate new video with Ashkenazi girl, reusing existing audio
    python scripts/regenerate_videos.py \
        --character "young Ashkenazi Israeli girl, age 22-25, fair skin, straight light brown hair, blue-green eyes" \
        --audio-dir output/fresh_workflow_20260126_231221 \
        --output-dir output/ashkenazi_video

    # Or step by step
    python scripts/regenerate_videos.py --step 1 --character "..." --output-dir ...
    python scripts/regenerate_videos.py --step 2 --output-dir ...
    python scripts/regenerate_videos.py --step 5 --audio-dir ... --output-dir ...
    python scripts/regenerate_videos.py --step 6 --output-dir ...
"""

import asyncio
import os
import sys
import shutil
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

# Default character descriptions
CHARACTER_PRESETS = {
    "ashkenazi": "young Ashkenazi Israeli woman, age 22-25, fair/light skin, straight or wavy light brown hair, blue-green eyes, European Jewish features",
    "sephardic": "young Israeli woman, age 22-25, olive/tan skin (Sephardic/Mizrachi appearance), dark curly hair, brown eyes",
    "ethiopian": "young Ethiopian-Israeli woman, age 22-25, dark brown skin, natural black hair, dark brown eyes, East African features",
    "russian": "young Russian-Israeli woman, age 22-25, very fair skin, straight blonde or light brown hair, light eyes, Slavic features",
    "israeli_man": "Israeli man, age 40, short dark hair, beard, brown eyes, Middle Eastern features",
}

# Voice presets
VOICE_PRESETS = {
    "jessica": "EXAVITQu4vr4xnSDxMaL",  # Female - young, professional
    "daniel": "onwK4e9ZLuTAKqWW03F9",   # Male - steady broadcaster, formal
    "george": "JBFqnCBsd6RMkjVDRZzb",   # Male - warm storyteller
    "brian": "nPczCjzI2devNBz1zQrb",    # Male - deep, resonant
}

# 5 home settings for scene generation
FIVE_HOME_SETTINGS = [
    "sitting on a comfortable sofa in a cozy living room, warm natural lighting from window",
    "standing by a large window in living room, soft daylight illuminating face",
    "seated at a wooden dining table, home kitchen visible in background",
    "standing in a modern kitchen, leaning against counter, natural indoor lighting",
    "close-up in living room, bookshelf visible behind, dramatic but natural lighting",
]


def get_google_client():
    from google import genai
    return genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))


async def step1_generate_reference_images(output_dir: Path, character_desc: str):
    """Generate 3 reference images for the specified character."""
    print("\n" + "=" * 70)
    print("STEP 1: Generate 3 Reference Images (NEW CHARACTER)")
    print("=" * 70)
    print(f"Character: {character_desc}")

    from google.genai import types
    client = get_google_client()
    output_dir.mkdir(parents=True, exist_ok=True)

    ref_prompt = f"""Generate a photorealistic portrait of a {character_desc}.
Neutral expression, looking directly at camera.
Clean background, professional lighting on face.
High quality, sharp focus, no hands near face.
9:16 vertical portrait orientation."""

    print(f"\nGenerating 3 reference options...")
    ref_paths = []

    for i in range(3):
        print(f"  Generating ref_option_{i+1}.png...")
        try:
            response = client.models.generate_content(
                model="nano-banana-pro-preview",
                contents=[ref_prompt],
                config=types.GenerateContentConfig(response_modalities=['image', 'text'])
            )

            image_bytes = None
            if response.candidates:
                for c in response.candidates:
                    if c.content and c.content.parts:
                        for p in c.content.parts:
                            if hasattr(p, 'inline_data') and p.inline_data:
                                image_bytes = p.inline_data.data
                                break

            if image_bytes:
                path = output_dir / f"ref_option_{i+1}.png"
                path.write_bytes(image_bytes)
                ref_paths.append(path)
                print(f"    Saved: {path.name} ({len(image_bytes):,} bytes)")
            else:
                print(f"    WARNING: No image generated")

        except Exception as e:
            print(f"    ERROR: {e}")

    # Auto-select first one
    if ref_paths:
        selected = ref_paths[0]
        selected_copy = output_dir / "selected_reference.png"
        selected_copy.write_bytes(selected.read_bytes())
        print(f"\nAuto-selected: {selected.name} → selected_reference.png")

    # Save character description for reference
    (output_dir / "character.txt").write_text(character_desc, encoding='utf-8')

    return ref_paths


async def step2_generate_scene_images(output_dir: Path, character_desc: str = None):
    """Generate 5 scene images using the reference."""
    print("\n" + "=" * 70)
    print("STEP 2: Generate 5 Scene Images WITH Reference")
    print("=" * 70)

    from google.genai import types
    client = get_google_client()

    ref_path = output_dir / "selected_reference.png"
    if not ref_path.exists():
        print("ERROR: selected_reference.png not found. Run step 1 first.")
        return []

    # Load character description if not provided
    if not character_desc:
        char_file = output_dir / "character.txt"
        if char_file.exists():
            character_desc = char_file.read_text().strip()
        else:
            character_desc = "the woman"

    ref_bytes = ref_path.read_bytes()
    print(f"Using reference: {ref_path} ({len(ref_bytes):,} bytes)")

    print(f"\nGenerating 5 scene variations...")
    scene_paths = []

    for i, setting in enumerate(FIVE_HOME_SETTINGS):
        print(f"\n  Scene {i+1}/5: {setting[:50]}...")

        prompt = f"""Generate a 9:16 vertical image of this SAME woman from the reference image.
Setting: {setting}

CRITICAL REQUIREMENTS:
- MUST use the reference image to maintain EXACT same face, hair texture, skin tone
- The woman must look IDENTICAL to the reference - same person, different setting
- Consistent lighting that matches a home environment
- No hands near face (important for lip-sync)
- Professional photography quality
- No text, no watermarks"""

        try:
            response = client.models.generate_content(
                model="nano-banana-pro-preview",
                contents=[
                    types.Part.from_bytes(data=ref_bytes, mime_type='image/png'),
                    prompt,
                ],
                config=types.GenerateContentConfig(response_modalities=['image', 'text'])
            )

            image_bytes = None
            if response.candidates:
                for c in response.candidates:
                    if c.content and c.content.parts:
                        for p in c.content.parts:
                            if hasattr(p, 'inline_data') and p.inline_data:
                                image_bytes = p.inline_data.data
                                break

            if image_bytes:
                path = output_dir / f"scene_{i+1}.png"
                path.write_bytes(image_bytes)
                scene_paths.append(path)
                print(f"    Saved: {path.name} ({len(image_bytes):,} bytes)")
            else:
                print(f"    WARNING: No image generated")

        except Exception as e:
            print(f"    ERROR: {e}")

    # Auto-select scenes 1, 3, 5 for variety
    if len(scene_paths) >= 5:
        selected_indices = [0, 2, 4]
    else:
        selected_indices = list(range(min(3, len(scene_paths))))

    for seg_idx, scene_idx in enumerate(selected_indices):
        if scene_idx < len(scene_paths):
            src = scene_paths[scene_idx]
            dst = output_dir / f"segment_{seg_idx:02d}_image.png"
            dst.write_bytes(src.read_bytes())
            print(f"  segment_{seg_idx:02d}_image.png ← {src.name}")

    return scene_paths


def copy_audio_files(audio_dir: Path, output_dir: Path):
    """Copy existing audio files from source directory."""
    print("\n" + "=" * 70)
    print("COPYING AUDIO FILES (Reusing existing audio)")
    print("=" * 70)
    print(f"Source: {audio_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    copied = []

    for i in range(3):
        src = audio_dir / f"segment_{i:02d}_audio.mp3"
        dst = output_dir / f"segment_{i:02d}_audio.mp3"

        if src.exists():
            shutil.copy2(src, dst)
            print(f"  Copied: {src.name} ({src.stat().st_size:,} bytes)")
            copied.append(dst)
        else:
            print(f"  WARNING: {src.name} not found in {audio_dir}")

    return copied


# Segment texts and emotions for audio generation
SEGMENT_TEXTS = [
    """תדמיינו גננת שהשאירה את השער פתוח לרווחה. נכנס פורץ, חטף חצי מהגן, והשאיר אחריו הרס וילדים מבוהלים.

ואז? הגננת עומדת מול ההורים ומכריזה בלי למצמץ: "אין בעיה. ברור שכולם אשמים – השומר, העירייה, כולם חוץ ממני. אבל אל תדאגו, אני אחקור בעצמי עד שהכל יתברר".""",

    """עם יד על הלב – הייתם שולחים את הילדים שלכם לגן הזה מחר בבוקר? הייתם סומכים על הגננת הזו?

זה בדיוק, אבל בדיוק, מה שממשלת ישראל עושה לנו. מי שאחראי למחדל הביטחוני הגדול בתולדותינו, רוצה לחקור את עצמו. זה לא רק אבסורד, זו סכנה קיומית.""",

    """אחרי כמעט שנתיים וחצי, אי אפשר לתת לחתול לשמור על השמנת. כדי לתקן, חייבים אמת. ורק ועדת חקירה ממלכתית תביא אותה.""",
]

SEGMENT_EMOTIONS = ["serious", "urgent", "angry"]


async def generate_audio_files(output_dir: Path, voice_id: str):
    """Generate audio files with specified voice."""
    print("\n" + "=" * 70)
    print("GENERATING AUDIO FILES (New voice)")
    print("=" * 70)
    print(f"Voice ID: {voice_id}")

    from src.providers.audio.elevenlabs import ElevenLabsProvider

    output_dir.mkdir(parents=True, exist_ok=True)

    provider = ElevenLabsProvider(
        api_key=os.getenv("ELEVENLABS_API_KEY"),
        voice_id=voice_id,
    )

    audio_results = []

    for i, (text, emotion) in enumerate(zip(SEGMENT_TEXTS, SEGMENT_EMOTIONS)):
        print(f"\n  Segment {i+1} (emotion: {emotion})...")
        audio_path = output_dir / f"segment_{i:02d}_audio.mp3"

        try:
            audio_bytes, duration = await provider.generate_speech(
                text=text,
                emotion=emotion,
                output_path=audio_path,
            )
            audio_results.append((audio_path, duration))
            print(f"    Saved: {audio_path.name} ({duration:.2f}s)")
        except Exception as e:
            print(f"    ERROR: {e}")
            raise

    await provider.close()

    total_duration = sum(d for _, d in audio_results)
    print(f"\nTotal audio duration: {total_duration:.2f}s")

    return audio_results


async def step5_generate_videos(output_dir: Path):
    """Generate videos using images + audio."""
    print("\n" + "=" * 70)
    print("STEP 5: Generate Videos (Fabric 1.0 Lip-Sync)")
    print("=" * 70)

    import fal_client

    api_key = os.getenv("FAL_KEY") or os.getenv("FAL_API_KEY")
    os.environ["FAL_KEY"] = api_key
    fal_client.api_key = api_key

    video_paths = []

    for i in range(3):
        image_path = output_dir / f"segment_{i:02d}_image.png"
        audio_path = output_dir / f"segment_{i:02d}_audio.mp3"
        video_path = output_dir / f"segment_{i:02d}_video.mp4"

        if not image_path.exists():
            print(f"  ERROR: {image_path.name} not found")
            continue
        if not audio_path.exists():
            print(f"  ERROR: {audio_path.name} not found")
            continue

        print(f"\n  Segment {i+1}:")
        print(f"    Image: {image_path.name} (NEW)")
        print(f"    Audio: {audio_path.name} (REUSED)")

        # Upload
        print("    Uploading...")
        image_url = await fal_client.upload_async(image_path.read_bytes(), content_type="image/png")
        audio_url = await fal_client.upload_async(audio_path.read_bytes(), content_type="audio/mpeg")

        # Submit
        print("    Submitting to Fabric 1.0...")
        handle = await fal_client.submit_async("veed/fabric-1.0", arguments={
            "image_url": image_url,
            "audio_url": audio_url,
            "resolution": "720p"
        })
        print(f"    Job ID: {handle.request_id}")

        # Poll
        print("    Processing (this may take several minutes)...")
        for j in range(180):
            status = await fal_client.status_async("veed/fabric-1.0", handle.request_id, with_logs=True)

            if j % 12 == 0 and j > 0:
                print(f"      [{j*5//60}m {(j*5)%60}s] {type(status).__name__}")

            if isinstance(status, fal_client.Completed):
                print(f"    Completed ({j*5}s)")
                break

            if hasattr(status, 'error') and status.error:
                print(f"    FAILED: {status.error}")
                break

            await asyncio.sleep(5)
        else:
            print("    TIMEOUT")
            continue

        # Download
        result = await fal_client.result_async("veed/fabric-1.0", handle.request_id)
        video_url = result.get("video", {}).get("url") if isinstance(result, dict) else result.video.url

        import httpx
        async with httpx.AsyncClient() as http:
            resp = await http.get(video_url)
            video_path.write_bytes(resp.content)
            video_paths.append(video_path)
            print(f"    Saved: {video_path.name} ({len(resp.content):,} bytes)")

    return video_paths


def step6_concatenate(output_dir: Path):
    """Concatenate video segments with direct cuts."""
    print("\n" + "=" * 70)
    print("STEP 6: Concatenate with FFmpeg (Direct Cuts)")
    print("=" * 70)

    import subprocess

    video_paths = [output_dir / f"segment_{i:02d}_video.mp4" for i in range(3)]
    for vp in video_paths:
        if not vp.exists():
            print(f"  ERROR: {vp.name} not found")
            return None

    concat_list = output_dir / "concat_list.txt"
    with open(concat_list, "w") as f:
        for vp in video_paths:
            f.write(f"file '{vp.name}'\n")

    final_path = output_dir / "final_video.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_list),
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        str(final_path)
    ]

    print(f"  Running FFmpeg...")
    result = subprocess.run(cmd, cwd=str(output_dir), capture_output=True, text=True)

    if result.returncode != 0:
        print(f"  ERROR: {result.stderr}")
        return None

    probe_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(final_path)]
    duration_result = subprocess.run(probe_cmd, capture_output=True, text=True)
    duration = float(duration_result.stdout.strip()) if duration_result.returncode == 0 else 0

    print(f"\n  FINAL VIDEO: {final_path}")
    print(f"  Duration: {duration:.2f}s")
    print(f"  Size: {final_path.stat().st_size:,} bytes")

    os.system(f"open '{final_path}'")
    return final_path


async def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Regenerate videos with new character and optional new voice",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Character presets:
  --character ashkenazi    Fair skin, light brown hair, blue-green eyes (female)
  --character sephardic    Olive skin, dark curly hair, brown eyes (female)
  --character ethiopian    Dark skin, natural black hair, East African features (female)
  --character russian      Very fair skin, blonde/light hair, Slavic features (female)
  --character israeli_man  Age 40, short dark hair, beard, brown eyes (male)

Voice presets:
  --voice jessica    Female - young, professional (default for female characters)
  --voice daniel     Male - steady broadcaster, formal (default for male characters)
  --voice george     Male - warm storyteller
  --voice brian      Male - deep, resonant

Example - Female character, reuse existing audio:
  python scripts/regenerate_videos.py \\
      --character ashkenazi \\
      --audio-dir output/fresh_workflow_20260126_231221 \\
      --output-dir output/ashkenazi_video

Example - Male character, generate new audio:
  python scripts/regenerate_videos.py \\
      --character israeli_man \\
      --voice daniel \\
      --output-dir output/israeli_man_video
"""
    )

    parser.add_argument("--step", "-s", choices=["1", "2", "4", "5", "6", "all"], default="all",
                       help="Step to run (1=ref images, 2=scenes, 4=audio, 5=videos, 6=concat)")
    parser.add_argument("--character", "-c", required=False,
                       help="Character description or preset name")
    parser.add_argument("--voice", "-v", required=False,
                       help="Voice preset (jessica, daniel, george, brian) or ElevenLabs voice ID")
    parser.add_argument("--audio-dir", "-a", type=Path,
                       help="Directory containing existing audio files to reuse (skips audio generation)")
    parser.add_argument("--output-dir", "-o", type=Path,
                       help="Output directory for new assets")
    args = parser.parse_args()

    # Resolve character description
    character_desc = args.character
    if character_desc and character_desc.lower() in CHARACTER_PRESETS:
        character_desc = CHARACTER_PRESETS[character_desc.lower()]

    # Resolve voice
    voice_id = args.voice
    if voice_id and voice_id.lower() in VOICE_PRESETS:
        voice_id = VOICE_PRESETS[voice_id.lower()]
    elif not voice_id and not args.audio_dir:
        # Default voice based on character
        if args.character and "man" in args.character.lower():
            voice_id = VOICE_PRESETS["daniel"]
        else:
            voice_id = VOICE_PRESETS["jessica"]

    # Default output directory
    if not args.output_dir:
        char_slug = args.character.split()[0] if args.character else "regen"
        args.output_dir = Path(f"output/{char_slug}_video_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("REGENERATE VIDEOS - Asset Reuse Workflow")
    print("=" * 70)
    print(f"Output: {output_dir}")
    if character_desc:
        print(f"Character: {character_desc[:60]}...")
    if args.audio_dir:
        print(f"Audio source: {args.audio_dir} (reusing)")
    elif voice_id:
        print(f"Voice: {voice_id} (generating new)")

    # Step 1: Generate reference images (requires character)
    if args.step in ["1", "all"]:
        if not character_desc:
            print("\nERROR: --character required for step 1")
            sys.exit(1)
        await step1_generate_reference_images(output_dir, character_desc)

    # Step 2: Generate scene images
    if args.step in ["2", "all"]:
        await step2_generate_scene_images(output_dir, character_desc)

    # Step 4: Generate or copy audio files
    if args.step in ["4", "all"]:
        if args.audio_dir:
            copy_audio_files(args.audio_dir, output_dir)
        elif voice_id:
            await generate_audio_files(output_dir, voice_id)
        else:
            print("\nERROR: --audio-dir or --voice required for step 4")
            sys.exit(1)

    # Copy audio files if specified (for step 5 only mode)
    if args.audio_dir and args.step == "5":
        copy_audio_files(args.audio_dir, output_dir)

    # Step 5: Generate videos
    if args.step in ["5", "all"]:
        await step5_generate_videos(output_dir)

    # Step 6: Concatenate
    if args.step in ["6", "all"]:
        step6_concatenate(output_dir)

    print("\n" + "=" * 70)
    print("REGENERATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
