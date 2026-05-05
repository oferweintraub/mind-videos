"""Character library — manifest-driven characters for the video pipeline.

Each character lives in `characters/<slug>/`:
  manifest.json   — metadata (description, style, voice settings)
  image.png       — the reference still used for lip-sync

A character is everything needed to make a segment:
  - what they look like (image)
  - what they sound like (voice_id + tts settings)
  - how they're described (for prompting consistency in /new-script)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional


CHARACTERS_DIR = Path(__file__).resolve().parent.parent / "characters"


@dataclass
class Voice:
    voice_id: str
    voice_name: str = ""
    stability: float = 0.5
    similarity: float = 0.75
    style: float = 0.5
    tempo: float = 1.0


@dataclass
class Character:
    slug: str                # e.g. "anchor_female"
    display_name: str        # e.g. "Female Anchor (Channel 14)"
    description: str         # one-paragraph English description (for prompting)
    style: str               # short style label, e.g. "south_park", "lego", "muppet"
    voice: Voice
    image: str = "image.png"  # filename relative to the character dir
    dir: Optional[Path] = None  # set on load; not serialized

    @property
    def image_path(self) -> Path:
        if self.dir is None:
            raise RuntimeError(f"Character {self.slug} has no dir set; call load() first")
        return self.dir / self.image

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("dir", None)
        return d

    def save(self, dir: Optional[Path] = None) -> Path:
        target = Path(dir) if dir else self.dir
        if target is None:
            target = CHARACTERS_DIR / self.slug
        target.mkdir(parents=True, exist_ok=True)
        manifest = target / "manifest.json"
        manifest.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False))
        self.dir = target
        return manifest


def load(slug: str, root: Optional[Path] = None) -> Character:
    root = Path(root) if root else CHARACTERS_DIR
    char_dir = root / slug
    manifest = char_dir / "manifest.json"
    if not manifest.exists():
        raise FileNotFoundError(
            f"No manifest at {manifest}. Available: {[p.name for p in root.iterdir() if p.is_dir() and not p.name.startswith('_')]}"
        )
    data = json.loads(manifest.read_text())
    voice = Voice(**data.pop("voice"))
    char = Character(voice=voice, **data)
    char.dir = char_dir
    if not char.image_path.exists():
        raise FileNotFoundError(f"Character {slug} manifest references missing image: {char.image_path}")
    return char


def list_all(root: Optional[Path] = None) -> list[Character]:
    root = Path(root) if root else CHARACTERS_DIR
    if not root.exists():
        return []
    out = []
    for p in sorted(root.iterdir()):
        if not p.is_dir() or p.name.startswith("_"):
            continue
        if not (p / "manifest.json").exists():
            continue
        try:
            out.append(load(p.name, root=root))
        except (FileNotFoundError, json.JSONDecodeError):
            continue
    return out


def slugs(root: Optional[Path] = None) -> list[str]:
    return [c.slug for c in list_all(root)]
