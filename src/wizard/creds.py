"""Per-session credential reader for the wizard.

Reads API keys from `st.session_state` (which is per-browser-session) so
each user's keys stay isolated to their own session. Falls back to
environment variables for local CLI usage.

**Never writes to os.environ** — that was the source of cross-session
leakage on Streamlit Cloud where the same Python process serves all users.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import streamlit as st


# These keys mirror the input widget keys in app.py's settings drawer.
_FAL_SS = "_key_FAL_KEY"
_ELEVENLABS_SS = "_key_ELEVENLABS_API_KEY"
_GOOGLE_SS = "_key_GOOGLE_API_KEY"


@dataclass
class Credentials:
    fal: str = ""
    elevenlabs: str = ""
    google: str = ""

    def has(self, *names: str) -> bool:
        return all(bool(getattr(self, n)) for n in names)

    def missing(self, *names: str) -> list[str]:
        labels = {"fal": "fal.ai", "elevenlabs": "ElevenLabs", "google": "Google AI"}
        return [labels[n] for n in names if not getattr(self, n)]


def read() -> Credentials:
    """Read keys for the current browser session (with env fallback for CLI).

    Strips whitespace defensively — copy-paste from emails / password
    managers / docs frequently grabs trailing newlines or spaces, and the
    API providers reject those as 401 Unauthorized.
    """
    s = st.session_state
    def _clean(v: str) -> str:
        return (v or "").strip()
    return Credentials(
        fal=_clean(s.get(_FAL_SS)) or _clean(os.environ.get("FAL_KEY")) or _clean(os.environ.get("FAL_API_KEY")),
        elevenlabs=_clean(s.get(_ELEVENLABS_SS)) or _clean(os.environ.get("ELEVENLABS_API_KEY")),
        google=_clean(s.get(_GOOGLE_SS)) or _clean(os.environ.get("GOOGLE_API_KEY")),
    )


def require(*names: str) -> Credentials:
    """Read creds and raise a friendly RuntimeError if any required key is missing."""
    creds = read()
    missing = creds.missing(*names)
    if missing:
        raise RuntimeError(
            f"Missing API key(s): {', '.join(missing)}. "
            "Add them in the Settings panel on the left."
        )
    return creds
