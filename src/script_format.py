"""Episode script format — parser for Markdown-based scripts.

A script is a Markdown file with optional YAML frontmatter and one segment per
`## <character_slug>` heading. Anything after the slug (in the heading line) is
treated as a free-text annotation and ignored by the pipeline.

Example:

    ---
    title: Hostages
    ---

    ## anchor_female  (love-struck)
    אני מאוהבת, איזה מנהיג חזק יש לנו

    ## anchor_male
    לגמרי! לא משאירים אנשים מאחור.

    ## eden  (quiet)
    אבל אמא, החטופים?

The same character may appear multiple times — each heading is a new segment.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Segment:
    character: str          # slug, lowercase
    text: str               # Hebrew (or any) text, stripped
    annotation: str = ""    # free-text after slug in heading, e.g. "(love-struck)"


@dataclass
class EpisodeScript:
    segments: list[Segment]
    meta: dict = field(default_factory=dict)
    source_path: Optional[Path] = None

    @property
    def title(self) -> str:
        return self.meta.get("title", "")

    @property
    def characters(self) -> list[str]:
        """Distinct character slugs used, in first-appearance order."""
        seen, out = set(), []
        for s in self.segments:
            if s.character not in seen:
                seen.add(s.character)
                out.append(s.character)
        return out


_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_HEADING_RE = re.compile(r"^##\s+(\S+)\s*(.*)$")


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    block, rest = m.group(1), text[m.end():]
    meta: dict = {}
    try:
        import yaml
        meta = yaml.safe_load(block) or {}
    except Exception:
        # Fallback: simple "key: value" lines
        for line in block.splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                meta[k.strip()] = v.strip().strip('"').strip("'")
    return meta, rest


def parse(text: str, source_path: Optional[Path] = None) -> EpisodeScript:
    meta, body = _parse_frontmatter(text)
    segments: list[Segment] = []
    current_slug: Optional[str] = None
    current_annotation = ""
    current_lines: list[str] = []

    def flush():
        if current_slug is None:
            return
        joined = "\n".join(current_lines).strip()
        if joined:
            segments.append(Segment(
                character=current_slug,
                text=joined,
                annotation=current_annotation.strip(),
            ))

    for raw in body.splitlines():
        m = _HEADING_RE.match(raw.rstrip())
        if m:
            flush()
            current_slug = m.group(1).lower().strip()
            current_annotation = m.group(2).strip()
            current_lines = []
        else:
            if current_slug is not None:
                current_lines.append(raw)
    flush()

    return EpisodeScript(segments=segments, meta=meta or {}, source_path=source_path)


def parse_file(path: Path) -> EpisodeScript:
    path = Path(path)
    return parse(path.read_text(encoding="utf-8"), source_path=path)


def validate_against_characters(script: EpisodeScript, available_slugs: list[str]) -> list[str]:
    """Return a list of error strings for characters referenced in the script
    that don't exist in the character library. Empty list = valid."""
    available = set(available_slugs)
    missing = [s.character for s in script.segments if s.character not in available]
    if not missing:
        return []
    seen, out = set(), []
    for slug in missing:
        if slug in seen:
            continue
        seen.add(slug)
        out.append(
            f"Character '{slug}' referenced in script but not in characters/. "
            f"Available: {sorted(available)}"
        )
    return out
