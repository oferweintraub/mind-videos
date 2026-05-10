"""Wizard session state + project import/export.

Single source of truth for wizard state: cast (in-memory list of Character),
segments (list of {character_slug, text}), title, current step, render result.

`init_state()` is idempotent — safe to call on every rerun.

Project import/export is a `.zip` containing the manifest+image of each
character plus the script.md. The same zip can be re-uploaded to resume work
after Streamlit Cloud's ephemeral disk is wiped.
"""

from __future__ import annotations

import io
import json
import re
import shutil
import zipfile
from dataclasses import asdict
from pathlib import Path
from typing import Optional

import streamlit as st

from src.character import Character, Voice, list_all as list_characters, load as load_character
from src.script_format import parse
from src.wizard import persistence


WIZARD_KEYS = ("step", "cast", "segments", "title", "result", "render_running",
               "demo_loaded", "loaded_zip_marker", "project_id", "share_keys")


DEMO_CAST_SLUGS = ["anchor_female", "anchor_male", "eden"]
DEMO_SEGMENTS = [
    {"character": "anchor_female",
     "text": "אני מאוהבת, איזה מנהיג חזק, איזה מנהיג דגול יש לנו, קרה לנו נס!"},
    {"character": "anchor_male",
     "text": "לגמרי! לא משאירים אנשים מאחור, זה לא יקרה במשמרת שלנו!"},
    {"character": "eden",
     "text": "אמא, הוא אמר שלא משאירים אנשים מאחור, אבל את החטופים השארנו מאחור."},
]
DEMO_TITLE = "Hostages"


def init_state():
    """Create the wizard's session-state slots if missing. Idempotent.

    The cast starts empty so "Load demo" has clear meaning. Characters in the
    on-disk library are still browsable; the wizard just doesn't auto-import
    them.
    """
    s = st.session_state
    if "step" not in s:
        s.step = 1
    if "cast" not in s:
        s.cast = {}    # slug -> Character (in-memory)
    if "segments" not in s:
        s.segments = []
    if "title" not in s:
        s.title = ""
    if "result" not in s:
        s.result = None  # {"path": str, "elapsed": float, "cost": float}
    if "render_running" not in s:
        s.render_running = False
    if "demo_loaded" not in s:
        s.demo_loaded = False
    if "loaded_zip_marker" not in s:
        s.loaded_zip_marker = None
    # Cloud persistence (Phase 2). project_id is set the first time a user
    # touches state — after that, every state change auto-saves.
    if "project_id" not in s:
        s.project_id = None
    if "share_keys" not in s:
        s.share_keys = False


def load_demo() -> bool:
    """Populate the cast with Channel 14 + Eden and segments with the hostages
    example. Returns True if all 3 demo characters were available on disk.
    """
    s = st.session_state
    s.cast = {}
    for slug in DEMO_CAST_SLUGS:
        try:
            char = load_character(slug)
            s.cast[slug] = char
        except FileNotFoundError:
            pass
    s.segments = [dict(seg) for seg in DEMO_SEGMENTS]  # copy
    s.title = DEMO_TITLE
    s.demo_loaded = True
    # Persist + push character images to storage
    pid = ensure_project_id()
    if pid:
        persistence.sync_cast_images_to_storage(pid, s.cast)
    auto_save()
    return len(s.cast) == len(DEMO_CAST_SLUGS)


def reset_all():
    """Clear the wizard back to a fresh project. Doesn't touch on-disk characters."""
    for k in WIZARD_KEYS:
        if k in st.session_state:
            del st.session_state[k]
    init_state()


def go_to(step: int):
    st.session_state.step = step
    auto_save()


# --- Cloud persistence (Phase 2) ---------------------------------------------

