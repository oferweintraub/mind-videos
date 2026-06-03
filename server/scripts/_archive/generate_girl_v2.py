#!/usr/bin/env python3
"""
Generate 5 cuter variants of the braids girl (South Park style).
Based on girl_sp3 direction but much more cute, warm, relatable.
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

from google import genai
from google.genai import types

OUTPUT_DIR = Path("output/girl_options_v2")

STYLE_SOUTHPARK = (
    "South Park cartoon style, flat 2D paper cutout animation, "
    "simple geometric shapes, thick black outlines, bright flat colors, "
    "construction-paper texture, Comedy Central South Park aesthetic"
)

GIRL_CORE = (
    "extremely cute and adorable 10-year-old Israeli girl, "
    "big sparkling warm brown eyes that are twice the normal South Park size, "
    "round soft face, rosy cheeks, small button nose, "
    "sweet innocent expression full of curiosity and wonder, "
    "the kind of face that makes every adult in the room melt"
)

CHARACTERS = {
    "girl_v2a": {
        "prompt": (
            f"Generate a 9:16 image of an {GIRL_CORE}. "
            "She has two long dark braids with small pink hair ties, "
            "wearing a cozy oversized light blue t-shirt that's too big for her, "
            "sitting on an orange couch in a warm Israeli living room, "
            "holding a bowl of cereal with both hands, looking up at the TV "
            "with a puzzled tilted-head expression, mouth slightly open. "
            "The room is cozy with warm lighting. "
            f"Rendered in {STYLE_SOUTHPARK}."
        ),
    },
    "girl_v2b": {
        "prompt": (
            f"Generate a 9:16 image of an {GIRL_CORE}. "
            "She has two dark braids with colorful mismatched hair ties, "
            "a small band-aid on one knee, "
            "wearing pink pajamas with little stars on them, "
            "sitting cross-legged on a couch hugging a worn stuffed bunny, "
            "looking at the TV with her head tilted and one eyebrow raised, "
            "confused but thoughtful expression. "
            "Warm cozy Israeli living room background. "
            f"Rendered in {STYLE_SOUTHPARK}."
        ),
    },
    "girl_v2c": {
        "prompt": (
            f"Generate a 9:16 image of an {GIRL_CORE}. "
            "She has two short dark braids sticking out to the sides, "
            "a few freckles on her nose and cheeks, gap in her front teeth visible, "
            "wearing a simple white t-shirt and purple shorts, "
            "sitting on a couch with her knees pulled up to her chin, "
            "arms wrapped around her legs, looking at the TV with wide confused eyes. "
            "A glass of chocolate milk on the coffee table. "
            "Warm living room with a bookshelf in background. "
            f"Rendered in {STYLE_SOUTHPARK}."
        ),
    },
    "girl_v2d": {
        "prompt": (
            f"Generate a 9:16 image of an {GIRL_CORE}. "
            "She has messy dark hair in two loose braids that are coming undone, "
            "a tiny butterfly hair clip on one side, "
            "wearing an oversized hoodie that covers her hands (sweater paws), "
            "sitting on a couch with a blanket over her lap, "
            "looking up from the TV toward camera with the most innocent questioning face, "
            "like she's about to say 'but why?'. "
            "Cozy warm-lit Israeli living room. "
            f"Rendered in {STYLE_SOUTHPARK}."
        ),
    },
    "girl_v2e": {
        "prompt": (
            f"Generate a 9:16 image of an {GIRL_CORE}. "
            "She has two neat dark braids, a red headband, "
            "round rosy cheeks, the biggest most innocent eyes, "
            "wearing a striped rainbow t-shirt, "
            "sitting on a couch next to a sleeping cat, "
            "one hand raised slightly as if about to ask a question in class, "
            "sweet earnest expression. "
            "Warm Israeli living room with family photos on the wall. "
            f"Rendered in {STYLE_SOUTHPARK}."
        ),
    },
}


async def generate_all():
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("ERROR: GOOGLE_API_KEY not set")
        return

    client = genai.Client(api_key=api_key)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for name, char in CHARACTERS.items():
        output_path = OUTPUT_DIR / f"{name}.png"
        if output_path.exists():
            print(f"  SKIP {name} (exists)")
            continue

        print(f"  Generating {name}...")
        try:
            response = client.models.generate_content(
                model="nano-banana-pro-preview",
                contents=[char["prompt"]],
                config=types.GenerateContentConfig(response_modalities=["image", "text"]),
            )

            saved = False
            for part in response.candidates[0].content.parts:
                if hasattr(part, "inline_data") and part.inline_data:
                    output_path.write_bytes(part.inline_data.data)
                    print(f"  ✓ Saved {output_path}")
                    saved = True
                    break
            if not saved:
                print(f"  ✗ No image returned for {name}")
                for part in response.candidates[0].content.parts:
                    if hasattr(part, "text") and part.text:
                        print(f"    Text: {part.text[:200]}")

        except Exception as e:
            print(f"  ✗ Error for {name}: {e}")

        await asyncio.sleep(2)


if __name__ == "__main__":
    print(f"Generating {len(CHARACTERS)} cute girl variants into {OUTPUT_DIR}/")
    print()
    asyncio.run(generate_all())
    print("\nDone! Review images in:", OUTPUT_DIR)
