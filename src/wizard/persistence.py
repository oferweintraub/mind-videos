"""Supabase persistence for the wizard.

Each project lives as a row in the `projects` table, with character
images stored in the `character-images` bucket keyed by
`<project_id>/<slug>.png`.

Trust model: anyone with the project_id can read/write that project.
The URL itself is the bearer token (RLS off on the table). Same model
as Excalidraw or jsonbin.

When SUPABASE_URL and SUPABASE_KEY aren't set (e.g., local dev without
the .env entries), `is_configured()` returns False and the wizard
silently falls back to in-memory-only state. This keeps the local
runner workable for developers who don't want a Supabase project.
"""

from __future__ import annotations

import base64
import logging
import os
import secrets
from dataclasses import asdict
from pathlib import Path
from typing import Optional

import streamlit as st


_BUCKET = "character-images"
log = logging.getLogger("mind-video.persistence")


def _read_secret(name: str) -> Optional[str]:
    """Read SUPABASE_URL or SUPABASE_KEY from secrets, env, in that order."""
    try:
        v = st.secrets[name]
        if v:
            return str(v).strip()
    except Exception as e:
        # Don't log a full traceback for missing keys — st.secrets raises
        # KeyError when a key isn't present, and that's expected during
        # local dev. Only log unusual exceptions.
        if not isinstance(e, KeyError):
            log.warning("_read_secret(%s): st.secrets raised %s: %s", name, type(e).__name__, e)
    env_val = (os.environ.get(name) or "").strip() or None
    return env_val


def is_configured() -> bool:
    url = _read_secret("SUPABASE_URL")
    key = _read_secret("SUPABASE_KEY")
    ok = bool(url) and bool(key)
    if not ok:
        log.info("is_configured: url_set=%s key_set=%s", bool(url), bool(key))
    return ok