def ensure_project_id() -> Optional[str]:
    """Return the current project_id, creating one (in Supabase) if missing.

    Returns None when Supabase isn't configured — callers should treat
    persistence as a no-op in that case (local-only mode).
    """
    s = st.session_state
    if s.get("project_id"):
        return s.project_id
    if not persistence.is_configured():
        return None
    pid = persistence.new_project_id()
    try:
        persistence.create_project(pid, title=s.get("title", ""))
        s.project_id = pid
        # Reflect in URL so the user can bookmark / share immediately
        try:
            st.query_params["p"] = pid
        except Exception:
            pass
        return pid
    except Exception as e:
        st.toast(f"Couldn't create cloud project: {type(e).__name__}", icon="⚠️")
        return None


def auto_save() -> None:
    """Persist session_state to Supabase. Best-effort, idempotent, no-op if
    persistence isn't configured."""
    s = st.session_state
    pid = s.get("project_id")
    if not pid or not persistence.is_configured():
        return
    try:
        persistence.save_state(
            pid,
            title=s.get("title", "") or "",
            cast_data=persistence.serialize_cast(s.get("cast", {})),
            segments_data=list(s.get("segments", [])),
            step=int(s.get("step", 1)),
            share_keys=bool(s.get("share_keys", False)),
        )
    except Exception as e:
        st.toast(f"Auto-save failed: {type(e).__name__}", icon="⚠️")


def hydrate_from_project(project_id: str) -> bool:
    """Replace current session_state with state from a Supabase project.

    Returns True on success. False if the project doesn't exist or
    persistence isn't configured.
    """
    if not persistence.is_configured():
        return False
    row = persistence.load_project(project_id)
    if row is None:
        return False
    s = st.session_state
    s.project_id = project_id
    s.title = row.get("title") or ""
    s.cast = persistence.deserialize_cast(row.get("cast_data") or [])
    s.segments = list(row.get("segments_data") or [])
    s.step = int(row.get("step") or 1)
    s.result = row.get("result")
    s.share_keys = bool(row.get("share_keys"))
    # If keys were shared, populate the per-session key inputs
    api_keys = row.get("api_keys") or {}
    if api_keys:
        if api_keys.get("fal"):
            s["_key_FAL_KEY"] = api_keys["fal"]
        if api_keys.get("elevenlabs"):
            s["_key_ELEVENLABS_API_KEY"] = api_keys["elevenlabs"]
        if api_keys.get("google"):
            s["_key_GOOGLE_API_KEY"] = api_keys["google"]
    # Pull character images from storage onto local disk so existing
    # pipeline code (char.image_path) just works
    persistence.hydrate_cast_images_from_storage(project_id, s.cast)
    return True


def add_character(char: Character):
    """Insert/replace a character in the cast (in-memory + on-disk).

    The character is expected to have its image+manifest already saved on disk
    (via scripts/save_character.py or its in-process equivalent).
    """
    st.session_state.cast[char.slug] = char
    pid = ensure_project_id()
    if pid and char.dir is not None:
        img_path = char.dir / char.image
        if img_path.exists():
            try:
                persistence.upload_character_image(pid, char.slug, img_path.read_bytes())
            except Exception:
                pass
    auto_save()


def remove_character(slug: str):
    """Remove from session cast. Also remove any segments using this character."""
    st.session_state.cast.pop(slug, None)
    st.session_state.segments = [
        s for s in st.session_state.segments if s.get("character") != slug
    ]
    auto_save()


def add_segment(character: str, text: str = ""):
    st.session_state.segments.append({"character": character, "text": text})
    auto_save()


def remove_segment(idx: int):
    if 0 <= idx < len(st.session_state.segments):
        st.session_state.segments.pop(idx)
        auto_save()


def move_segment(idx: int, delta: int):
    """Move segment at idx up (delta=-1) or down (delta=+1)."""
    segs = st.session_state.segments
    j = idx + delta
    if 0 <= j < len(segs):
        segs[idx], segs[j] = segs[j], segs[idx]
        auto_save()


# --- Cost / duration estimates ------------------------------------------------

CHARS_PER_SEC = 15.0          # Hebrew TTS rough rate
LIPSYNC_USD_PER_SEC = 0.08    # VEED Fabric 480p
TTS_USD_PER_SEG = 0.05        # rough, mostly subscription


def estimate_segment_seconds(text: str) -> float:
    return max(1.0, len(text) / CHARS_PER_SEC)


