#!/usr/bin/env python3
"""
Episode 1: "מה קרה באוקטובר?" — Production Script

Puppet satire featuring Bibi, Kisch, and Silman in a panel discussion.
Pipeline: Expression images → Audio → Lip-sync videos → Reaction stills → Concat

Usage:
    python scripts/episode1_produce.py images    # Generate expression images
    python scripts/episode1_produce.py audio     # Generate audio clips
    python scripts/episode1_produce.py video     # Generate lip-sync videos
    python scripts/episode1_produce.py stills    # Generate reaction/insert stills
    python scripts/episode1_produce.py concat    # Concatenate final video
    python scripts/episode1_produce.py all       # Run full pipeline
    python scripts/episode1_produce.py status    # Show progress
"""

import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

OUTPUT_DIR = Path("output/episode1")
SELECTED_PUPPETS = Path("output/puppet_style_test/selected")

VOICE_IDS = {
    "bibi": "aooUHbQzVbqHLJx3zbYH",
    "kisch": "jUCQwcBAqLbVF54GHPlv",
    "silman": "LtYcxc0xwy3LHnPjIUBt",
}

AUDIO_MODEL = "eleven_v3"

PUPPET_STYLE = (
    "felt puppet, Muppet style, foam and fabric texture, visible stitched seams, "
    "soft round features, slightly oversized head, studio lighting, "
    "professional puppet photography, Spitting Image style political caricature, "
    "3D felt craft puppet"
)

# ============================================================================
# SCENE DEFINITIONS (22 scenes)
# ============================================================================

