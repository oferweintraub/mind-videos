"""Promote a candidate from characters/_candidates/ into the character library.

Usage:
    python scripts/save_character.py \\
        --slug young_woman \\
        --pick 2 \\
        --display-name "Young Woman (Lego)" \\
        --description "young woman, blonde wavy hair, green eyes, soft smile" \\
        --style lego \\
        --voice-id FGY2WhTYpPnrIDTdsKH5 \\
        --voice-name "Laura" \\
        --tempo 1.0

Result:
    characters/young_woman/manifest.json
    characters/young_woman/image.png   (copied from option_2.png)
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.character import Character, Voice


def _voice_catalog() -> dict:
    """Load config/voices.yaml. Returns empty dict if missing/unparseable."""
    try:
        import yaml  # type: ignore
        path = ROOT / "config" / "voices.yaml"
        if not path.exists():
            return {}
        return yaml.safe_load(path.read_text()) or {}
    except Exception:
        return {}


def main():
    p = argparse.ArgumentParser(description="Promote a character candidate to the library")
    p.add_argument("--slug", required=True)
    p.add_argument("--pick", type=int, required=True, help="Candidate number (1-based) to promote")
    p.add_argument("--display-name", default="", help="Human-readable display name")
    p.add_argument("--description", default="", help="Description (one paragraph)")
    p.add_argument("--style", default="custom", help="Style label, e.g. south_park, lego, muppet")

    p.add_argument("--voice-id", required=True, help="ElevenLabs voice ID")
    p.add_argument("--voice-name", default="", help="Human label for the voice")
    p.add_argument("--stability", type=float, default=0.5)
    p.add_argument("--similarity", type=float, default=0.75)
    p.add_argument("--style-weight", type=float, default=0.5,
                   help="ElevenLabs 'style' value (0.0-1.0)")
    p.add_argument("--tempo", type=float, default=1.0,
                   help="ffmpeg atempo applied after TTS (1.0 = no change, 1.25 = 25%% faster)")

    p.add_argument("--force", action="store_true",
                   help="Overwrite an existing characters/<slug>/ directory")
    args = p.parse_args()

    candidates_dir = ROOT / "characters" / "_candidates" / args.slug
    src_image = candidates_dir / f"option_{args.pick}.png"
    if not src_image.exists():
        sys.exit(f"ERROR: candidate not found: {src_image.relative_to(ROOT)}\n"
                 f"  Run scripts/character_lab.py first, or check the --pick number.")

    target_dir = ROOT / "characters" / args.slug
    target_image = target_dir / "image.png"
    target_manifest = target_dir / "manifest.json"
    if target_dir.exists() and (target_manifest.exists() or target_image.exists()) and not args.force:
        sys.exit(f"ERROR: characters/{args.slug}/ already exists. Pass --force to overwrite.")

    # Soft-validate the voice ID against the catalog. Don't error — clones
    # and freshly-discovered voices won't be in the file.
    catalog = _voice_catalog()
    catalog_voices = catalog.get("voices", []) if catalog else []
    catalog_ids = {v["id"]: v for v in catalog_voices}
    if catalog_ids and args.voice_id not in catalog_ids:
        print(f"   [note] voice_id '{args.voice_id}' is not in config/voices.yaml — "
              f"using anyway (custom voice or clone). Run "
              f"`python scripts/list_voices.py` to see the catalog.")
    elif args.voice_id in catalog_ids and not args.voice_name:
        # Convenience: fill in name from the catalog if user didn't pass one
        args.voice_name = catalog_ids[args.voice_id]["name"]

    target_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_image, target_image)

    char = Character(
        slug=args.slug,
        display_name=args.display_name or args.slug.replace("_", " ").title(),
        description=args.description,
        style=args.style,
        voice=Voice(
            voice_id=args.voice_id,
            voice_name=args.voice_name,
            stability=args.stability,
            similarity=args.similarity,
            style=args.style_weight,
            tempo=args.tempo,
        ),
    )
    char.save(dir=target_dir)

    print(f"\n>> Saved character: {args.slug}")
    print(f"   image:    characters/{args.slug}/image.png")
    print(f"   manifest: characters/{args.slug}/manifest.json")
    print(f"   voice:    {args.voice_id} ({args.voice_name or 'unnamed'})")
    print(f"\n   Use it in a script.md with: '## {args.slug}'\n")


if __name__ == "__main__":
    main()
