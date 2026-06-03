#!/usr/bin/env python3
"""
PROPER WORKFLOW - Follow exactly as defined:

1. Generate 3 potential ref images with Nano Banana Pro → select best one
2. Use best ref to generate 5 images at various home settings → select 3 for segments
3. Get full text (45-60s) and split into 3 parts
4. ElevenLabs Jessica: natural/calm → intense/emotional → angry/charged
5. Fabric 1.0 for lip-sync videos (image + audio)
6. FFmpeg concatenate with direct cuts

Run: python scripts/proper_workflow.py [step]
Steps: 1, 2, 3, 4, 5, 6, all
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

# Output directory
OUTPUT_DIR = Path(f"output/proper_workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

# The script text (גן ילדים example - ~54 seconds total)
FULL_TEXT = """תדמיינו גננת שהשאירה את השער פתוח לרווחה. נכנס פורץ, חטף חצי מהגן, והשאיר אחריו הרס וילדים מבוהלים.

ואז? הגננת עומדת מול ההורים ומכריזה בלי למצמץ: "אין בעיה. ברור שכולם אשמים – השומר, העירייה, כולם חוץ ממני. אבל אל תדאגו, אני אחקור בעצמי עד שהכל יתברר".

עם יד על הלב – הייתם שולחים את הילדים שלכם לגן הזה מחר בבוקר? הייתם סומכים על הגננת הזו?

זה בדיוק, אבל בדיוק, מה שממשלת ישראל עושה לנו. מי שאחראי למחדל הביטחוני הגדול בתולדותינו, רוצה לחקור את עצמו. זה לא רק אבסורד, זו סכנה קיומית.

אחרי כמעט שנתיים וחצי, אי אפשר לתת לחתול לשמור על השמנת. כדי לתקן, חייבים אמת. ורק ועדת חקירה ממלכתית תביא אותה."""

# Split into 3 segments
SEGMENT_TEXTS = [
    # Segment 1: Natural and calm
    """תדמיינו גננת שהשאירה את השער פתוח לרווחה. נכנס פורץ, חטף חצי מהגן, והשאיר אחריו הרס וילדים מבוהלים.

ואז? הגננת עומדת מול ההורים ומכריזה בלי למצמץ: "אין בעיה. ברור שכולם אשמים – השומר, העירייה, כולם חוץ ממני. אבל אל תדאגו, אני אחקור בעצמי עד שהכל יתברר".""",

    # Segment 2: Intense and emotional
    """עם יד על הלב – הייתם שולחים את הילדים שלכם לגן הזה מחר בבוקר? הייתם סומכים על הגננת הזו?

זה בדיוק, אבל בדיוק, מה שממשלת ישראל עושה לנו. מי שאחראי למחדל הביטחוני הגדול בתולדותינו, רוצה לחקור את עצמו. זה לא רק אבסורד, זו סכנה קיומית.""",

    # Segment 3: Angry and charged
    """אחרי כמעט שנתיים וחצי, אי אפשר לתת לחתול לשמור על השמנת. כדי לתקן, חייבים אמת. ורק ועדת חקירה ממלכתית תביא אותה.""",
]

# Emotions for each segment
SEGMENT_EMOTIONS = ["serious", "urgent", "angry"]

# 5 home settings for scene generation (step 2)
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


async def step1_generate_reference_images(output_dir: Path):
    """
    STEP 1: Generate 3 potential reference images with Nano Banana Pro.
    Then select the best one based on: face clarity, hair definition, lip-sync friendliness.
    """
    print("\n" + "=" * 70)
    print("STEP 1: Generate 3 Reference Images")
    print("=" * 70)

    from google.genai import types
    client = get_google_client()
    output_dir.mkdir(parents=True, exist_ok=True)

    ref_prompt = """Generate a photorealistic portrait of a young Israeli woman, age 22-25.
She has olive/tan skin (Sephardic/Mizrachi appearance), dark curly hair, brown eyes.
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

    print(f"\n3 reference images generated in: {output_dir}")
    print("ACTION REQUIRED: Review images and select best one.")
    print("Selection criteria: face clarity, hair definition, clear mouth for lip-sync")

    # Auto-select first one for now (can be changed)
    if ref_paths:
        selected = ref_paths[0]
        selected_copy = output_dir / "selected_reference.png"
        selected_copy.write_bytes(selected.read_bytes())
        print(f"\nAuto-selected: {selected.name} (copied to selected_reference.png)")

    return ref_paths