def estimate_episode(segments: list[dict]) -> dict:
    """Return {audio_secs, cost_usd, segments}. Defensive against missing text."""
    audio_secs = sum(estimate_segment_seconds(s.get("text", "")) for s in segments)
    cost = audio_secs * LIPSYNC_USD_PER_SEC + TTS_USD_PER_SEG * len(segments)
    return {"audio_secs": audio_secs, "cost_usd": cost, "segments": len(segments)}


# --- Slug helpers -------------------------------------------------------------

_SAFE_SLUG_RE = re.compile(r"[^a-z0-9_]+")


def safe_slug(text: str, fallback: str = "character") -> str:
    """Coerce a free-text label into a valid character slug."""
    s = text.strip().lower().replace(" ", "_").replace("-", "_")
    s = _SAFE_SLUG_RE.sub("", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:30] or fallback


def safe_episode_slug(text: str, fallback: str = "my_episode") -> str:
    return safe_slug(text, fallback)


# --- Project export / import (.zip) -------------------------------------------

def export_project_zip(title: str, cast: dict, segments: list[dict]) -> bytes:
    """Build an in-memory .zip of the current project. Returns the bytes."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Characters: include manifest + image for everyone in the cast
        for slug, char in cast.items():
            manifest_data = json.dumps(char.to_dict(), indent=2, ensure_ascii=False)
            zf.writestr(f"characters/{slug}/manifest.json", manifest_data)
            if char.dir is not None and char.image_path.exists():
                zf.write(char.image_path, f"characters/{slug}/image.png")
        # Episode: a script.md
        script_lines = []
        if title:
            script_lines.append("---")
            script_lines.append(f"title: {title}")
            script_lines.append("---")
            script_lines.append("")
        for seg in segments:
            slug = seg.get("character", "")
            text = (seg.get("text") or "").strip()
            if not slug or not text:
                continue
            script_lines.append(f"## {slug}")
            script_lines.append(text)
            script_lines.append("")
        slug_for_dir = safe_episode_slug(title or "project")
        zf.writestr(f"episodes/{slug_for_dir}/script.md", "\n".join(script_lines))
        # README inside the zip so users know what they downloaded
        zf.writestr("README.txt",
                    "Mind Video — exported project\n\n"
                    "Drop this .zip back into the wizard's settings drawer to resume.\n"
                    "Or unzip into a Mind Video repo's root to use from the CLI.\n")
    buf.seek(0)
    return buf.read()


def import_project_zip(file_bytes: bytes, characters_root: Path) -> tuple[dict, list[dict], str]:
    """Extract a project zip into characters_root and parse the script.

    Writes characters/<slug>/{manifest.json, image.png} to disk so they survive
    across the rerun. Returns (cast_dict, segments_list, title).
    """
    cast: dict = {}
    segments: list[dict] = []
    title = ""

    with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
        # First pass: write all character files to disk
        for name in zf.namelist():
            if not name.startswith("characters/") or name.endswith("/"):
                continue
            parts = name.split("/")
            if len(parts) != 3:
                continue
            _, slug, fname = parts
            if fname not in ("manifest.json", "image.png"):
                continue
            target_dir = characters_root / slug
            target_dir.mkdir(parents=True, exist_ok=True)
            (target_dir / fname).write_bytes(zf.read(name))

        # Second pass: load every character from disk via the canonical loader
        for d in sorted(characters_root.iterdir()):
            if not d.is_dir() or d.name.startswith("_"):
                continue
            if not (d / "manifest.json").exists():
                continue
            try:
                char = load_character(d.name, root=characters_root)
                cast[char.slug] = char
            except Exception:
                continue

        # Find a script.md anywhere under episodes/
        for name in zf.namelist():
            if name.endswith("script.md") and name.startswith("episodes/"):
                script_text = zf.read(name).decode("utf-8")
                parsed = parse(script_text)
                title = parsed.title
                segments = [
                    {"character": s.character, "text": s.text}
                    for s in parsed.segments
                ]
                break

    return cast, segments, title