SCENES = [
    {
        "num": 1, "type": "speak", "char": "bibi",
        "expr": "bibi_neutral",
        "text": "בוקר טוב",
        "emotion": "neutral",
    },
    {
        "num": 2, "type": "speak", "char": "kisch",
        "expr": "kisch_eager",
        "text": "היי ביבי, היי ביבי, אני פה...",
        "emotion": "excited",
    },
    {
        "num": 3, "type": "react", "char": "bibi",
        "expr": "bibi_disgusted",
        "text": "", "duration": 1.5,
    },
    {
        "num": 4, "type": "speak", "char": "bibi",
        "expr": "bibi_confused",
        "text": "בואו נמשיך... אומרים לי שהיה איזה אירוע באוקטובר 2023, אבל אני לא זוכר כלום, ממש נראה לי שלא היה כלום...",
        "emotion": "sarcastic",
    },
    {
        "num": 5, "type": "speak", "char": "silman",
        "expr": "silman_sarcastic",
        "text": "בוא...אירוע, נו באמת.. בוא נגזים... אהה.. מקסימום התרחשות... אולי אפילו סוג של איזה סיטואציה",
        "emotion": "sarcastic",
    },
    {
        "num": 6, "type": "speak", "char": "bibi",
        "expr": "bibi_confused",
        "text": "נו, ומה כבר קרה?",
        "emotion": "neutral",
    },
    {
        "num": 7, "type": "speak", "char": "silman",
        "expr": "silman_naive",
        "text": "היתה סיטואציה והיו כמה אנשים שנקלעו לסיטואציה ..בוא לא נגדיל ... זה לא כמו מאות אלפי אנשים בקפלן שרודפים אַחֲרַי וממש מכים אותי ...",
        "emotion": "cynical",
    },
    {
        "num": 8, "type": "speak", "char": "bibi",
        "expr": "bibi_shocked",
        "text": "מה? היו מאות אלפים בקפלן?",
        "emotion": "excited",
    },
    {
        "num": 9, "type": "speak", "char": "kisch",
        "expr": "kisch_eager",
        "text": "כלום כלום, שניים שלושה שעוד זוכרים את בגין וטעו בניווט...היי אני פה",
        "emotion": "neutral",
    },
    {
        "num": 10, "type": "speak", "char": "bibi",
        "expr": "bibi_confused",
        "text": "אוקיי, מה היתה הסיטואציה? גם קרה שם משהו???",
        "emotion": "neutral",
    },
    {
        "num": "10b", "type": "speak", "char": "bibi",
        "expr": "bibi_phone",
        "text": (
            "כן כן, כמה פעמים צריך להגיד את זה... כן, תעבירו את המזוודות לחמאס... "
            "אני צריך לקבל כל היום פתקים מיחיא?... תעבירו כבר"
        ),
        "emotion": "sarcastic",
    },
    {
        "num": "10c", "type": "speak", "char": "bibi",
        "expr": "bibi_confused",
        "text": "טוב, מה כבר קרה שם?",
        "emotion": "neutral",
    },
    {
        "num": 11, "type": "speak", "char": "kisch",
        "expr": "kisch_proud",
        "text": "היתה סיטואציה וגם היו נפגעים... האמת, כבר הכנתי לכבוד זה ריקוד...רוצה לראות?",
        "emotion": "excited",
    },
    {
        "num": 12, "type": "speak", "char": "bibi",
        "expr": "bibi_outraged",
        "text": (
            "נפגעים? ממש?? כמה היו??? למה לא העירו אותי? "
            "תגידו, זה משהו שינון יכול להריץ עליו איזה קונספירציה ונגמור עם זה?"
        ),
        "emotion": "sarcastic",
    },
    {
        "num": 14, "type": "speak", "char": "silman",
        "expr": "silman_silly",
        "text": "מממ...אולי היו חי מתים...משהו כזה",
        "emotion": "neutral",
    },
    {
        "num": 15, "type": "speak", "char": "bibi",
        "expr": "bibi_confused",
        "text": "חי מתים?? באמת?",
        "emotion": "excited",
    },
    {
        "num": 16, "type": "speak", "char": "kisch",
        "expr": "kisch_serious",
        "text": "אהה... טיפונת יותר... אולי אלף פעמים חי",
        "emotion": "serious",
    },
    {
        "num": 17, "type": "speak", "char": "bibi",
        "expr": "bibi_outraged",
        "text": (
            "מה? למה לא משכו? למה לא דחפו? למה לא הרימו? למה לא הורידו? "
            "איך אני תמיד מקיף את עצמי רק באשמים? מי אחראי לכל זה כי אני ממש אבל ממש לא"
        ),
        "emotion": "angry",
    },
    {
        "num": 18, "type": "speak", "char": "kisch",
        "expr": "kisch_cheerful",
        "text": "זה החבר שלנו, זה הנכס, זה יחיא",
        "emotion": "excited",
    },
    {
        "num": 19, "type": "speak", "char": "bibi",
        "expr": "bibi_scheming",
        "text": (
            "מי?? סינוואר? לא יכול להיות, רק אתמול החלפנו פתקים, "
            "סיכון מחושב הוא כתב לי, "
            "וחשבתי שהוא מתכוון לזה שלחנו לו תיק יד של איב סן לורן במקום הגוצ'י הזה שאשתו ביקשה, "
            "מי היה מאמין? אחרי כל מה שהשקענו בו? "
            "טוב, קודם כל לא היה כלום כי אין כלום, אני לפחות לא זוכר כלום, "
            "ושנית תביאו לי מיד רשימת אשמים אפשרית, "
            "אני חייב לצאת עם סרטון יוטיוב להפיל את האירוע הזה על מישהו"
        ),
        "emotion": "sarcastic",
    },
    {
        "num": 20, "type": "speak", "char": "silman",
        "expr": "silman_cheerful",
        "text": "בוא לא נעשה מזה סיפור גדול... דרמה, כן…דרמה זה כשאני לבד בחדר ומותקפת מכל כיוון... זו אולי במקסימום התרחשות אומללה...",
        "emotion": "cynical",
    },
    {
        "num": 21, "type": "speak", "char": "kisch",
        "expr": "kisch_eager",
        "text": "היי אני פה, להראות את הריקוד שהכנתי?",
        "emotion": "excited",
    },
    {
        "num": 22, "type": "speak", "char": "bibi",
        "expr": "bibi_scheming",
        "text": (
            "לא, די, מספיק להיום... אני הולך לצלם סרטון … הנה, כבר יש לי סיסמא: "
            "ביחצ ננצח! אני אקרא לכולם לשלב ידיים, להיות באחדות הנהדרת שאני מטיף לה יום ולילה "
            "ועל אף האירועים ואי נעימות מסויימת להגיע לדרום..."
            "כי הדרום כולו אדום עכשיו וממש חבל לפספס... "
            "מחר נמשיך לחפש אשמים בארוע שלא קרה... משוחררים"
        ),
        "emotion": "serious",
    },
]

# ============================================================================
# EXPRESSION IMAGE PROMPTS
# ============================================================================

