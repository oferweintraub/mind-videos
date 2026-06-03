#!/usr/bin/env python3
"""
Generate 5 options for the child character (10-year-old girl).
3 in South Park style, 2 in puppet style — to match both anchor sets.
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

OUTPUT_DIR = Path("output/girl_options")

STYLE_SOUTHPARK = (
    "South Park cartoon style, flat 2D paper cutout animation, "
    "simple geometric shapes, thick black outlines, bright flat colors, "
    "small beady eyes, simple round head, construction-paper texture, "
    "Comedy Central South Park aesthetic"
)

STYLE_PUPPET = (
    "felt puppet, Muppet style, foam and fabric texture, visible stitched seams, "
    "soft round features, slightly oversized head, studio lighting, "
    "professional puppet photography, 3D felt craft puppet"
)

GIRL_BASE = (
    "adorable 10-year-old Israeli girl, big warm brown eyes full of wonder, "
    "olive skin, cute round face, innocent naive expression, "
    "slightly messy hair, wearing pajamas or a simple t-shirt, "
    "sitting on a couch in a cozy Israeli living room watching TV, "
    "she looks smart and curious, like she's about to ask a question that will "
    "stump every adult in the room"
)

CHARACTERS = {
    "girl_sp1": {
        "style": "southpark",
        "prompt": (
            f"Generate a 9:16 portrait of an {GIRL_BASE}. "
            "She has long dark wavy hair in a messy ponytail, big curious eyes, "
            "wearing a purple pajama top, holding a cereal bowl. "
            f"Rendered in {STYLE_SOUTHPARK}."
        ),
    },
    "girl_sp2": {
        "style": "southpark",
        "prompt": (
            f"Generate a 9:16 portrait of an {GIRL_BASE}. "
            "She has short dark curly hair with a small hair clip, "
            "wearing an oversized t-shirt as pajamas, hugging a stuffed bear, "
            "one eyebrow slightly raised in confusion. "
            f"Rendered in {STYLE_SOUTHPARK}."
        ),
    },
    "girl_sp3": {
        "style": "southpark",
        "prompt": (
            f"Generate a 9:16 portrait of an {GIRL_BASE}. "
            "She has two braids with colorful hair ties, freckles on her nose, "
            "wearing a yellow t-shirt, sitting cross-legged on the couch, "
            "head tilted to the side with a puzzled look. "
            f"Rendered in {STYLE_SOUTHPARK}."
        ),
    },
    "girl_puppet1": {
        "style": "puppet",
        "prompt": (
            f"Generate a 9:16 portrait of an {GIRL_BASE}. "
            "She has long dark wavy hair, big round felt eyes with long eyelashes, "
            "rosy felt cheeks, wearing cozy pink pajamas, "
            "sitting on a couch holding a glass of milk, looking up at the TV with wonder. "
            f"Rendered as a {STYLE_PUPPET}."
        ),
    },
    "girl_puppet2": {
        "style": "puppet",
        "prompt": (
            f"Generate a 9:16 portrait of an {GIRL_BASE}. "
            "She has dark curly hair in a loose bun with strands falling out, "
            "big warm brown felt eyes, a tiny gap in her front teeth, "
            "wearing an oversized hoodie, sitting on a couch with knees up, "
            "looking confused and thoughtful. "
            f"Rendered as a {STYLE_PUPPET}."
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

        print(f"  Generating {name} ({char['style']})...")
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
    print(f"Generating {len(CHARACTERS)} girl character options into {OUTPUT_DIR}/")
    print(f"  South Park: 3 variants")
    print(f"  Puppet:     2 variants")
    print()
    asyncio.run(generate_all())
    print("\nDone! Review images in:", OUTPUT_DIR)
