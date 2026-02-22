#!/usr/bin/env python3
"""
Puppet Style Test: Find the best puppet aesthetic for political satire.

Tests multiple image models/approaches for generating felt/Muppet-style
puppet characters (Netanyahu, Trump).

Run:
  python scripts/puppet_style_test.py
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

OUTPUT_DIR = Path("output/puppet_style_test")

# Character descriptions — exaggerated for puppet style
BIBI_DESC = (
    "an older Israeli male politician, gray-white receding hair swept back, "
    "prominent nose, round face, heavy-set build, wearing a dark navy suit "
    "with white shirt and dark tie"
)

TRUMP_DESC = (
    "an American male politician with distinctive swooping blonde-orange hair, "
    "round face, tan skin, wearing a navy blue suit with an oversized red tie, "
    "expressive hand gestures"
)

KISCH_DESC = (
    "an Israeli male politician in his 40s, short dark hair with slight gray, "
    "rectangular glasses, thin face, slightly awkward smile, wearing a dark suit "
    "with white shirt and no tie, eager nodding expression"
)

SILMAN_DESC = (
    "an Israeli female politician in her 40s, straight dark brown shoulder-length hair, "
    "sharp facial features, prominent cheekbones, wearing a professional dark blazer, "
    "enthusiastic agreeable expression, nodding"
)

PUPPET_STYLE = (
    "felt puppet, Muppet style, foam and fabric texture, visible stitched seams, "
    "soft round features, slightly oversized head, studio lighting, "
    "professional puppet photography, Spitting Image style political caricature, "
    "3D felt craft puppet, 9:16 portrait"
)

CLAYMATION_STYLE = (
    "claymation puppet, stop-motion animation style, clay texture, "
    "smooth rounded features, exaggerated caricature proportions, "
    "slightly oversized head, warm studio lighting, Wallace and Gromit quality, "
    "political satire puppet, 9:16 portrait"
)

CARTOON_3D_STYLE = (
    "3D cartoon caricature, Pixar-quality render, exaggerated proportions, "
    "oversized head, comedic expression, glossy skin, dramatic lighting, "
    "political satire character, 9:16 portrait"
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


async def test_flux2_pro(style_name: str, style_desc: str, out_dir: Path):
    """Test FLUX.2 Pro with puppet prompts."""
    out_dir.mkdir(parents=True, exist_ok=True)

    chars = [("bibi", BIBI_DESC), ("trump", TRUMP_DESC), ("kisch", KISCH_DESC), ("silman", SILMAN_DESC)]
    for char_name, char_desc in chars:
        path = out_dir / f"{char_name}.png"
        if path.exists():
            print(f"  {style_name}/FLUX2Pro/{char_name}: exists")
            continue

        prompt = f"Portrait of {char_desc}, rendered as a {style_desc}"
        print(f"  {style_name}/FLUX2Pro/{char_name}: generating...")

        result = await fal_client.run_async("fal-ai/flux-2-pro", arguments={
            "prompt": prompt,
            "image_size": {"width": 576, "height": 1024},
            "num_images": 1,
            "safety_tolerance": "5",
        })
        image_bytes = await download_image(result)
        path.write_bytes(image_bytes)
        print(f"  {style_name}/FLUX2Pro/{char_name}: {len(image_bytes):,} bytes")


async def test_instant_character(style_name: str, style_desc: str, out_dir: Path):
    """Test Instant Character model."""
    out_dir.mkdir(parents=True, exist_ok=True)

    chars = [("bibi", BIBI_DESC), ("trump", TRUMP_DESC), ("kisch", KISCH_DESC), ("silman", SILMAN_DESC)]
    for char_name, char_desc in chars:
        path = out_dir / f"{char_name}.png"
        if path.exists():
            print(f"  {style_name}/InstantChar/{char_name}: exists")
            continue

        prompt = f"{char_desc}, rendered as a {style_desc}"
        print(f"  {style_name}/InstantChar/{char_name}: generating...")

        result = await fal_client.run_async("fal-ai/instant-character", arguments={
            "prompt": prompt,
            "image_size": {"width": 576, "height": 1024},
            "num_images": 1,
        })
        image_bytes = await download_image(result)
        path.write_bytes(image_bytes)
        print(f"  {style_name}/InstantChar/{char_name}: {len(image_bytes):,} bytes")


async def test_nano_banana(style_name: str, style_desc: str, out_dir: Path):
    """Test Nano Banana Pro with puppet prompts."""
    from google import genai
    from google.genai import types

    out_dir.mkdir(parents=True, exist_ok=True)
    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

    chars = [("bibi", BIBI_DESC), ("trump", TRUMP_DESC), ("kisch", KISCH_DESC), ("silman", SILMAN_DESC)]
    for char_name, char_desc in chars:
        path = out_dir / f"{char_name}.png"
        if path.exists():
            print(f"  {style_name}/NanoBanana/{char_name}: exists")
            continue

        prompt = f"Generate a 9:16 portrait of {char_desc}, rendered as a {style_desc}"
        print(f"  {style_name}/NanoBanana/{char_name}: generating...")

        response = client.models.generate_content(
            model="nano-banana-pro-preview",
            contents=[prompt],
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
            print(f"  {style_name}/NanoBanana/{char_name}: FAILED - no image in response")
            continue

        path.write_bytes(image_bytes)
        print(f"  {style_name}/NanoBanana/{char_name}: {len(image_bytes):,} bytes")


async def test_kontext(style_name: str, style_desc: str, out_dir: Path):
    """Test FLUX Kontext Pro with puppet prompts."""
    out_dir.mkdir(parents=True, exist_ok=True)

    chars = [("bibi", BIBI_DESC), ("trump", TRUMP_DESC), ("kisch", KISCH_DESC), ("silman", SILMAN_DESC)]
    for char_name, char_desc in chars:
        path = out_dir / f"{char_name}.png"
        if path.exists():
            print(f"  {style_name}/Kontext/{char_name}: exists")
            continue

        prompt = f"Portrait of {char_desc}, rendered as a {style_desc}"
        print(f"  {style_name}/Kontext/{char_name}: generating...")

        result = await fal_client.run_async("fal-ai/flux-pro/kontext", arguments={
            "prompt": prompt,
            "image_size": {"width": 576, "height": 1024},
            "num_images": 1,
            "safety_tolerance": "5",
        })
        image_bytes = await download_image(result)
        path.write_bytes(image_bytes)
        print(f"  {style_name}/Kontext/{char_name}: {len(image_bytes):,} bytes")


async def main():
    api_key = os.getenv("FAL_KEY") or os.getenv("FAL_API_KEY")
    os.environ["FAL_KEY"] = api_key
    fal_client.api_key = api_key

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("PUPPET STYLE TEST")
    print(f"Output: {OUTPUT_DIR}")
    print("=" * 60)

    styles = [
        ("muppet", PUPPET_STYLE),
        ("claymation", CLAYMATION_STYLE),
        ("cartoon3d", CARTOON_3D_STYLE),
    ]

    for style_name, style_desc in styles:
        print(f"\n--- Style: {style_name} ---")

        # Run models in sequence per style (to avoid rate limits)
        for test_fn, model_name, suffix in [
            (test_flux2_pro, "FLUX2Pro", "flux2pro"),
            (test_instant_character, "InstantChar", "instantchar"),
            (test_nano_banana, "NanoBanana", "nanobana"),
        ]:
            try:
                await test_fn(style_name, style_desc, OUTPUT_DIR / f"{style_name}_{suffix}")
            except Exception as e:
                print(f"  {style_name}/{model_name}: FAILED - {e}")

    print("\n" + "=" * 60)
    print("COMPLETE")
    print("=" * 60)

    # Summary
    print(f"\nGenerated images in: {OUTPUT_DIR}/")
    for d in sorted(OUTPUT_DIR.iterdir()):
        if d.is_dir():
            files = list(d.glob("*.png"))
            print(f"  {d.name}/: {len(files)} images")


if __name__ == "__main__":
    asyncio.run(main())