# Character base descriptions (from puppet_round3.py)
BIBI_BASE = (
    "an older heavy-set Israeli male politician: gray-white receding hair swept back, "
    "heavy jowls, double chin, prominent bulbous nose, "
    "wearing dark navy suit with white shirt and dark tie"
)
KISCH_BASE = (
    "a stocky heavy-set Israeli male politician: short gray-peppered hair receding at temples, "
    "square jaw, broad face, thick neck, rectangular glasses, dark suit with gold tie"
)
SILMAN_BASE = (
    "a slender Israeli woman politician with very curly light-brown hair pulled up in a bun "
    "with a black fabric headband, thin elongated face, prominent cheekbones, "
    "round black earrings, dark blouse"
)

REFERENCE_IMAGES = {
    "bibi": OUTPUT_DIR / "images" / "bibi_neutral.png",
    "kisch": OUTPUT_DIR / "images" / "kisch_cheerful.png",
    "silman": OUTPUT_DIR / "images" / "silman_reference.png",
}

EXPRESSIONS = {
    # Bibi — all variants use bibi_neutral as reference
    "bibi_neutral": {"source": "existing", "file": "bibi.png"},
    "bibi_confused": {
        "source": "generate_with_ref", "char": "bibi",
        "prompt": (
            "Generate a 9:16 portrait of this EXACT SAME felt Muppet puppet. "
            "Change ONLY the expression to: CONFUSED and PUZZLED — head tilted slightly, "
            "eyebrows raised, mouth slightly open in bewilderment, looking innocent and clueless. "
            "Keep everything else identical: same puppet, same clothing, same face shape, same colors."
        ),
    },
    "bibi_shocked": {
        "source": "generate_with_ref", "char": "bibi",
        "prompt": (
            "Generate a 9:16 portrait of this EXACT SAME felt Muppet puppet. "
            "Change ONLY the expression to: SHOCKED and SURPRISED — eyes wide open, mouth gaping, "
            "eyebrows raised high, jaw dropped, hearing something truly unbelievable. "
            "Keep everything else identical: same puppet, same clothing, same face shape, same colors."
        ),
    },
    "bibi_disgusted": {
        "source": "generate_with_ref", "char": "bibi",
        "prompt": (
            "Generate a 9:16 portrait of this EXACT SAME felt Muppet puppet. "
            "Change ONLY the expression to: DISGUSTED and CONTEMPTUOUS — looking sideways with narrowed eyes, "
            "upper lip curled in disdain, annoyed contemptuous look. "
            "Keep everything else identical: same puppet, same clothing, same face shape, same colors."
        ),
    },
    "bibi_phone": {
        "source": "generate_with_ref", "char": "bibi",
        "prompt": (
            "Generate a 9:16 portrait of this EXACT SAME felt Muppet puppet. "
            "He is HOLDING AN OLD TELEPHONE RECEIVER to his ear with one hand, "
            "scheming conniving expression, whispering conspiratorially into the phone. "
            "Keep everything else identical: same puppet, same clothing, same face shape, same colors."
        ),
    },
    "bibi_outraged": {
        "source": "generate_with_ref", "char": "bibi",
        "prompt": (
            "Generate a 9:16 portrait of this EXACT SAME felt Muppet puppet. "
            "Change ONLY the expression to: OUTRAGED and INDIGNANT — pointing finger accusingly, "
            "face flushed with anger, mouth open mid-shout, furiously deflecting blame. "
            "Keep everything else identical: same puppet, same clothing, same face shape, same colors."
        ),
    },
    "bibi_scheming": {
        "source": "generate_with_ref", "char": "bibi",
        "prompt": (
            "Generate a 9:16 portrait of this EXACT SAME felt Muppet puppet. "
            "Change ONLY the expression to: SCHEMING and PLOTTING — leaning forward, evil cunning grin, "
            "narrowed calculating eyes, rubbing hands together like a villain. "
            "Keep everything else identical: same puppet, same clothing, same face shape, same colors."
        ),
    },
    # Kisch — all variants use kisch_cheerful as reference
    "kisch_cheerful": {"source": "existing", "file": "kisch.png"},
    "kisch_eager": {
        "source": "generate_with_ref", "char": "kisch",
        "prompt": (
            "Generate a 9:16 portrait of this EXACT SAME felt Muppet puppet. "
            "Change ONLY the expression to: DESPERATELY EAGER with a small SNEAKY SMILE — "
            "waving hand frantically, wide eager eyes behind glasses, subtle sly latent grin. "
            "Keep everything else identical: same puppet, same clothing, same face shape, same colors."
        ),
    },
    "kisch_proud": {
        "source": "generate_with_ref", "char": "kisch",
        "prompt": (
            "Generate a 9:16 portrait of this EXACT SAME felt Muppet puppet. "
            "Change ONLY the expression to: PUFFED UP with PRIDE — chest out, "
            "subtle sly sneaky grin, looking very pleased with himself. "
            "Keep everything else identical: same puppet, same clothing, same face shape, same colors."
        ),
    },
    "kisch_serious": {
        "source": "generate_with_ref", "char": "kisch",
        "prompt": (
            "Generate a 9:16 portrait of this EXACT SAME felt Muppet puppet. "
            "Change ONLY the expression to: SERIOUS and DEADPAN — no smile, straight face, "
            "matter-of-fact expression, neutral serious look. "
            "Keep everything else identical: same puppet, same clothing, same face shape, same colors."
        ),
    },
    # Silman — all variants use silman_reference
    "silman_sarcastic": {
        "source": "generate_with_ref", "char": "silman",
        "prompt": (
            "Generate a 9:16 portrait of this EXACT SAME felt Muppet puppet. "
            "Change ONLY the expression to: SARCASTIC and DISMISSIVE — rolling eyes, "
            "one corner of mouth raised, hand waving dismissively, condescending look. "
            "Keep everything else identical: same puppet, same clothing, same face shape, same hair, same colors."
        ),
    },
    "silman_victim": {
        "source": "generate_with_ref", "char": "silman",
        "prompt": (
            "Generate a 9:16 portrait of this EXACT SAME felt Muppet puppet. "
            "Change ONLY the expression to: DEFENSIVE VICTIM — fists raised, upset pouting face, "
            "looking persecuted and attacked from all sides. "
            "Keep everything else identical: same puppet, same clothing, same face shape, same hair, same colors."
        ),
    },
    "silman_naive": {
        "source": "generate_with_ref", "char": "silman",
        "prompt": (
            "Generate a 9:16 portrait of this EXACT SAME felt Muppet puppet. "
            "Change ONLY the expression to: NAIVE and INNOCENT — wide doe eyes, "
            "slightly open mouth, head tilted, looking sweetly clueless. "
            "Keep everything else identical: same puppet, same clothing, same face shape, same hair, same colors."
        ),
    },
    "silman_cheerful": {
        "source": "generate_with_ref", "char": "silman",
        "prompt": (
            "Generate a 9:16 portrait of this EXACT SAME felt Muppet puppet. "
            "Change ONLY the expression to: CHEERFUL and BUBBLY — big bright smile, "
            "happy sparkling eyes, looking delighted and carefree. "
            "Keep everything else identical: same puppet, same clothing, same face shape, same hair, same colors."
        ),
    },
    "silman_silly": {
        "source": "generate_with_ref", "char": "silman",
        "prompt": (
            "Generate a 9:16 portrait of this EXACT SAME felt Muppet puppet. "
            "Change ONLY the expression to: SILLY and GOOFY — big dorky smile, "
            "eyes slightly crossed, playful ridiculous expression. "
            "Keep everything else identical: same puppet, same clothing, same face shape, same hair, same colors."
        ),
    },
}


