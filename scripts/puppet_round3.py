#!/usr/bin/env python3
"""
Puppet Round 3: All characters via Nano Banana Pro.
Uses reference photos for Kisch and Silman.
Satirical personality descriptions for all characters.
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

OUTPUT_DIR = Path("output/puppet_style_test/round3")
REF_DIR = Path("output/puppet_style_test/references")

PUPPET_STYLE = (
    "felt puppet, Muppet style, foam and fabric texture, visible stitched seams, "
    "soft round features, slightly oversized head, studio lighting, "
    "professional puppet photography, Spitting Image style political caricature, "
    "3D felt craft puppet"
)

# Character prompts with satirical personality
CHARACTERS = {
    "bibi": {
        "ref_dir": None,  # text-only
        "prompt": (
            "Generate a 9:16 portrait of a felt Muppet puppet caricature of an older heavy-set "
            "Israeli male politician: gray-white receding hair swept back, heavy jowls, double chin, "
            "squinty scheming eyes, prominent bulbous nose, smug conniving smirk. "
            "He looks like a crook, a con artist, a swindler — shifty-eyed and plotting. "
            "Wearing a dark navy suit with white shirt and dark tie. "
            f"Rendered as a {PUPPET_STYLE}."
        ),
    },
    "trump": {
        "ref_dir": None,  # text-only
        "prompt": (
            "Generate a 9:16 portrait of a felt Muppet puppet caricature of an American male "
            "politician with distinctive swooping blonde-orange hair, round face, very tan/orange skin, "
            "small pursed lips, wearing a navy blue suit with an oversized bright red tie, "
            "expressive hand gestures, bombastic confident expression. "
            f"Rendered as a {PUPPET_STYLE}."
        ),
    },
    "kisch": {
        "ref_dir": REF_DIR / "kisch",
        "prompt": (
            "Look at these reference photos of this person. "
            "Now create a 9:16 portrait of this SAME person reimagined as a "
            f"{PUPPET_STYLE}. "
            "Keep his exact face — stocky heavy-set build, short gray-peppered hair receding at temples, "
            "square jaw, broad face, thick neck, rectangular glasses. "
            "But make him look like a sycophantic flatterer — obsequious grin showing teeth, "
            "sleazy eager-to-please expression, like a yes-man who agrees with everything his boss says. "
            "Wearing dark suit with gold tie. Exaggerate his features for satirical puppet caricature."
        ),
    },
    "silman": {
        "ref_dir": REF_DIR / "silman",
        "prompt": (
            "Look at these reference photos of this person. "
            "Now create a 9:16 portrait of this SAME person reimagined as a "
            f"{PUPPET_STYLE}. "
            "Keep her exact look — slender woman with very curly light-brown hair pulled up in a bun "
            "with a fabric headband turban, thin elongated face, prominent cheekbones, "
            "round black earrings, wearing dark patterned blouse. "
            "But make her look like an empty-headed yes-woman — vacant agreeable smile, "
            "nodding enthusiastically, dim-witted expression, an echoer who repeats whatever her boss says. "
            "Exaggerate her features for satirical puppet caricature."
        ),
    },
}


def generate_image(client, char_name: str, char_info: dict, out_dir: Path):
    """Generate puppet with Nano Banana Pro."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{char_name}.png"
    if path.exists():
        print(f"  {char_name}: exists")
        return

    contents = []

    # Add reference images if available
    ref_dir = char_info.get("ref_dir")
    if ref_dir and ref_dir.exists():
        ref_files = sorted(ref_dir.glob("*.png"))[:4]
        for ref_file in ref_files:
            ref_bytes = ref_file.read_bytes()
            contents.append(types.Part.from_bytes(data=ref_bytes, mime_type='image/png'))
        print(f"  {char_name}: generating with {len(ref_files)} reference photos...")
    else:
        print(f"  {char_name}: generating (text-only)...")

    contents.append(char_info["prompt"])

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

    if not image_bytes:
        print(f"  {char_name}: FAILED - no image in response")
        # Try again without "dim-witted" language (safety filter)
        if ref_dir:
            print(f"  {char_name}: retrying with softer prompt...")
            softer_prompt = char_info["prompt"].replace(
                "dim-witted expression, an echoer who repeats whatever her boss says",
                "eager agreeable expression, always nodding along"
            ).replace(
                "sleazy eager-to-please expression, like a yes-man who agrees with everything his boss says",
                "eager-to-please expression, always nodding in agreement"
            )
            contents_retry = []
            ref_files = sorted(ref_dir.glob("*.png"))[:4]
            for ref_file in ref_files:
                contents_retry.append(types.Part.from_bytes(data=ref_file.read_bytes(), mime_type='image/png'))
            contents_retry.append(softer_prompt)

            response2 = client.models.generate_content(
                model="nano-banana-pro-preview",
                contents=contents_retry,
                config=types.GenerateContentConfig(response_modalities=['image', 'text']),
            )
            if response2.candidates:
                for c in response2.candidates:
                    if c.content and c.content.parts:
                        for p in c.content.parts:
                            if hasattr(p, 'inline_data') and p.inline_data:
                                image_bytes = p.inline_data.data
                                break
            if not image_bytes:
                print(f"  {char_name}: RETRY ALSO FAILED")
                return

    path.write_bytes(image_bytes)
    print(f"  {char_name}: {len(image_bytes):,} bytes")


def main():
    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("PUPPET ROUND 3 — Nano Banana Pro (all characters)")
    print(f"Output: {OUTPUT_DIR}")
    print("=" * 60)

    for char_name, char_info in CHARACTERS.items():
        try:
            generate_image(client, char_name, char_info, OUTPUT_DIR)
        except Exception as e:
            print(f"  {char_name}: FAILED - {e}")

    print("\n" + "=" * 60)
    print("COMPLETE")
    print("=" * 60)

    files = list(OUTPUT_DIR.glob("*.png"))
    print(f"Generated {len(files)} images in {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
