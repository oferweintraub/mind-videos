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
    character: str          # slug, lowercase (for a scene: the narrator's voice)
    text: str               # Hebrew (or any) text, stripped (for a scene: narration)
    annotation: str = ""    # free-text after slug in heading, e.g. "(love-struck)"
    animation: str = ""     # text-to-video prompt — set via "(anim: ...)" annotation
    background: str = ""    # scene background hint — set via "(bg: ...)" annotation

    @property
    def is_scene(self) -> bool:
        """A scene is a generated-animation clip rather than a lip-synced still."""
        return bool(self.animation.strip())


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
# Annotation keys: "(anim: <text-to-video prompt>)" / "(bg: <scene hint>)".
# Non-greedy capture anchored to the final ")" tolerates parens inside the value.
_ANIM_RE = re.compile(r"\(\s*anim:\s*(.*?)\s*\)\s*$", re.IGNORECASE)
_BG_RE = re.compile(r"\(\s*bg:\s*(.*?)\s*\)\s*$", re.IGNORECASE)


def _annotation_value(annotation: str, pattern: re.Pattern) -> str:
    """Pull a `(key: value)` value out of a heading annotation, or '' if absent."""
    m = pattern.search(annotation or "")
    return m.group(1).strip() if m else ""


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
        annotation = current_annotation.strip()
        animation = _annotation_value(annotation, _ANIM_RE)
        background = _annotation_value(annotation, _BG_RE)
        # Keep the segment if it has narration text OR is an animation scene
        # (a scene may have an empty narration line).
        if joined or animation:
            segments.append(Segment(
                character=current_slug,
                text=joined,
                annotation=annotation,
                animation=animation,
                background=background,
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
