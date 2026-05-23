"""Content-hash cache keys for per-segment pipeline outputs.

Why content hashing instead of seg-index-based filenames:
- A change to one segment doesn't bust cached files for unchanged segments
  (no more "fix one pronunciation, lose another" — eleven_v3 is non-
  deterministic, so a re-run of an unchanged segment may pronounce things
  differently. With hash caching we don't re-run it at all.)
- Cross-project pollution becomes impossible — the path includes the hash
- "Render again" on an unchanged project is a zero-cost cache hit
- To force a fresh take of the same text, bump regen_counter so the hash
  changes (used by the per-segment Regenerate button)

Used by both src/wizard/step3_render.py (Streamlit) and scripts/make_episode.py
(CLI) so they share the same cache.
"""

import hashlib
from pathlib import Path

# Bump these only when the upstream provider changes its output format in a
# way that breaks cached files (e.g. switching TTS or lip-sync model).
_AUDIO_CACHE_VERSION = "v1"
_VIDEO_CACHE_VERSION = "v1"


def audio_cache_key(
    text: str,
    voice_id: str,
    tempo: float = 1.0,
    stability: float = 0.5,
    similarity: float = 0.8,
    style: float = 0.3,
    regen_counter: int = 0,
) -> str:
    """Deterministic 16-char hex key for a TTS output."""
    h = hashlib.sha256()
    payload = (
        f"{_AUDIO_CACHE_VERSION}|{voice_id}|{tempo}|"
        f"{stability}|{similarity}|{style}|{regen_counter}|{text}"
    )
    h.update(payload.encode("utf-8"))
    return h.hexdigest()[:16]


def video_cache_key(audio_path: Path, image_path: Path) -> str:
    """Deterministic 16-char hex key for a lip-sync output.

    Hashes the actual bytes of audio + image so the cache stays correct even
    if those files were regenerated under the same name.
    """
    h = hashlib.sha256()
    h.update(_VIDEO_CACHE_VERSION.encode())
    h.update(b"|")
    h.update(Path(audio_path).read_bytes())
    h.update(b"|")
    h.update(Path(image_path).read_bytes())
    return h.hexdigest()[:16]
