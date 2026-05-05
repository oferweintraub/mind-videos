#!/usr/bin/env python3
"""
Generate Channel 14 anchor character options across 3 visual styles.
5 female + 5 male = 10 total (spread across styles).
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

OUTPUT_DIR = Path("output/anchor_options")

# --- Style definitions ---

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

STYLE_CARTOON = (
    "bold 2D cartoon caricature, flat bright colors, thick outlines, "
    "exaggerated features, editorial cartoon style meets adult animation, "
    "slightly grotesque satirical illustration, sharp angular shapes, "
    "like Archer or Superjail adult animation style"
)

# --- Character base descriptions ---

FEMALE_BASE = (
    "young Israeli Sephardic/Mizrahi woman in her early 30s, "
    "dark olive skin, big dark eyes with heavy dramatic makeup and fake eyelashes, "
    "long dark hair (straightened or big curls), full lips, sharp eyebrows, "
    "hoop earrings, tight-fitting top with number '14' printed on it, "
    "aggressive confident expression, slightly trashy glamour, "
    "looks like she's about to yell at someone on a talk show, "
    "Israeli TV news studio background with '14' logo"
)

MALE_BASE = (
    "young Israeli Sephardic/Mizrahi man in his early 30s, "
    "dark olive skin, short dark hair with lots of gel slicked back, "
    "thick eyebrows, stubble beard, gold chain visible under collar, "
    "muscular build, tight polo shirt or button-up with number '14' printed on it, "
    "cocky aggressive smirk, looks like a bouncer who got a TV job, "
    "Israeli TV news studio background with '14' logo"
)

# --- Variants per character across styles ---

CHARACTERS = {
    # South Park style - 2 female + 2 male
    "female_sp1": {
        "style": "southpark",
        "prompt": (
            f"Generate a 9:16 portrait of a {FEMALE_BASE}. "
            "She has straightened long dark hair, big hoop earrings, chewing gum. "
            f"Rendered in {STYLE_SOUTHPARK}."
        ),
    },
    "female_sp2": {
        "style": "southpark",
        "prompt": (
            f"Generate a 9:16 portrait of a {FEMALE_BASE}. "
            "She has big voluminous curly dark hair, red lipstick, long acrylic nails visible. "
            f"Rendered in {STYLE_SOUTHPARK}."
        ),
    },
    "male_sp1": {
        "style": "southpark",
        "prompt": (
            f"Generate a 9:16 portrait of a {MALE_BASE}. "
            "He has very short buzzcut, thick neck, tight black polo with gold chain. "
            f"Rendered in {STYLE_SOUTHPARK}."
        ),
    },
    "male_sp2": {
        "style": "southpark",
        "prompt": (
            f"Generate a 9:16 portrait of a {MALE_BASE}. "
            "He has slicked-back hair with undercut, open collar white shirt showing chest hair and gold chain. "
            f"Rendered in {STYLE_SOUTHPARK}."
        ),
    },

    # Puppet / Muppet style - 2 female + 2 male
    "female_puppet1": {
        "style": "puppet",
        "prompt": (
            f"Generate a 9:16 portrait of a {FEMALE_BASE}. "
            "She has straightened dark hair with blonde highlights, big fake eyelashes, "
            "glossy lips, chewing gum with mouth slightly open. "
            f"Rendered as a {STYLE_PUPPET}."
        ),
    },
    "female_puppet2": {
        "style": "puppet",
        "prompt": (
            f"Generate a 9:16 portrait of a {FEMALE_BASE}. "
            "She has a high tight ponytail, heavy contour makeup, big gold hoop earrings, "
            "resting attitude face, one eyebrow raised. "
            f"Rendered as a {STYLE_PUPPET}."
        ),
    },
    "male_puppet1": {
        "style": "puppet",
        "prompt": (
            f"Generate a 9:16 portrait of a {MALE_BASE}. "
            "He has gelled spiky short dark hair, diamond stud earring, "
            "tight V-neck with chest showing, self-satisfied grin. "
            f"Rendered as a {STYLE_PUPPET}."
        ),
    },
    "male_puppet2": {
        "style": "puppet",
        "prompt": (
            f"Generate a 9:16 portrait of a {MALE_BASE}. "
            "He has a neat fade haircut, trimmed beard, "
            "button-up shirt rolled sleeves showing forearm tattoo, smug expression. "
            f"Rendered as a {STYLE_PUPPET}."
        ),
    },

    # Bold 2D cartoon - 1 female + 1 male
    "female_cartoon1": {
        "style": "cartoon",
        "prompt": (
            f"Generate a 9:16 portrait of a {FEMALE_BASE}. "
            "She has big wild dark curly hair, oversized earrings, red lipstick, "
            "leaning forward aggressively pointing at camera. "
            f"Rendered in {STYLE_CARTOON}."
        ),
    },
    "male_cartoon1": {
        "style": "cartoon",
        "prompt": (
            f"Generate a 9:16 portrait of a {MALE_BASE}. "
            "He has slicked-back dark hair, heavy gold chain, too-tight shirt straining at buttons, "
            "pointing aggressively at camera with cocky grin. "
            f"Rendered in {STYLE_CARTOON}."
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

            # Extract image
            saved = False
            for part in response.candidates[0].content.parts:
                if hasattr(part, "inline_data") and part.inline_data:
                    output_path.write_bytes(part.inline_data.data)
                    print(f"  ✓ Saved {output_path}")
                    saved = True
                    break
            if not saved:
                print(f"  ✗ No image returned for {name}")
                # Save any text response for debugging
                for part in response.candidates[0].content.parts:
                    if hasattr(part, "text") and part.text:
                        print(f"    Text: {part.text[:200]}")

        except Exception as e:
            print(f"  ✗ Error for {name}: {e}")

        # Small delay to avoid rate limiting
        await asyncio.sleep(2)


if __name__ == "__main__":
    print(f"Generating {len(CHARACTERS)} anchor options into {OUTPUT_DIR}/")
    print(f"  South Park: 2F + 2M")
    print(f"  Puppet:     2F + 2M")
    print(f"  Cartoon:    1F + 1M")
    print()
    asyncio.run(generate_all())
    print("\nDone! Review images in:", OUTPUT_DIR)