@st.cache_resource
def _client():
    """Cached Supabase client. Created once per session, reused across reruns."""
    from supabase import create_client
    url = _read_secret("SUPABASE_URL")
    key = _read_secret("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("Supabase not configured (missing SUPABASE_URL or SUPABASE_KEY)")
    return create_client(url, key)


def new_project_id() -> str:
    """Generate a 12-char URL-safe random ID (~72 bits entropy)."""
    return base64.urlsafe_b64encode(secrets.token_bytes(9)).rstrip(b"=").decode()


# ---------------------------------------------------------------------------
# Project row CRUD
# ---------------------------------------------------------------------------

def create_project(project_id: str, title: str = "") -> dict:
    """Insert a new (mostly empty) project row. Returns the row data."""
    res = _client().table("projects").insert({
        "id": project_id,
        "title": title,
    }).execute()
    return res.data[0] if res.data else {}


def load_project(project_id: str) -> Optional[dict]:
    """Fetch a project row by ID. Returns None if not found."""
    try:
        res = (
            _client().table("projects")
            .select("*")
            .eq("id", project_id)
            .limit(1)
            .execute()
        )
    except Exception:
        log.exception("load_project(%s): query raised", project_id)
        raise
    n = len(res.data or [])
    log.info("load_project(%s): rows=%d", project_id, n)
    return res.data[0] if res.data else None


def save_state(
    project_id: str,
    *,
    title: Optional[str] = None,
    cast_data: Optional[list] = None,
    segments_data: Optional[list] = None,
    step: Optional[int] = None,
    result: Optional[dict] = None,
    share_keys: Optional[bool] = None,
    api_keys: Optional[dict] = None,
) -> None:
    """Update fields on a project row. None values are skipped."""
    update: dict = {}
    if title is not None: update["title"] = title
    if cast_data is not None: update["cast_data"] = cast_data
    if segments_data is not None: update["segments_data"] = segments_data
    if step is not None: update["step"] = step
    if result is not None: update["result"] = result
    if share_keys is not None: update["share_keys"] = share_keys
    if api_keys is not None: update["api_keys"] = api_keys
    if not update:
        return
    _client().table("projects").update(update).eq("id", project_id).execute()


def delete_project(project_id: str) -> None:
    """Hard delete: project row + all storage objects."""
    client = _client()
    try:
        files = client.storage.from_(_BUCKET).list(project_id) or []
        keys = [f"{project_id}/{f['name']}" for f in files if f.get("name")]
        if keys:
            client.storage.from_(_BUCKET).remove(keys)
    except Exception:
        pass  # storage cleanup best-effort
    client.table("projects").delete().eq("id", project_id).execute()


# ---------------------------------------------------------------------------
# Character image CRUD (storage bucket)
# ---------------------------------------------------------------------------

def upload_character_image(project_id: str, slug: str, image_bytes: bytes) -> str:
    """Upload (or overwrite) a character image. Returns the storage key."""
    key = f"{project_id}/{slug}.png"
    _client().storage.from_(_BUCKET).upload(
        path=key,
        file=image_bytes,
        file_options={"content-type": "image/png", "upsert": "true"},
    )
    return key


def download_character_image(project_id: str, slug: str) -> Optional[bytes]:
    """Download a character image. Returns bytes or None if missing."""
    try:
        return _client().storage.from_(_BUCKET).download(f"{project_id}/{slug}.png")
    except Exception:
        return None


def list_project_objects(project_id: str) -> list[str]:
    """List all storage object names under <project_id>/. Useful for sync."""
    try:
        files = _client().storage.from_(_BUCKET).list(project_id) or []
        return [f["name"] for f in files if f.get("name")]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Episode video CRUD (storage bucket — same bucket as character images)
# ---------------------------------------------------------------------------

def _episode_video_key(project_id: str, slug: str) -> str:
    return f"{project_id}/episode_{slug}.mp4"


def upload_episode_video(project_id: str, slug: str, video_bytes: bytes) -> str:
    """Upload (or overwrite) a rendered episode mp4. Returns the storage key."""
    key = _episode_video_key(project_id, slug)
    _client().storage.from_(_BUCKET).upload(
        path=key,
        file=video_bytes,
        file_options={"content-type": "video/mp4", "upsert": "true"},
    )
    return key


def download_episode_video(project_id: str, slug: str) -> Optional[bytes]:
    """Download a rendered episode mp4. Returns bytes or None if missing."""
    try:
        return _client().storage.from_(_BUCKET).download(_episode_video_key(project_id, slug))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Project ↔ session_state helpers (called from the wizard)
# ---------------------------------------------------------------------------

CHARACTERS_DIR = Path(__file__).resolve().parent.parent.parent / "characters"


def serialize_cast(cast: dict) -> list[dict]:
    """Cast dict -> list of plain dicts suitable for cast_data jsonb."""
    out = []
    for slug, char in cast.items():
        out.append({
            "slug": char.slug,
            "display_name": char.display_name,
            "description": char.description,
            "style": char.style,
            "voice": asdict(char.voice),
            "image": char.image,
        })
    return out


def deserialize_cast(cast_data: list[dict]) -> dict:
    """list of dicts -> dict slug -> Character, with .dir set to characters/<slug>."""
    from src.character import Character, Voice
    out = {}
    for d in cast_data or []:
        voice = Voice(**d.get("voice", {}))
        char = Character(
            slug=d["slug"],
            display_name=d.get("display_name", ""),
            description=d.get("description", ""),
            style=d.get("style", ""),
            voice=voice,
            image=d.get("image", "image.png"),
        )
        char.dir = CHARACTERS_DIR / char.slug
        out[char.slug] = char
    return out


def sync_cast_images_to_storage(project_id: str, cast: dict) -> int:
    """Upload every cast member's local image.png to storage. Idempotent.

    Returns number of images uploaded. Best-effort — failures don't raise.
    """
    n = 0
    for slug, char in cast.items():
        if char.dir is None:
            continue
        path = char.dir / char.image
        if not path.exists():
            continue
        try:
            upload_character_image(project_id, slug, path.read_bytes())
            n += 1
        except Exception:
            pass  # best-effort
    return n


def hydrate_cast_images_from_storage(project_id: str, cast: dict) -> int:
    """Download cast images from storage to local disk (so existing pipeline
    code that reads char.image_path works unchanged). Idempotent — skips
    if a local file already exists.

    Returns number of images downloaded.
    """
    n = 0
    for slug, char in cast.items():
        if char.dir is None:
            continue
        char.dir.mkdir(parents=True, exist_ok=True)
        local = char.dir / char.image
        if local.exists():
            continue
        data = download_character_image(project_id, slug)
        if data is None:
            continue
        local.write_bytes(data)
        n += 1
    return n