# ============================================================================
# HELPERS
# ============================================================================

def get_image_path(expr_name: str) -> Path:
    """Get path to an expression image in the episode images dir."""
    return OUTPUT_DIR / "images" / f"{expr_name}.png"


def _scene_id(scene: dict) -> str:
    """Get a formatted scene ID string (handles int and str scene nums)."""
    num = scene["num"]
    if isinstance(num, int):
        return f"{num:02d}"
    return str(num)


def get_audio_path(scene: dict) -> Path:
    """Get path to a scene's audio file."""
    return OUTPUT_DIR / "audio" / f"scene_{_scene_id(scene)}_{scene['char']}.mp3"


def get_video_path(scene: dict) -> Path:
    """Get path to a scene's video file."""
    suffix = "_still" if scene["type"] != "speak" else ""
    return OUTPUT_DIR / "video" / f"scene_{_scene_id(scene)}_{scene['char']}{suffix}.mp4"


# ============================================================================
# STEP 1: GENERATE EXPRESSION IMAGES
# ============================================================================

async def step_images():
    """Generate expression variant images using Nano Banana Pro (text-only)."""
    print("\n" + "=" * 70)
    print("STEP 1: Generate Expression Images")
    print("=" * 70)

    from google import genai
    from google.genai import types

    images_dir = OUTPUT_DIR / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    generated = 0
    skipped = 0

    for name, info in EXPRESSIONS.items():
        path = images_dir / f"{name}.png"

        if path.exists():
            print(f"  {name}: exists, skipping")
            skipped += 1
            continue

        if info["source"] == "existing":
            src = SELECTED_PUPPETS / info["file"]
            if src.exists():
                shutil.copy(src, path)
                print(f"  {name}: copied from selected/{info['file']}")
                skipped += 1
            else:
                print(f"  {name}: ERROR — {src} not found")
            continue

        if info["source"] == "user_provided":
            print(f"  {name}: USER MUST PROVIDE → {path}")
            print(f"           Place the image file at: {path.absolute()}")
            continue

        # Generate with Nano Banana Pro (with reference or text-only)
        use_ref = info["source"] == "generate_with_ref"
        ref_bytes = None
        if use_ref:
            ref_path = REFERENCE_IMAGES[info["char"]]
            if not ref_path.exists():
                print(f"  {name}: ERROR — reference image missing: {ref_path}")
                continue
            ref_bytes = ref_path.read_bytes()

        max_retries = 3
        for attempt in range(max_retries):
            if attempt > 0:
                wait = 10 * attempt
                print(f"  {name}: retrying in {wait}s (attempt {attempt + 1}/{max_retries})...")
                await asyncio.sleep(wait)
            else:
                print(f"  {name}: generating{' (with reference)' if use_ref else ''}...")

            try:
                contents = []
                if ref_bytes:
                    contents.append(types.Part.from_bytes(data=ref_bytes, mime_type='image/png'))
                contents.append(info["prompt"])

                response = client.models.generate_content(
                    model="nano-banana-pro-preview",
                    contents=contents,
                    config=types.GenerateContentConfig(response_modalities=['image', 'text']),
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
                    path.write_bytes(image_bytes)
                    generated += 1
                    print(f"  {name}: saved ({len(image_bytes):,} bytes)")
                    break
                else:
                    print(f"  {name}: no image in response")

            except Exception as e:
                err = str(e)
                if "503" in err and attempt < max_retries - 1:
                    print(f"  {name}: 503 (model busy)")
                    continue
                print(f"  {name}: ERROR — {e}")
                break

    print(f"\nImages: {generated} generated, {skipped} reused/skipped")
    print(f"Check: {images_dir}/")


# ============================================================================
# STEP 2: GENERATE AUDIO
# ============================================================================

async def step_audio():
    """Generate audio clips for all speaking scenes using ElevenLabs cloned voices."""
    print("\n" + "=" * 70)
    print("STEP 2: Generate Audio (ElevenLabs Cloned Voices)")
    print("=" * 70)

    from src.providers.audio.elevenlabs import ElevenLabsProvider

    audio_dir = OUTPUT_DIR / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    provider = ElevenLabsProvider(
        api_key=os.getenv("ELEVENLABS_API_KEY"),
        model_id=AUDIO_MODEL,
        language_code="he",
    )

    speaking_scenes = [s for s in SCENES if s["type"] == "speak"]
    total_chars = sum(len(s["text"]) for s in speaking_scenes)
    print(f"  {len(speaking_scenes)} speaking scenes, ~{total_chars} characters total")

    generated = 0
    skipped = 0
    total_duration = 0.0
    newly_generated = []  # Track which scenes were freshly generated (for tempo)

    for scene in speaking_scenes:
        audio_path = get_audio_path(scene)
        num = scene["num"]

        if audio_path.exists():
            print(f"  Scene {_scene_id(scene):>4s} ({scene['char']:6s}): exists, skipping")
            skipped += 1
            continue

        print(f"  Scene {_scene_id(scene):>4s} ({scene['char']:6s}, {scene['emotion']:9s}): generating...")
        try:
            audio_bytes, duration = await provider.generate_speech(
                text=scene["text"],
                voice_id=VOICE_IDS[scene["char"]],
                emotion=scene["emotion"],
                output_path=audio_path,
            )
            generated += 1
            total_duration += duration
            newly_generated.append(scene)
            print(f"           saved ({duration:.1f}s, {len(audio_bytes):,} bytes)")

        except Exception as e:
            print(f"           ERROR — {e}")

    await provider.close()

    print(f"\nAudio: {generated} generated, {skipped} skipped")
    print(f"Total new audio duration: {total_duration:.1f}s")
    print(f"Characters used: ~{total_chars}")

    # Post-process: speed up ONLY newly generated audio
    # Bibi scenes: 1.20x, long scenes (19, 22): 1.25x
    if newly_generated:
        print(f"\n  Applying tempo adjustments to {len(newly_generated)} new files...")
        for scene in newly_generated:
            audio_path = get_audio_path(scene)
            if not audio_path.exists():
                continue

            num = scene["num"]
            speed = 1.0
            if scene["char"] == "bibi":
                speed = 1.20
            if num in (19, 22):
                speed = 1.25  # Extra fast for long monologues

            if speed != 1.0:
                tmp_path = audio_path.with_suffix(".tmp.mp3")
                cmd = [
                    "ffmpeg", "-y", "-i", str(audio_path),
                    "-filter:a", f"atempo={speed}",
                    "-vn", str(tmp_path),
                ]
                result = subprocess.run(cmd, capture_output=True)
                if result.returncode == 0:
                    tmp_path.rename(audio_path)
                    print(f"  Scene {_scene_id(scene):>4s}: {speed}x tempo applied")
                else:
                    tmp_path.unlink(missing_ok=True)
                    print(f"  Scene {_scene_id(scene):>4s}: tempo FAILED — {result.stderr.decode()[:100]}")
    else:
        print("\n  No new audio files — skipping tempo adjustments")


# ============================================================================
# STEP 3: GENERATE LIP-SYNC VIDEOS
# ============================================================================

async def step_video():
    """Generate lip-sync videos for all speaking scenes via VEED Fabric 1.0.

    Submits all jobs first, then polls them in parallel for efficiency.
    """
    print("\n" + "=" * 70)
    print("STEP 3: Generate Lip-Sync Videos (VEED Fabric 1.0)")
    print("=" * 70)

    import fal_client
    import httpx

    api_key = os.getenv("FAL_KEY") or os.getenv("FAL_API_KEY")
    os.environ["FAL_KEY"] = api_key
    fal_client.api_key = api_key

    video_dir = OUTPUT_DIR / "video"
    video_dir.mkdir(parents=True, exist_ok=True)

    speaking_scenes = [s for s in SCENES if s["type"] == "speak"]

    # Phase 1: Upload and submit all pending jobs
    jobs = {}  # num → {"handle", "video_path", "done"}
    for scene in speaking_scenes:
        num = scene["num"]
        video_path = get_video_path(scene)

        sid = _scene_id(scene)
        if video_path.exists():
            print(f"  Scene {sid:>4s}: exists, skipping")
            continue

        image_path = get_image_path(scene["expr"])
        audio_path = get_audio_path(scene)

        if not image_path.exists():
            print(f"  Scene {sid:>4s}: SKIP — image missing ({image_path.name})")
            continue
        if not audio_path.exists():
            print(f"  Scene {sid:>4s}: SKIP — audio missing ({audio_path.name})")
            continue

        print(f"  Scene {sid:>4s}: uploading...")
        image_url = await fal_client.upload_async(
            image_path.read_bytes(), content_type="image/png"
        )
        audio_url = await fal_client.upload_async(
            audio_path.read_bytes(), content_type="audio/mpeg"
        )

        print(f"  Scene {sid:>4s}: submitting to Fabric 1.0...")
        handle = await fal_client.submit_async("veed/fabric-1.0", arguments={
            "image_url": image_url,
            "audio_url": audio_url,
            "resolution": "720p",
        })

        jobs[sid] = {
            "handle": handle,
            "video_path": video_path,
            "char": scene["char"],
            "done": False,
            "failed": False,
        }
        print(f"  Scene {sid:>4s}: submitted (job {handle.request_id})")

    if not jobs:
        print("\n  All videos exist or no jobs to submit.")
        return

    # Phase 2: Poll all jobs in parallel
    print(f"\n  Polling {len(jobs)} jobs (this will take several minutes)...")
    start_time = time.time()
    last_status_print = 0

    while any(not j["done"] for j in jobs.values()):
        elapsed = time.time() - start_time

        for sid, job in jobs.items():
            if job["done"]:
                continue

            try:
                status = await fal_client.status_async(
                    "veed/fabric-1.0", job["handle"].request_id, with_logs=True
                )

                if isinstance(status, fal_client.Completed):
                    result = await fal_client.result_async(
                        "veed/fabric-1.0", job["handle"].request_id
                    )
                    video_url = (
                        result.get("video", {}).get("url")
                        if isinstance(result, dict)
                        else result.video.url
                    )

                    async with httpx.AsyncClient(timeout=60.0) as http:
                        resp = await http.get(video_url)
                        job["video_path"].write_bytes(resp.content)

                    job["done"] = True
                    print(f"  Scene {sid:>4s}: DONE ({len(resp.content):,} bytes, {elapsed:.0f}s)")

                elif hasattr(status, 'error') and status.error:
                    job["done"] = True
                    job["failed"] = True
                    print(f"  Scene {sid:>4s}: FAILED — {status.error}")

            except Exception as e:
                print(f"  Scene {sid:>4s}: poll error — {e}")

        pending = sum(1 for j in jobs.values() if not j["done"])
        if pending > 0:
            # Print status every 30 seconds
            if elapsed - last_status_print >= 30:
                last_status_print = elapsed
                mins = int(elapsed) // 60
                secs = int(elapsed) % 60
                print(f"    [{mins}m{secs:02d}s] {pending} jobs still processing...")
            await asyncio.sleep(5)

    elapsed = time.time() - start_time
    done_count = sum(1 for j in jobs.values() if not j["failed"])
    failed_count = sum(1 for j in jobs.values() if j["failed"])
    print(f"\n  {done_count} succeeded, {failed_count} failed ({elapsed:.0f}s total)")


# ============================================================================
# STEP 4: GENERATE REACTION/INSERT STILLS
# ============================================================================

async def step_stills():
    """Generate still videos for reaction shots and inserts (image → silent video)."""
    print("\n" + "=" * 70)
    print("STEP 4: Generate Reaction/Insert Stills")
    print("=" * 70)

    from src.utils.ffmpeg import run_ffmpeg

    video_dir = OUTPUT_DIR / "video"
    video_dir.mkdir(parents=True, exist_ok=True)

    non_speaking = [s for s in SCENES if s["type"] != "speak"]
    generated = 0

    for scene in non_speaking:
        sid = _scene_id(scene)
        video_path = get_video_path(scene)
        duration = scene.get("duration", 1.5)

        if video_path.exists():
            print(f"  Scene {sid:>4s}: exists, skipping")
            continue

        image_path = get_image_path(scene["expr"])
        if not image_path.exists():
            print(f"  Scene {sid:>4s}: SKIP — image missing ({image_path.name})")
            continue

        print(f"  Scene {sid:>4s}: generating {duration}s still from {image_path.name}...")

        # Create video from still image with silent audio
        args = [
            "-loop", "1",
            "-i", str(image_path),
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-c:v", "libx264", "-t", str(duration),
            "-pix_fmt", "yuv420p", "-r", "25",
            "-vf", "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2:color=black",
            "-c:a", "aac", "-shortest",
            str(video_path),
        ]

        try:
            await run_ffmpeg(args)
            generated += 1
            print(f"  Scene {sid:>4s}: saved ({video_path.stat().st_size:,} bytes)")
        except Exception as e:
            print(f"  Scene {sid:>4s}: ERROR — {e}")

    print(f"\n  {generated} stills generated")


# ============================================================================
# STEP 5: CONCATENATE ALL SCENES
# ============================================================================

async def step_concat():
    """Concatenate all scene videos into the final episode video."""
    print("\n" + "=" * 70)
    print("STEP 5: Concatenate Final Video")
    print("=" * 70)

    from src.utils.ffmpeg import run_ffmpeg, get_video_info

    final_path = OUTPUT_DIR / "final.mp4"

    # Collect all scene videos in order
    video_paths = []
    missing = []
    for scene in SCENES:
        path = get_video_path(scene)
        if path.exists():
            video_paths.append(path)
        else:
            missing.append(scene["num"])

    if missing:
        print(f"  WARNING: Missing scenes: {missing}")
        print(f"  Concatenating {len(video_paths)}/{len(SCENES)} available scenes")
    else:
        print(f"  All {len(SCENES)} scenes present")

    if not video_paths:
        print("  ERROR: No videos found. Run previous steps first.")
        return

    # Use ffmpeg concat filter for robustness (handles format differences)
    n = len(video_paths)
    args = []
    for p in video_paths:
        args.extend(["-i", str(p)])

    # Build filter: normalize resolution/fps/audio, then concat
    filter_parts = []
    for i in range(n):
        filter_parts.append(
            f"[{i}:v]scale=720:1280:force_original_aspect_ratio=decrease,"
            f"pad=720:1280:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps=25[v{i}]"
        )
        filter_parts.append(
            f"[{i}:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[a{i}]"
        )

    concat_inputs = "".join(f"[v{i}][a{i}]" for i in range(n))
    filter_parts.append(f"{concat_inputs}concat=n={n}:v=1:a=1[outv][outa]")

    filter_complex = ";".join(filter_parts)

    args.extend([
        "-filter_complex", filter_complex,
        "-map", "[outv]", "-map", "[outa]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        str(final_path),
    ])

    print(f"  Concatenating {n} scenes...")
    await run_ffmpeg(args, timeout=600)

    # Get final video info
    info = await get_video_info(final_path)
    duration = info.get("duration", 0)

    print(f"\n  FINAL VIDEO: {final_path}")
    print(f"  Duration: {duration:.1f}s ({duration/60:.1f}m)")
    print(f"  Size: {final_path.stat().st_size / 1024 / 1024:.1f}MB")

    # Save metadata
    metadata = {
        "scenes": len(SCENES),
        "scenes_included": len(video_paths),
        "scenes_missing": missing,
        "duration": duration,
        "characters": {
            "bibi": sum(1 for s in SCENES if s["char"] == "bibi"),
            "kisch": sum(1 for s in SCENES if s["char"] == "kisch"),
            "silman": sum(1 for s in SCENES if s["char"] == "silman"),
        },
        "voice_ids": VOICE_IDS,
        "audio_model": AUDIO_MODEL,
    }
    metadata_path = OUTPUT_DIR / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False))
    print(f"  Metadata: {metadata_path}")


