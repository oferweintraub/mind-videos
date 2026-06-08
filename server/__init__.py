"""HTTP API server — backs the React frontend in `frontend/`.

Run locally:
    uvicorn server:app --reload --port 8000

Endpoints:
    POST /auth/register         — create a user (sha256 + users.json)
    POST /auth/login            — verify credentials
    GET  /characters            — list the character library
    POST /characters            — save a manifest + image into characters/<slug>/
    POST /create-script         — write episodes/<slug>/script.md
    POST /make-video            — kick off render, returns {job_id}
    GET  /jobs/{job_id}         — poll job status
    GET  /static/characters/... — serve character images for the UI

The Vite dev server proxies /auth, /characters, /create-script, /make-video,
/jobs, /static to this server (see frontend/vite.config.ts).
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import json
import re
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
# Directory that contains the moved server-side package files (server/)
SERVER_ROOT = ROOT
sys.path.insert(0, str(SERVER_ROOT))

from src.character import CHARACTERS_DIR, Character, Voice, list_all as list_characters, slugs as character_slugs  # noqa: E402
from src.script_format import parse as parse_script, validate_against_characters  # noqa: E402
from src.pipeline.character_gen import generate_text_only
from src.config import get_config


USERS_PATH = SERVER_ROOT / "users.json"
EPISODES_DIR = SERVER_ROOT / "episodes"
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


# ---------------------------------------------------------------------------
# Auth storage (sha256 + users.json — same format the old Node server used)
# ---------------------------------------------------------------------------

_users_lock = threading.Lock()


def _normalize_email(email: Optional[str]) -> str:
    return (email or "").strip().lower()


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _load_users() -> dict[str, str]:
    if not USERS_PATH.exists():
        USERS_PATH.write_text("{}", encoding="utf-8")
        return {}
    try:
        raw = USERS_PATH.read_text(encoding="utf-8")
        return json.loads(raw) if raw.strip() else {}
    except (OSError, json.JSONDecodeError) as e:
        print(f"Failed to load users.json: {e}", file=sys.stderr)
        return {}


def _save_users(users: dict[str, str]) -> None:
    USERS_PATH.write_text(json.dumps(users, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Render jobs (in-memory — single-process dev server only)
# ---------------------------------------------------------------------------

JOBS: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def _new_job(slug: str) -> str:
    job_id = uuid.uuid4().hex[:12]
    with _jobs_lock:
        JOBS[job_id] = {
            "id": job_id,
            "slug": slug,
            "status": "queued",
            "started_at": None,
            "finished_at": None,
            "error": None,
            "final_path": None,
            "log_tail": [],
        }
    return job_id


def _update_job(job_id: str, **fields) -> None:
    with _jobs_lock:
        if job_id in JOBS:
            JOBS[job_id].update(fields)


def _append_log(job_id: str, line: str) -> None:
    with _jobs_lock:
        job = JOBS.get(job_id)
        if job is None:
            return
        tail = job["log_tail"]
        tail.append(line.rstrip())
        # Bound memory — keep last 200 lines.
        if len(tail) > 200:
            del tail[: len(tail) - 200]


async def _run_make_episode(job_id: str, slug: str, api_keys: Optional[dict] = None) -> None:
    """Shell out to scripts/make_episode.py and stream logs into the job dict."""
    import os as _os
    _update_job(job_id, status="running", started_at=time.time())
    cmd = [sys.executable, str(SERVER_ROOT / "scripts" / "make_episode.py"), slug]
    env = _os.environ.copy()
    if api_keys:
        if api_keys.get("fal"):
            env["FAL_KEY"] = api_keys["fal"]
        if api_keys.get("elevenlabs"):
            env["ELEVENLABS_API_KEY"] = api_keys["elevenlabs"]
        if api_keys.get("google"):
            env["GOOGLE_API_KEY"] = api_keys["google"]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(SERVER_ROOT),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=env,
        )
        assert proc.stdout is not None
        while True:
            chunk = await proc.stdout.readline()
            if not chunk:
                break
            _append_log(job_id, chunk.decode("utf-8", errors="replace"))
        rc = await proc.wait()
    except Exception as exc:
        _update_job(job_id, status="error", error=str(exc), finished_at=time.time())
        return

    if rc != 0:
        _update_job(job_id, status="error", error=f"make_episode exited with rc={rc}", finished_at=time.time())
        return

    final = EPISODES_DIR / slug / "final.mp4"
    _update_job(
        job_id,
        status="done",
        finished_at=time.time(),
        final_path=str(final.relative_to(SERVER_ROOT)) if final.exists() else None,
    )


# ---------------------------------------------------------------------------
# FastAPI app + request/response models
# ---------------------------------------------------------------------------

app = FastAPI(title="Mind Video API")
# "http://localhost:5173",
#         "http://127.0.0.1:5173",
#         "http://localhost:5174",
#         "http://127.0.0.1:5174",
#         "http://localhost:3000",
#         "http://127.0.0.1:3000",
#         "http://localhost:8501",
# CORS: allow local frontend dev server origins so browser preflight/requests succeed
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
         "http://localhost:5173",
         "http://127.0.0.1:5173",
         "http://localhost:5174",
         "http://127.0.0.1:5174",
         "http://localhost:3000",
         "http://127.0.0.1:3000",
         "http://localhost:8501",
         "http://10.100.102.9:8501"
    ],
    allow_credentials=True,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


class AuthBody(BaseModel):
    email: str
    password: str


class VoiceBody(BaseModel):
    voice_id: str
    voice_name: str = ""
    stability: float = 0.5
    similarity: float = 0.75
    style: float = 0.5
    tempo: float = 1.0


class CharacterBody(BaseModel):
    slug: str
    display_name: str
    description: str
    style: str
    voice: VoiceBody
    image_base64: str = Field(..., description="PNG bytes, base64-encoded (data URL prefix optional).")
    public: bool = True  # default to public for new characters


class CreateScriptBody(BaseModel):
    slug: str
    content: str


class ApiKeysBody(BaseModel):
    fal: str = ""
    elevenlabs: str = ""
    google: str = ""


class MakeVideoBody(BaseModel):
    slug: str
    voice_overrides: dict[str, str] = Field(default_factory=dict)
    api_keys: ApiKeysBody = Field(default_factory=ApiKeysBody)


class CloneVoiceBody(BaseModel):
    name: str
    audio_base64: str = Field(..., description="Audio bytes, base64-encoded (data URL prefix optional).")
    mime_type: str = "audio/mpeg"
    elevenlabs_api_key: str = ""


class GenerateCandidatesBody(BaseModel):
    slug: Optional[str] = None
    description: str
    style: str
    count: int = 3


class PromoteCandidateBody(BaseModel):
    slug: str
    idx: int = 1
    display_name: str = ""
    description: str = ""
    style: str = ""
    voice: VoiceBody
    public: bool = True  # whether to make character public by default


def _safe_slug(text: Optional[str]) -> str:
    s = (text or "").strip().lower()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^a-z0-9_\-]", "_", s)
    s = re.sub(r"_+", "_", s)
    s = re.sub(r"^_|_$", "", s)
    return s or "character"


def _bad(status: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"success": False, "message": message})


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


@app.post("/auth/register")
def auth_register(body: AuthBody):
    email = _normalize_email(body.email)
    if not email or not body.password:
        return _bad(400, "Enter an email and password.")
    with _users_lock:
        users = _load_users()
        if email in users:
            return _bad(409, "A user with that email already exists.")
        users[email] = _hash_password(body.password)
        _save_users(users)
    return {"success": True, "user": {"email": email}}


@app.post("/auth/login")
def auth_login(body: AuthBody):
    email = _normalize_email(body.email)
    if not email or not body.password:
        return _bad(400, "Enter an email and password.")
    with _users_lock:
        users = _load_users()
    stored = users.get(email)
    if not stored:
        return _bad(404, "No account found for that email.")
    if stored != _hash_password(body.password):
        return _bad(401, "Incorrect password.")
    return {"success": True, "user": {"email": email}}


# ---------------------------------------------------------------------------
# Characters
# ---------------------------------------------------------------------------


def _character_to_json(c: Character) -> dict:
    d = c.to_dict()
    d["image_url"] = f"/static/characters/{c.slug}/{c.image}"
    return d


@app.get("/characters")
def characters_list(public_only: bool = True):
    """List characters. Set public_only=false to include private characters (admin only)."""
    return {"characters": [_character_to_json(c) for c in list_characters(public_only=public_only)]}


@app.post("/characters")
def characters_create(body: CharacterBody):
    if not SLUG_RE.match(body.slug):
        raise HTTPException(400, "slug must be lowercase alphanumeric (underscore/dash allowed)")

    payload = body.image_base64
    if payload.startswith("data:"):
        payload = payload.split(",", 1)[-1]
    try:
        image_bytes = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as e:
        raise HTTPException(400, f"image_base64 is not valid base64: {e}")
    if not image_bytes:
        raise HTTPException(400, "image_base64 is empty")

    # Normalize to a real PNG. Users may upload JPEG/WebP; writing those bytes
    # to a file named image.png leaves a misnamed file that can break the
    # downstream lipsync image upload. Re-encode via Pillow so image.png is
    # always genuinely PNG (and RGB, dropping any alpha that trips encoders).
    import io
    from PIL import Image

    try:
        with Image.open(io.BytesIO(image_bytes)) as im:
            im = im.convert("RGB")
            buf = io.BytesIO()
            im.save(buf, format="PNG")
            image_bytes = buf.getvalue()
    except Exception as e:
        raise HTTPException(400, f"could not decode image: {e}")

    char_dir = CHARACTERS_DIR / body.slug
    char_dir.mkdir(parents=True, exist_ok=True)
    (char_dir / "image.png").write_bytes(image_bytes)

    char = Character(
        slug=body.slug,
        display_name=body.display_name,
        description=body.description,
        style=body.style,
        voice=Voice(**body.voice.model_dump()),
        public=body.public,
        image="image.png",
    )
    char.save(char_dir)
    return {"character": _character_to_json(char)}


# ---------------------------------------------------------------------------
# Scripts
# ---------------------------------------------------------------------------


@app.post("/create-script")
def create_script(body: CreateScriptBody):
    if not SLUG_RE.match(body.slug):
        raise HTTPException(400, "slug must be lowercase alphanumeric (underscore/dash allowed)")

    script = parse_script(body.content)
    if not script.segments:
        raise HTTPException(400, "script has no segments — needs at least one `## <character_slug>` heading")

    errors = validate_against_characters(script, character_slugs())
    if errors:
        raise HTTPException(400, "; ".join(errors))

    episode_dir = EPISODES_DIR / body.slug
    episode_dir.mkdir(parents=True, exist_ok=True)
    script_path = episode_dir / "script.md"
    script_path.write_text(body.content, encoding="utf-8")

    return {
        "slug": body.slug,
        "script_path": str(script_path.relative_to(SERVER_ROOT)),
        "segment_count": len(script.segments),
    }

@app.get("/home")
def home():
    return {"message": "Welcome to the Home Page"}

# ---------------------------------------------------------------------------
# Render jobs
# ---------------------------------------------------------------------------


@app.post("/make-video")
async def make_video(body: MakeVideoBody):
    if not SLUG_RE.match(body.slug):
        raise HTTPException(400, "slug must be lowercase alphanumeric (underscore/dash allowed)")
    script_path = EPISODES_DIR / body.slug / "script.md"
    if not script_path.exists():
        raise HTTPException(404, f"no script at {script_path.relative_to(SERVER_ROOT)} — call /create-script first")

    overrides_path = EPISODES_DIR / body.slug / "voice_overrides.json"
    if body.voice_overrides:
        overrides_path.write_text(json.dumps(body.voice_overrides, indent=2), encoding="utf-8")
    elif overrides_path.exists():
        overrides_path.unlink()

    job_id = _new_job(body.slug)
    asyncio.create_task(_run_make_episode(job_id, body.slug, body.api_keys.model_dump()))
    return {"job_id": job_id, "status": "queued"}


@app.post("/clone-voice")
async def clone_voice(body: CloneVoiceBody):
    """Clone a voice sample via ElevenLabs Instant Voice Cloning.

    Reads ELEVENLABS_API_KEY from the server env. Returns the new voice_id.
    """
    import os as _os
    import httpx

    api_key = (body.elevenlabs_api_key or "").strip() or _os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise HTTPException(400, "No ElevenLabs API key — set it in Settings and click Apply")

    payload = body.audio_base64
    if payload.startswith("data:"):
        payload = payload.split(",", 1)[-1]
    try:
        audio_bytes = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as e:
        raise HTTPException(400, f"audio_base64 is not valid base64: {e}")
    if not audio_bytes:
        raise HTTPException(400, "audio_base64 is empty")
    if len(audio_bytes) > 25 * 1024 * 1024:
        raise HTTPException(400, "audio is over 25 MB — ElevenLabs IVC rejects larger files")

    # Pick a reasonable filename + extension from the mime type
    mime = (body.mime_type or "audio/mpeg").lower()
    ext_map = {
        "audio/mpeg": "mp3", "audio/mp3": "mp3",
        "audio/wav": "wav", "audio/x-wav": "wav",
        "audio/webm": "webm",
        "audio/mp4": "m4a", "audio/m4a": "m4a", "audio/x-m4a": "m4a",
    }
    ext = ext_map.get(mime, "mp3")
    safe_name = re.sub(r"[^A-Za-z0-9_\-]", "_", body.name or "voice")[:60] or "voice"

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.post(
                "https://api.elevenlabs.io/v1/voices/add",
                headers={"xi-api-key": api_key},
                data={"name": safe_name},
                files={"files": (f"{safe_name}.{ext}", audio_bytes, mime)},
            )
        except httpx.HTTPError as e:
            raise HTTPException(502, f"ElevenLabs request failed: {e}")

    if resp.status_code >= 400:
        raise HTTPException(resp.status_code, f"ElevenLabs IVC failed: {resp.text}")
    data = resp.json()
    voice_id = data.get("voice_id")
    if not voice_id:
        raise HTTPException(502, f"ElevenLabs response missing voice_id: {data}")
    return {"voice_id": voice_id, "name": safe_name}


@app.get("/jobs/{job_id}")
def job_status(job_id: str):
    with _jobs_lock:
        job = JOBS.get(job_id)
        if job is None:
            raise HTTPException(404, "unknown job_id")
        # Shallow copy so the caller can serialize without locking.
        return dict(job)


# ---------------------------------------------------------------------------
# Rendered videos library
# ---------------------------------------------------------------------------


_TITLE_RE = re.compile(r"^#\s+(.*\S)\s*$")


def _episode_title(slug: str) -> str:
    """Pull a human title from episodes/<slug>/script.md (first `# ` heading)."""
    script_path = EPISODES_DIR / slug / "script.md"
    if script_path.exists():
        try:
            for line in script_path.read_text(encoding="utf-8").splitlines():
                m = _TITLE_RE.match(line.strip())
                if m and not line.lstrip().startswith("##"):
                    return m.group(1)
        except OSError:
            pass
    return slug.replace("_", " ")


@app.get("/videos")
def videos_list():
    """List every episode that has a rendered final.mp4, newest first."""
    if not EPISODES_DIR.exists():
        return {"videos": []}
    videos = []
    for episode_dir in EPISODES_DIR.iterdir():
        if not episode_dir.is_dir():
            continue
        final = episode_dir / "final.mp4"
        if not final.exists():
            continue
        slug = episode_dir.name
        videos.append({
            "slug": slug,
            "title": _episode_title(slug),
            "video_url": f"/static/episodes/{slug}/final.mp4",
            "created_at": final.stat().st_mtime,
        })
    videos.sort(key=lambda v: v["created_at"], reverse=True)
    return {"videos": videos}


# ---------------------------------------------------------------------------
# Static files (character images for the UI)
# ---------------------------------------------------------------------------

if CHARACTERS_DIR.exists():
    app.mount("/static/characters", StaticFiles(directory=str(CHARACTERS_DIR)), name="static-characters")

if EPISODES_DIR.exists():
    app.mount("/static/episodes", StaticFiles(directory=str(EPISODES_DIR)), name="static-episodes")


@app.post("/characters/promote")
def characters_promote(body: PromoteCandidateBody):
    if not SLUG_RE.match(body.slug):
        raise HTTPException(400, "slug must be lowercase alphanumeric (underscore/dash allowed)")

    src_path = CHARACTERS_DIR / "_candidates" / body.slug / f"option_{body.idx}.png"
    if not src_path.exists():
        raise HTTPException(
            404,
            f"no candidate at {src_path.relative_to(SERVER_ROOT)} — generate candidates first",
        )

    char_dir = CHARACTERS_DIR / body.slug
    char_dir.mkdir(parents=True, exist_ok=True)
    (char_dir / "image.png").write_bytes(src_path.read_bytes())

    char = Character(
        slug=body.slug,
        display_name=body.display_name or body.slug.replace("_", " "),
        description=body.description,
        style=body.style,
        voice=Voice(**body.voice.model_dump()),
        public=body.public,  # use the public setting from the request
        image="image.png",
    )
    char.save(char_dir)
    return {"character": _character_to_json(char)}


@app.post("/characters/generate")
async def characters_generate(body: GenerateCandidatesBody):
    """Generate candidate images (text-only) and save under characters/_candidates/<slug>/option_N.png

    Returns JSON: { candidates: [{ idx, image_url }, ... ] }
    """
    cfg = get_config()
    google_key = cfg.api_keys.google
    slug = _safe_slug(body.slug or body.description)
    candidates_dir = CHARACTERS_DIR / "_candidates" / slug
    candidates_dir.mkdir(parents=True, exist_ok=True)

    out = []
    # Generate sequentially to avoid API throttling
    for i in range(1, max(1, int(body.count)) + 1):
        fname = f"option_{i}.png"
        out_path = candidates_dir / fname
        try:
            await generate_text_only(body.description, body.style, out_path, google_api_key=google_key)
        except Exception as exc:
            # On failure, annotate but continue to attempt remaining
            _append_log("generate", f"generate_text_only failed for {out_path}: {exc}")
            continue
        url = f"/static/characters/_candidates/{slug}/{fname}"
        out.append({"idx": i, "image_url": url})

    return {"candidates": out}


# ---------------------------------------------------------------------------
# Voice catalog (stock ElevenLabs voices) — backs the searchable voice picker
# ---------------------------------------------------------------------------

VOICES_PATH = SERVER_ROOT / "config" / "voices.yaml"
VOICE_PREVIEWS_DIR = SERVER_ROOT / "config" / "voice_previews"

if VOICE_PREVIEWS_DIR.is_dir():
    app.mount(
        "/static/voice_previews",
        StaticFiles(directory=str(VOICE_PREVIEWS_DIR)),
        name="voice-previews",
    )


def _load_catalog_voices() -> tuple[list[dict], dict]:
    """Stock voices from config/voices.yaml."""
    import yaml  # pyyaml is already a dependency

    if not VOICES_PATH.exists():
        return [], {}
    try:
        data = yaml.safe_load(VOICES_PATH.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise HTTPException(500, f"voices.yaml is not valid YAML: {e}")
    voices = []
    for v in data.get("voices", []) or []:
        vid = v.get("id", "")
        # Pre-generated Hebrew preview clips ship in config/voice_previews/<id>.mp3
        preview = (
            f"/static/voice_previews/{vid}.mp3"
            if vid and (VOICE_PREVIEWS_DIR / f"{vid}.mp3").is_file()
            else ""
        )
        voices.append({
            "id": vid,
            "name": v.get("name", ""),
            "tone": v.get("tone", ""),
            "good_for": v.get("good_for", []) or [],
            "source": "catalog",
            "category": "premade",
            "preview_url": preview,
        })
    return voices, data.get("defaults", {})


async def _fetch_account_voices() -> list[dict]:
    """Live voices from the ElevenLabs account (incl. cloned). Empty on any error."""
    import os as _os
    import httpx

    api_key = (_os.environ.get("ELEVENLABS_API_KEY") or "").strip()
    if not api_key:
        return []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://api.elevenlabs.io/v1/voices",
                headers={"xi-api-key": api_key},
            )
    except httpx.HTTPError:
        return []
    if resp.status_code >= 400:
        return []

    out = []
    for v in resp.json().get("voices", []) or []:
        labels = v.get("labels") or {}
        tone = ", ".join(
            str(labels[k]) for k in ("accent", "age", "gender", "description", "use_case")
            if labels.get(k)
        )
        out.append({
            "id": v.get("voice_id", ""),
            "name": v.get("name", ""),
            "tone": tone,
            "good_for": [v.get("category")] if v.get("category") else [],
            "source": "account",
            "category": v.get("category", ""),  # cloned | premade | generated | professional
            "preview_url": v.get("preview_url", "") or "",
        })
    return out


@app.get("/voices")
async def list_voices():
    """Stock catalog (config/voices.yaml) merged with live ElevenLabs account
    voices (including cloned). Deduped by id; the catalog's richer description
    wins, but the account category is preserved so cloned voices are findable.
    """
    catalog, defaults = _load_catalog_voices()
    account = await _fetch_account_voices()

    by_id: dict[str, dict] = {}
    for v in catalog:
        if v["id"]:
            by_id[v["id"]] = v
    for v in account:
        if not v["id"]:
            continue
        if v["id"] in by_id:
            # keep the catalog description, but carry over the live category
            # and a preview if the catalog didn't ship one.
            by_id[v["id"]]["category"] = v["category"] or by_id[v["id"]]["category"]
            if not by_id[v["id"]].get("preview_url"):
                by_id[v["id"]]["preview_url"] = v.get("preview_url", "")
        else:
            by_id[v["id"]] = v

    # Cloned voices first (most relevant to the user), then the rest by name.
    voices = sorted(
        by_id.values(),
        key=lambda v: (v.get("category") != "cloned", v.get("name", "").lower()),
    )
    return {"voices": voices, "defaults": defaults}


# ---------------------------------------------------------------------------
# Health check + built frontend (single-container / Cloud Run deploy)
#
# In production the React bundle (frontend/dist) is served by this same server
# so the UI and API share one origin. Locally the Vite dev server proxies to
# this backend instead, so this block is a no-op when dist/ is absent.
# ---------------------------------------------------------------------------

@app.get("/healthz")
def healthz():
    """Liveness probe for Cloud Run / load balancers."""
    return {"status": "ok"}


import os as _os_static  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402

_FRONTEND_DIST = Path(
    _os_static.environ.get("FRONTEND_DIST", str(ROOT.parent / "frontend" / "dist"))
)

if _FRONTEND_DIST.is_dir():
    _INDEX_HTML = _FRONTEND_DIST / "index.html"

    # Hashed JS/CSS/image assets emitted by Vite.
    app.mount(
        "/assets",
        StaticFiles(directory=str(_FRONTEND_DIST / "assets")),
        name="frontend-assets",
    )

    @app.get("/")
    def _spa_root():
        return FileResponse(str(_INDEX_HTML))

    # SPA fallback: any non-API, non-static path returns index.html so the
    # client-side app can render. API routes above are matched first because
    # they were registered before this catch-all.
    @app.get("/{full_path:path}")
    def _spa_fallback(full_path: str):
        candidate = _FRONTEND_DIST / full_path
        if candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(_INDEX_HTML))