async def step2_generate_scene_images(output_dir: Path):
    """
    STEP 2: Use the selected reference to generate 5 images at various home settings.
    Ensure face, lighting, and character are consistent.
    Then select best 3 for the 3 video segments.
    """
    print("\n" + "=" * 70)
    print("STEP 2: Generate 5 Scene Images WITH Reference")
    print("=" * 70)

    from google.genai import types
    client = get_google_client()

    ref_path = output_dir / "selected_reference.png"
    if not ref_path.exists():
        print("ERROR: selected_reference.png not found. Run step 1 first.")
        return []

    ref_bytes = ref_path.read_bytes()
    print(f"Using reference: {ref_path} ({len(ref_bytes):,} bytes)")

    print(f"\nGenerating 5 scene variations (all using same reference)...")
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

    print(f"\n5 scene images generated.")
    print("ACTION REQUIRED: Review and select best 3 for segments:")
    print("  - Segment 1 (calm): needs neutral/calm expression")
    print("  - Segment 2 (intense): needs concerned/urgent expression")
    print("  - Segment 3 (angry): needs intense/angry expression")

    # Auto-select scenes 1, 3, 5 for variety
    if len(scene_paths) >= 5:
        selected_indices = [0, 2, 4]  # scenes 1, 3, 5
    else:
        selected_indices = [0, 1, 2]

    for seg_idx, scene_idx in enumerate(selected_indices):
        if scene_idx < len(scene_paths):
            src = scene_paths[scene_idx]
            dst = output_dir / f"segment_{seg_idx:02d}_image.png"
            dst.write_bytes(src.read_bytes())
            print(f"  segment_{seg_idx:02d}_image.png <- {src.name}")

    return scene_paths


async def step3_prepare_text(output_dir: Path):
    """
    STEP 3: Get full text (45-60 seconds) and split into 3 parts.
    Save texts for review.
    """
    print("\n" + "=" * 70)
    print("STEP 3: Prepare Text (Split into 3 Segments)")
    print("=" * 70)

    output_dir.mkdir(parents=True, exist_ok=True)
    texts_dir = output_dir / "texts"
    texts_dir.mkdir(exist_ok=True)

    print("\nFull text (~54 seconds):")
    print("-" * 50)
    print(FULL_TEXT)
    print("-" * 50)

    print("\nSplit into 3 segments:")
    for i, (text, emotion) in enumerate(zip(SEGMENT_TEXTS, SEGMENT_EMOTIONS)):
        text_path = texts_dir / f"segment_{i:02d}_{emotion}.txt"
        text_path.write_text(text, encoding='utf-8')
        word_count = len(text.split())
        print(f"\n  Segment {i+1} ({emotion}): ~{word_count} words")
        print(f"  Saved: {text_path.name}")

    print(f"\nTexts saved to: {texts_dir}")
    return SEGMENT_TEXTS


async def step4_generate_audio(output_dir: Path):
    """
    STEP 4: Use ElevenLabs Jessica voice to generate audio.
    Emotions: natural/calm → intense/emotional → angry/charged
    """
    print("\n" + "=" * 70)
    print("STEP 4: Generate Audio (ElevenLabs Jessica)")
    print("=" * 70)

    from src.providers.audio.elevenlabs import ElevenLabsProvider

    provider = ElevenLabsProvider(
        api_key=os.getenv("ELEVENLABS_API_KEY"),
        voice_id="EXAVITQu4vr4xnSDxMaL",  # Jessica
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
    """
    STEP 5: Use Fabric 1.0 to generate videos with lip-sync.
    Uses segment image + audio for each segment.
    """
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
        print(f"    Image: {image_path.name}")
        print(f"    Audio: {audio_path.name}")

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
        for j in range(180):  # 15 min max
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
    """
    STEP 6: Concatenate video segments with FFmpeg using direct cuts.
    No crossfades, no transitions - just direct cuts between segments.
    """
    print("\n" + "=" * 70)
    print("STEP 6: Concatenate with FFmpeg (Direct Cuts)")
    print("=" * 70)

    import subprocess

    # Check all segments exist
    video_paths = [output_dir / f"segment_{i:02d}_video.mp4" for i in range(3)]
    for vp in video_paths:
        if not vp.exists():
            print(f"  ERROR: {vp.name} not found")
            return None

    # Create concat list
    concat_list = output_dir / "concat_list.txt"
    with open(concat_list, "w") as f:
        for vp in video_paths:
            f.write(f"file '{vp.name}'\n")

    # Concatenate
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

    # Get duration
    probe_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(final_path)]
    duration_result = subprocess.run(probe_cmd, capture_output=True, text=True)
    duration = float(duration_result.stdout.strip()) if duration_result.returncode == 0 else 0

    print(f"\n  FINAL VIDEO: {final_path}")
    print(f"  Duration: {duration:.2f}s")
    print(f"  Size: {final_path.stat().st_size:,} bytes")

    # Open video
    os.system(f"open '{final_path}'")

    return final_path


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Proper workflow - follow exactly")
    parser.add_argument("step", nargs="?", default="all",
                       choices=["1", "2", "3", "4", "5", "6", "all"],
                       help="Step to run (1-6 or all)")
    parser.add_argument("--output-dir", "-o", type=Path, help="Output directory")
    args = parser.parse_args()

    output_dir = args.output_dir or OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("PROPER WORKFLOW")
    print("=" * 70)
    print(f"Output: {output_dir}")

    if args.step in ["1", "all"]:
        await step1_generate_reference_images(output_dir)

    if args.step in ["2", "all"]:
        await step2_generate_scene_images(output_dir)

    if args.step in ["3", "all"]:
        await step3_prepare_text(output_dir)

    if args.step in ["4", "all"]:
        await step4_generate_audio(output_dir)

    if args.step in ["5", "all"]:
        await step5_generate_videos(output_dir)

    if args.step in ["6", "all"]:
        step6_concatenate(output_dir)

    print("\n" + "=" * 70)
    print("WORKFLOW COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
