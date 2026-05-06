"""Character lab — generate N candidate stills for a new character.

Two modes:

  Single style (N candidates of one style):
    python scripts/character_lab.py \\
        --description "young woman, blonde wavy hair, green eyes, soft smile" \\
        --style lego \\
        --slug young_woman \\
        --count 3

  Multi-style (one candidate per style — useful when you're undecided):
    python scripts/character_lab.py \\
        --description "70-year-old grandpa, white hair, weary eyes" \\
        --style lego,south_park,muppet \\
        --slug old_man

Writes:
    characters/_candidates/<slug>/option_1.png
    characters/_candidates/<slug>/option_1_style.txt   (which style was used)
    characters/_candidates/<slug>/option_2.png
    characters/_candidates/<slug>/option_2_style.txt
    ... etc
    characters/_candidates/<slug>/_prompt.txt   (last prompt used)

After review, promote one with:
    python scripts/save_character.py --slug young_woman --pick 2 [voice options]
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

from google import genai
from google.genai import types


STYLE_PRESETS = {
    "south_park": (
        "Rendered in South Park flat 2D paper-cutout cartoon style with thick black outlines, "
        "bright flat colors, and simple geometric features."
    ),
    "lego": (
        "Rendered as a LEGO minifigure in glossy plastic 3D, blocky cylindrical proportions, "
        "stud on the head, simple printed face."
    ),
    "muppet": (
        "Rendered as a Sesame Street / Muppet-style felt puppet, oversized head, "
        "large ping-pong-ball eyes, fuzzy felt texture, soft warm studio lighting."
    ),
    "pixar": (
        "Rendered in Pixar / Disney 3D cartoon style, soft shading, large expressive eyes, "
        "warm and approachable look."
    ),
    "ghibli": (
        "Rendered in Studio Ghibli watercolor anime style, soft natural lighting, "
        "hand-painted backgrounds, gentle expression."
    ),
    "comic": (
        "Rendered in digital comic book art style, bold linework, halftone shading, "
        "saturated colors."
    ),
    "anime": (
        "Rendered in modern Japanese anime style, clean linework, large eyes, cel shading."
    ),
}


def build_prompt(description: str, style: str) -> str:
    style_lower = style.strip().lower().replace("-", "_").replace(" ", "_")
    style_clause = STYLE_PRESETS.get(style_lower, f"Rendered in {style} style.")
    return (
        f"Generate a vertical 9:16 portrait image of a single character: {description}. "
        f"{style_clause} "
        f"The character is centered in the frame from the chest up, looking slightly toward the camera. "
        f"Important: no hands near the face, mouth fully visible and clearly defined, "
        f"eyes well-lit, neutral or slightly warm expression suitable for animated lip-sync. "
        f"Plain or softly out-of-focus background; do not include any text, captions, logos, or watermarks."
    )


async def generate_one(client: genai.Client, prompt: str, out_path: Path) -> Path:
    response = client.models.generate_content(
        model="nano-banana-pro-preview",
        contents=[prompt],
        config=types.GenerateContentConfig(response_modalities=["image", "text"]),
    )
    for part in response.candidates[0].content.parts:
        if hasattr(part, "inline_data") and part.inline_data:
            out_path.write_bytes(part.inline_data.data)
            return out_path
    raise RuntimeError(f"Nano Banana Pro returned no image data for {out_path.name}")


def parse_styles(style_arg: str) -> list[str]:
    """Split a --style value on commas. Whitespace tolerant. Always returns >=1 entry."""
    parts = [s.strip() for s in style_arg.split(",") if s.strip()]
    if not parts:
        sys.exit("ERROR: --style is empty")
    return parts


async def main_async(args):
    if "GOOGLE_API_KEY" not in os.environ:
        sys.exit("ERROR: GOOGLE_API_KEY is not set. Add it to .env or export it.")

    out_dir = ROOT / "characters" / "_candidates" / args.slug
    out_dir.mkdir(parents=True, exist_ok=True)

    styles = parse_styles(args.style)
    multi_style = len(styles) > 1

    if multi_style:
        # One candidate per style. --count is ignored in this mode.
        plan = [(i, styles[i - 1]) for i in range(1, len(styles) + 1)]
        print(f"\n>> Multi-style mode: 1 candidate per style for slug='{args.slug}'")
        print(f">> Styles: {styles}")
    else:
        plan = [(i, styles[0]) for i in range(1, args.count + 1)]
        print(f"\n>> Generating {args.count} candidates for slug='{args.slug}', style='{styles[0]}'")

    print(f">> Output: {out_dir.relative_to(ROOT)}/")
    # Save the last prompt used for human reference
    sample_prompt = build_prompt(args.description, styles[0])
    (out_dir / "_prompt.txt").write_text(sample_prompt + "\n")
    print(f">> Prompt (sample): {sample_prompt[:120]}...\n")

    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    tasks = []
    plan_for_results: list[tuple[int, str]] = []
    for i, style in plan:
        out = out_dir / f"option_{i}.png"
        if out.exists() and not args.force:
            print(f"   [skip] {out.name} ({style}) already exists (pass --force to regenerate)")
            continue
        prompt = build_prompt(args.description, style)
        (out_dir / f"option_{i}_style.txt").write_text(style)
        tasks.append(generate_one(client, prompt, out))
        plan_for_results.append((i, style))

    if not tasks:
        print(">> All candidates already exist. Nothing to do.")
        return

    results = await asyncio.gather(*tasks, return_exceptions=True)
    for (i, style), r in zip(plan_for_results, results):
        if isinstance(r, Exception):
            print(f"   [FAIL] option_{i} ({style}): {type(r).__name__}: {r}")
        else:
            print(f"   [ok]   option_{i} ({style}) -> {r.relative_to(ROOT)}")

    print(f"\n>> Done. Review the candidates and pick one with:")
    print(f"   python scripts/save_character.py --slug {args.slug} --pick <N> "
          f"--display-name '...' --voice-id <ELEVENLABS_ID>")


def main():
    p = argparse.ArgumentParser(description="Generate candidate character images")
    p.add_argument("--description", required=True,
                   help="One-paragraph English description of the character")
    p.add_argument("--style", required=True,
                   help=f"Style: one of {sorted(STYLE_PRESETS)} or any free-text style label. "
                        "Comma-separated for multi-style (e.g. 'lego,south_park,muppet') — "
                        "produces one candidate per style; --count is ignored.")
    p.add_argument("--slug", required=True,
                   help="Short slug (lowercase, underscores), e.g. young_woman")
    p.add_argument("--count", type=int, default=3, help="Number of candidates (default 3)")
    p.add_argument("--force", action="store_true", help="Regenerate even if files exist")
    args = p.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
