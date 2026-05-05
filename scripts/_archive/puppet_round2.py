#!/usr/bin/env python3
"""
Puppet Round 2: Improved character descriptions based on real reference photos.

Uses:
- FLUX.2 Pro (text-only, best puppet texture) for all characters
- Nano Banana Pro (with reference photos) for Kisch and Silman

Output: output/puppet_style_test/round2/
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

import fal_client
import httpx

OUTPUT_DIR = Path("output/puppet_style_test/round2")
REF_DIR = Path("output/puppet_style_test/references")

# ── Updated character descriptions ──

BIBI_DESC = (
    "an older heavy-set Israeli male politician with gray-white receding hair swept back, "
    "heavy jowls, double chin, squinty scheming eyes, prominent bulbous nose, "
    "smug conniving smirk, shifty expression like a con artist, "
    "wearing a dark navy suit with white shirt and dark tie"
)

TRUMP_DESC = (
    "an American male politician with distinctive swooping blonde-orange hair, "
    "round face, tan skin, wearing a navy blue suit with an oversized red tie, "
    "expressive hand gestures"
)

KISCH_DESC = (
    "a stocky heavy-set Israeli male politician in his 50s, short gray-peppered hair "
    "receding at the temples, square jaw, broad face, thick neck, rectangular glasses, "
    "obsequious sycophantic grin showing teeth, eager-to-please expression, "
    "wearing a dark suit with white shirt and gold tie"
)

SILMAN_DESC = (
    "a slender Israeli female politician in her 40s with very curly light-brown hair "
    "pulled up in a bun with a fabric headband turban covering the top of her head, "
    "thin elongated face, prominent cheekbones, long nose, round black earrings, "
    "vacant agreeable smile, nodding enthusiastically, dim-witted expression, "
    "wearing a dark patterned blouse"
)

PUPPET_STYLE = (
    "felt puppet, Muppet style, foam and fabric texture, visible stitched seams, "
    "soft round features, slightly oversized head, studio lighting, "
    "professional puppet photography, Spitting Image style political caricature, "
    "3D felt craft puppet, 9:16 portrait"
)


async def download_image(result) -> bytes:
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
            out = result["output"]
            image_url = out.get("url") if isinstance(out, dict) else out
    elif hasattr(result, "images") and result.images:
        image_url = result.images[0].url if hasattr(result.images[0], "url") else result.images[0]

    if not image_url:
        raise RuntimeError(f"No image URL in result: {result}")

    async with httpx.AsyncClient(timeout=60.0) as http:
        resp = await http.get(image_url)
        resp.raise_for_status()
        return resp.content


async def generate_flux2pro(char_name: str, char_desc: str, out_dir: Path):
    """Generate puppet with FLUX.2 Pro (text-only, best puppet texture)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{char_name}.png"
    if path.exists():
        print(f"  FLUX2Pro/{char_name}: exists")
        return

    prompt = f"Portrait of {char_desc}, rendered as a {PUPPET_STYLE}"
    print(f"  FLUX2Pro/{char_name}: generating...")

    result = await fal_client.run_async("fal-ai/flux-2-pro", arguments={
        "prompt": prompt,
        "image_size": {"width": 576, "height": 1024},
        "num_images": 1,
        "safety_tolerance": "5",
    })
    image_bytes = await download_image(result)
    path.write_bytes(image_bytes)
    print(f"  FLUX2Pro/{char_name}: {len(image_bytes):,} bytes")


async def generate_nanobana_with_ref(char_name: str, char_desc: str, ref_dir: Path, out_dir: Path):
    """Generate puppet with Nano Banana Pro using reference photos."""
    from google import genai
    from google.genai import types

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{char_name}.png"
    if path.exists():
        print(f"  NanoBana+Ref/{char_name}: exists")
        return

    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

    # Load reference images
    ref_files = sorted(ref_dir.glob("*.png"))[:3]  # Use up to 3 refs
    if not ref_files:
        print(f"  NanoBana+Ref/{char_name}: no reference images found in {ref_dir}")
        return

    contents = []
    for ref_file in ref_files:
        ref_bytes = ref_file.read_bytes()
        contents.append(types.Part.from_bytes(data=ref_bytes, mime_type='image/png'))

    prompt = (
        f"Look at these reference photos of this person. "
        f"Now generate a 9:16 portrait of this SAME person as a {PUPPET_STYLE}. "
        f"The puppet should be a satirical caricature: {char_desc}. "
        f"Keep the person's distinctive facial features but exaggerate them in puppet form."
    )
    contents.append(prompt)

    print(f"  NanoBana+Ref/{char_name}: generating with {len(ref_files)} reference photos...")

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
        print(f"  NanoBana+Ref/{char_name}: FAILED - no image in response")
        return

    path.write_bytes(image_bytes)
    print(f"  NanoBana+Ref/{char_name}: {len(image_bytes):,} bytes")


async def main():
    api_key = os.getenv("FAL_KEY") or os.getenv("FAL_API_KEY")
    os.environ["FAL_KEY"] = api_key
    fal_client.api_key = api_key

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("PUPPET ROUND 2 — Improved Descriptions + Reference Photos")
    print(f"Output: {OUTPUT_DIR}")
    print("=" * 60)

    flux_dir = OUTPUT_DIR / "flux2pro"
    nanobana_dir = OUTPUT_DIR / "nanobana_ref"

    # ── FLUX.2 Pro (text-only) — all 4 characters ──
    print("\n--- FLUX.2 Pro (text-only, muppet style) ---")
    for char_name, char_desc in [
        ("bibi", BIBI_DESC),
        ("trump", TRUMP_DESC),
        ("kisch", KISCH_DESC),
        ("silman", SILMAN_DESC),
    ]:
        try:
            await generate_flux2pro(char_name, char_desc, flux_dir)
        except Exception as e:
            print(f"  FLUX2Pro/{char_name}: FAILED - {e}")

    # ── Nano Banana Pro (with reference photos) — Kisch, Silman, Bibi ──
    print("\n--- Nano Banana Pro (with reference photos, muppet style) ---")
    for char_name, char_desc, ref_subdir in [
        ("kisch", KISCH_DESC, REF_DIR / "kisch"),
        ("silman", SILMAN_DESC, REF_DIR / "silman"),
    ]:
        try:
            await generate_nanobana_with_ref(char_name, char_desc, ref_subdir, nanobana_dir)
        except Exception as e:
            print(f"  NanoBana+Ref/{char_name}: FAILED - {e}")

    print("\n" + "=" * 60)
    print("COMPLETE")
    print("=" * 60)

    # Summary
    for d in sorted(OUTPUT_DIR.iterdir()):
        if d.is_dir():
            files = list(d.glob("*.png"))
            print(f"  {d.name}/: {len(files)} images")


if __name__ == "__main__":
    asyncio.run(main())
