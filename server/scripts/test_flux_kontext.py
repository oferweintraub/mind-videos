"""Smoke test: does generate_with_ref actually produce an image?

Costs ~$0.05 against fal.ai's FLUX Kontext Pro.

Run:  python scripts/test_flux_kontext.py
"""
from __future__ import annotations
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from src.pipeline.character_gen import generate_with_ref


async def main():
    fal_key = os.environ.get("FAL_KEY") or os.environ.get("FAL_API_KEY")
    if not fal_key:
        print("FAL_KEY not in .env")
        sys.exit(1)
    ref = ROOT / "characters" / "eden" / "image.png"
    out_dir = ROOT / "output" / "flux_kontext_test"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "out_lego.png"

    print(f"Ref:        {ref}  ({ref.stat().st_size // 1024} KB)")
    print(f"Out:        {out_path}")
    print(f"Style:      lego")
    print()
    try:
        result = await generate_with_ref(
            ref, "a young girl with two braids in pajamas", "lego", out_path,
            fal_key=fal_key,
        )
        print(f"✅ Success: {result}  ({result.stat().st_size // 1024} KB)")
    except Exception as e:
        print(f"❌ Failed: {type(e).__name__}: {e}")
        import traceback; traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    asyncio.run(main())
