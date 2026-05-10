"""Mind Video — wizard for end-to-end video creation.

Run locally:    streamlit run app.py
Deploy:         see README §3.1 (Streamlit Community Cloud)

Three steps: Cast → Script → Render. State lives in st.session_state and is
persisted-on-demand via the project-export .zip in the Settings drawer.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

import streamlit as st
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from src.wizard.theme import apply_theme, step_indicator, PALETTE
from src.wizard.state import (
    init_state, reset_all, import_project_zip, export_project_zip,
    hydrate_from_project,
)
from src.wizard import step1_cast, step2_script, step3_render
from src.wizard import persistence


# ---------------------------------------------------------------------------
# Page config + theme
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Mind Video",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_theme()


# ---------------------------------------------------------------------------
# Auth gate (shared password — only enforced when APP_PASSWORD is set)
# ---------------------------------------------------------------------------

def _expected_password():
    try:
        return st.secrets["APP_PASSWORD"]
    except Exception:
        return os.environ.get("APP_PASSWORD")


def _gate():
    expected = _expected_password()
    if not expected or st.session_state.get("authed"):
        return

    # If the URL carries a valid project ID, that IS the access token —
    # skip the password gate. The project_id is unguessable (72 bits) and
    # users explicitly share it with collaborators. Same trust model as
    # Excalidraw / Figma share links.
    pid = (st.query_params.get("p") or "").strip() if hasattr(st, "query_params") else ""
    if pid and persistence.is_configured():
        try:
            if persistence.load_project(pid) is not None:
                st.session_state.authed = True
                return
        except Exception:
            pass  # fall through to password gate

    st.markdown(
        f'<div style="max-width:380px; margin: 8vh auto 0 auto;">',
        unsafe_allow_html=True,
    )
    st.markdown("# 🎬 Mind Video")
    st.markdown(
        '<p class="wz-quiet">Enter the password your collaborator gave you.</p>',
        unsafe_allow_html=True,
    )
    pw = st.text_input("Password", type="password", label_visibility="collapsed")
    if st.button("Enter", type="primary", disabled=not pw, width="stretch"):
        if pw == expected:
            st.session_state.authed = True
            st.rerun()
        else:
            st.error("Wrong password")
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()


# ---------------------------------------------------------------------------
# Settings drawer (sidebar) — API keys + project import/export
# ---------------------------------------------------------------------------

def _settings_drawer():
    with st.sidebar:
        st.markdown("## Settings")

        st.markdown("### API keys")
        st.markdown(
            '<p class="wz-quiet" style="font-size:0.8rem;">'
            'Your keys stay in this browser session — they\'re not logged or stored.'
            '</p>',
            unsafe_allow_html=True,
        )
        # Keys are stored in session_state (per-browser-session), never
        # written to os.environ — that would leak across users on Streamlit
        # Cloud's shared-process model.
        for k, label, link in [
            ("FAL_KEY",            "fal.ai (lip-sync)",   "https://fal.ai/dashboard/keys"),
            ("ELEVENLABS_API_KEY", "ElevenLabs (voice)",  "https://elevenlabs.io/app/settings/api-keys"),
            ("GOOGLE_API_KEY",     "Google AI (images)",  "https://aistudio.google.com/app/apikey"),
        ]:
            st.text_input(
                label,
                type="password",
                key=f"_key_{k}",
                help=f"Get key: {link}",
            )

        st.markdown(
            '<p class="wz-tiny" style="margin-top:0.6rem;">'
            'Tier reminders: fal.ai needs paid balance. ElevenLabs needs Creator+ '
            'for Hebrew. Google AI free tier is fine.'
            '</p>',
            unsafe_allow_html=True,
        )

        # ── Share link (Phase 2: cloud-backed projects) ───────────────────
        if persistence.is_configured() and (
            st.session_state.get("cast") or st.session_state.get("segments")
        ):
            st.markdown("### Share")
            pid = st.session_state.get("project_id")
            if pid:
                base = "https://mind-video-play.streamlit.app"
                share_url = f"{base}/?p={pid}"
                st.markdown(
                    '<p class="wz-quiet" style="font-size:0.82rem;">'
                    'Anyone with this URL can open this project and continue '
                    "where you left off. Don't share with strangers."
                    '</p>',
                    unsafe_allow_html=True,
                )
                st.code(share_url, language=None)

                # Optional: include the original creator's API keys in the row
                # so the recipient inherits them. Default OFF — recipient
                # normally has to bring their own keys.
                share_keys_now = st.checkbox(
                    "Include my API keys in the link",
                    value=bool(st.session_state.get("share_keys", False)),
                    help=(
                        "Off (recommended): recipient pastes their own keys. "
                        "On: recipient inherits yours — they spend YOUR "
                        "fal.ai / ElevenLabs balance. Use only with people "
                        "you trust."
                    ),
                    key="sb_share_keys_toggle",
                )
                # Persist the toggle + keys (or null them out) to the row
                if share_keys_now != st.session_state.get("share_keys", False):
                    st.session_state.share_keys = share_keys_now
                    api_keys = None
                    if share_keys_now:
                        api_keys = {
                            "fal": st.session_state.get("_key_FAL_KEY", "") or "",
                            "elevenlabs": st.session_state.get("_key_ELEVENLABS_API_KEY", "") or "",
                            "google": st.session_state.get("_key_GOOGLE_API_KEY", "") or "",
                        }
                    else:
                        api_keys = {}  # explicit clear (jsonb null gets weird)
                    try:
                        persistence.save_state(
                            pid, share_keys=share_keys_now, api_keys=api_keys,
                        )
                        st.toast(
                            "Keys included in share link"
                            if share_keys_now
                            else "Keys cleared from share link",
                            icon="🔑" if share_keys_now else "✅",
                        )
                    except Exception as e:
                        st.toast(f"Couldn't update share settings: {type(e).__name__}", icon="⚠️")
            else:
                st.markdown(
                    '<p class="wz-tiny">Add a character or load the demo to '
                    'get a shareable URL.</p>',
                    unsafe_allow_html=True,
                )

        st.markdown("### Project")

        # Export current project as .zip — only meaningful if there's something
        if st.session_state.get("cast") or st.session_state.get("segments"):
            zip_bytes = export_project_zip(
                st.session_state.title,
                st.session_state.cast,
                st.session_state.segments,
            )
            st.download_button(
                "⬇ Export as .zip",
                data=zip_bytes,
                file_name="mind_video_project.zip",
                mime="application/zip",
                width="stretch",
                key="sb_export",
            )

        # Import a previously-exported .zip
        uploaded = st.file_uploader(
            "Import a project",
            type=["zip"],
            label_visibility="visible",
            key="sb_import",
        )
        if uploaded is not None:
            marker = (uploaded.name, uploaded.size)
            if st.session_state.get("loaded_zip_marker") != marker:
                try:
                    cast, segments, title = import_project_zip(
                        uploaded.read(), characters_root=ROOT / "characters",
                    )
                    st.session_state.cast = cast
                    st.session_state.segments = segments
                    st.session_state.title = title
                    st.session_state.loaded_zip_marker = marker
                    st.session_state.step = 2 if segments else 1
                    st.toast(
                        f"Loaded {len(cast)} character(s) and "
                        f"{len(segments)} segment(s)",
                        icon="📦",
                    )
                    st.rerun()
                except Exception as e:
                    st.error(f"Couldn't load that .zip: {type(e).__name__}: {e}")

        st.markdown("### Reset")
        if st.button("↻ Start a new project", key="sb_reset",
                     width="stretch"):
            reset_all()
            st.rerun()

        if _expected_password() and st.session_state.get("authed"):
            st.divider()
            if st.button("Sign out", key="sb_signout", width="stretch"):
                for k in list(st.session_state.keys()):
                    del st.session_state[k]
                st.rerun()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

_gate()
init_state()


# Cloud project hydration: if URL has ?p=<id>, load that project's state.
# Idempotent — only runs once per session, even on reruns.
def _hydrate_from_url():
    if st.session_state.get("_hydrated_from_url"):
        return
    pid = (st.query_params.get("p") or "").strip() if hasattr(st, "query_params") else ""
    if not pid:
        st.session_state._hydrated_from_url = True
        return
    if not persistence.is_configured():
        st.session_state._hydrated_from_url = True
        return
    if hydrate_from_project(pid):
        st.session_state._hydrated_from_url = True
    else:
        # Project doesn't exist — clear the URL param so we don't get stuck
        try:
            del st.query_params["p"]
        except Exception:
            pass
        st.session_state._hydrated_from_url = True
        st.toast(f"Project `{pid}` not found", icon="⚠️")


_hydrate_from_url()
_settings_drawer()

# Header
header_left, header_right = st.columns([5, 1])
with header_left:
    st.markdown(
        f'<h1 style="margin:0; font-size:1.4rem;">'
        f'🎬 <span style="color:{PALETTE["accent"]};">Mind</span> Video'
        f'</h1>',
        unsafe_allow_html=True,
    )
with header_right:
    st.markdown(
        '<p class="wz-tiny" style="text-align:right; margin:0;">'
        'Hebrew animated videos · '
        '<span style="color:#E8B14F;">add your API keys ←</span> '
        'in the Settings panel'
        '</p>',
        unsafe_allow_html=True,
    )

# Step indicator
step_indicator(st.session_state.step, ["Cast", "Script", "Render"])

# Route to the right step
step = st.session_state.step
if step == 1:
    step1_cast.render()
elif step == 2:
    step2_script.render()
elif step == 3:
    step3_render.render()
else:
    st.error(f"Unknown step: {step}")
    st.session_state.step = 1
