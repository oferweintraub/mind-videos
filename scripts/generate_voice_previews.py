"""One-shot: generate a short Hebrew preview MP3 per stock voice.

Usage:
    python scripts/generate_voice_previews.py [--force]

Reads config/voices.yaml. For each voice, calls ElevenLabs with a fixed
Hebrew sample line. Saves to config/voice_previews/<voice_id>.mp3.

The previews are committed to the repo so deploys can serve them instantly
without per-session API spend. Re-run with --force to regenerate (e.g. after
adding a new voice or tweaking the sample text).

Cost: ~10 voices × ~30 chars × $0.30/1k chars ≈ $0.001 total.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import httpx
import yaml


# A single short Hebrew line that exercises a few different sounds — pleasant
# and informative when the user clicks the preview button.
SAMPLE_TEXT = "שלום, ככה אני נשמע. נעים להכיר."


async def synthesize(voice_id: str, out_path: Path) -> None:
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        sys.exit("ERROR: ELEVENLABS_API_KEY not set. Add to .env first.")
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={"xi-api-key": api_key},
            json={
                "text": SAMPLE_TEXT,
                "model_id": "eleven_v3",
                "language_code": "he",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                    "style": 0.4,
                },
            },
        )
        r.raise_for_status()
        out_path.write_bytes(r.content)


async def main_async(force: bool):
    catalog = yaml.safe_load((ROOT / "config" / "voices.yaml").read_text())
    voices = catalog.get("voices", [])
    out_dir = ROOT / "config" / "voice_previews"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f">> {len(voices)} voices in catalog")
    print(f">> Sample text: {SAMPLE_TEXT}")
    print(f">> Output: {out_dir.relative_to(ROOT)}/\n")

    todo = []
    for v in voices:
        out = out_dir / f"{v['id']}.mp3"
        if out.exists() and not force:
            print(f"   [skip]  {v['name']:<10} (preview exists)")
            continue
        todo.append((v, out))

    if not todo:
        print("\n>> All previews exist. Pass --force to regenerate.")
        return

    # Sequential — Creator tier only allows ~2 concurrent TTS requests.
    print(f"\n>> Generating {len(todo)} previews sequentially…")
    for v, out in todo:
        for attempt in range(3):
            try:
                await synthesize(v["id"], out)
                print(f"   [ok]    {v['name']}")
                break
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < 2:
                    await asyncio.sleep(3 * (attempt + 1))
                    continue
                print(f"   [FAIL]  {v['name']:<10} {type(e).__name__}: {e}")
                break
            except Exception as e:
                print(f"   [FAIL]  {v['name']:<10} {type(e).__name__}: {e}")
                break

    print(f"\n>> Done.")


def main():
    p = argparse.ArgumentParser(description="Generate Hebrew voice previews")
    p.add_argument("--force", action="store_true",
                   help="Regenerate all (default: skip existing)")
    args = p.parse_args()
    asyncio.run(main_async(args.force))


if __name__ == "__main__":
    main()