# ============================================================================
# STATUS
# ============================================================================

def show_status():
    """Show progress of all production steps."""
    print("\n" + "=" * 70)
    print("Episode 1 — Production Status")
    print("=" * 70)

    images_dir = OUTPUT_DIR / "images"
    audio_dir = OUTPUT_DIR / "audio"
    video_dir = OUTPUT_DIR / "video"

    # Unique expressions needed
    needed_exprs = set(s["expr"] for s in SCENES)
    have_images = sum(1 for e in needed_exprs if (images_dir / f"{e}.png").exists())
    print(f"\n  Images:  {have_images}/{len(needed_exprs)} expression variants")
    for name in sorted(needed_exprs):
        status = "OK" if (images_dir / f"{name}.png").exists() else "MISSING"
        print(f"    {name:25s} [{status}]")

    # Audio
    speaking = [s for s in SCENES if s["type"] == "speak"]
    have_audio = sum(1 for s in speaking if get_audio_path(s).exists())
    print(f"\n  Audio:   {have_audio}/{len(speaking)} speaking scenes")

    # Videos (lip-sync)
    have_video = sum(1 for s in speaking if get_video_path(s).exists())
    print(f"  Videos:  {have_video}/{len(speaking)} lip-sync videos")

    # Stills
    non_speaking = [s for s in SCENES if s["type"] != "speak"]
    have_stills = sum(1 for s in non_speaking if get_video_path(s).exists())
    print(f"  Stills:  {have_stills}/{len(non_speaking)} reaction/insert stills")

    # Final
    final = OUTPUT_DIR / "final.mp4"
    if final.exists():
        size_mb = final.stat().st_size / 1024 / 1024
        print(f"\n  Final:   EXISTS ({size_mb:.1f}MB)")
    else:
        print(f"\n  Final:   NOT YET")

    # Character count estimate
    total_chars = sum(len(s["text"]) for s in speaking)
    print(f"\n  Total audio characters: ~{total_chars}")
    print(f"  ElevenLabs credits: 37,925 available")


# ============================================================================
# MAIN
# ============================================================================

async def main():
    import argparse
    parser = argparse.ArgumentParser(
        description='Episode 1: "מה קרה באוקטובר?" — Production',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "step",
        choices=["images", "audio", "video", "stills", "concat", "all", "status"],
        help="Production step to run",
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print('Episode 1: "מה קרה באוקטובר?"')
    print(f"Output: {OUTPUT_DIR}")
    print("=" * 70)

    if args.step == "status":
        show_status()
        return

    if args.step in ["images", "all"]:
        await step_images()

    if args.step in ["audio", "all"]:
        await step_audio()

    if args.step in ["video", "all"]:
        await step_video()

    if args.step in ["stills", "all"]:
        await step_stills()

    if args.step in ["concat", "all"]:
        await step_concat()

    print("\n" + "=" * 70)
    if args.step == "all":
        print("FULL PIPELINE COMPLETE")
    else:
        print(f"STEP '{args.step}' COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
