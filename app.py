"""Mind Video — wizard for end-to-end video creation.

Run locally:    streamlit run app.py
Deploy:         see README §3.1 (Streamlit Community Cloud)

Three steps: Cast → Script → Render. State lives in st.session_state and is
persisted-on-demand via the project-export .zip in the Settings drawer.
"""

import logging
import os
import sys
from pathlib import Path

# Surface module-level prints/logs in Streamlit Cloud's runtime panel.
log = logging.getLogger("mind-video")
logging.basicConfig(level=logging.INFO, format="%(asctime)s mind-video %(levelname)s %(message)s")

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
    log.info("gate enter pid=%r authed=%r configured=%r",
             pid, st.session_state.get("authed"), persistence.is_configured())
    if pid:
        if not persistence.is_configured():
            log.warning("gate: pid present but persistence is_configured()=False")
        else:
            try:
                row = persistence.load_project(pid)
                if row is not None:
                    log.info("gate: bypass OK for pid=%s", pid)
                    st.session_state.authed = True
                    return
                else:
                    log.warning("gate: load_project(%s) returned None", pid)
            except Exception:
                log.exception("gate: load_project(%s) raised", pid)

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

        # ── Recent projects in this session ────────────────────────────────
        recent = st.session_state.get("recent_projects") or []
        if persistence.is_configured() and len(recent) > 1:
            st.markdown("### Recent projects")
            cur = st.session_state.get("project_id")
            for r in recent[:6]:
                pid = r.get("id")
                title = (r.get("title") or "Untitled")[:30]
                is_current = (pid == cur)
                label = f"{'● ' if is_current else ''}{title}"
                if is_current:
                    st.markdown(
                        f'<p class="wz-tiny" style="margin:0.2rem 0; color:{PALETTE["accent"]};">'
                        f'{label} <span style="opacity:0.6;">· current</span></p>',
                        unsafe_allow_html=True,
                    )
                else:
                    if st.button(label, key=f"sb_recent_{pid}", width="stretch"):
                        st.query_params["p"] = pid
                        # Force re-hydration on next run
                        st.session_state._hydrated_from_url = False
                        st.rerun()
            st.markdown(
                '<p class="wz-tiny" style="margin-top:0.4rem;">'
                'Tip: bookmark project URLs to keep them across browser sessions.'
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
                    from src.wizard.state import go_to as _go_to, auto_save as _auto_save
                    _go_to(2 if segments else 1)
                    _auto_save()  # ensure full snapshot is persisted
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
            # Clear ?p= so the new project doesn't try to hydrate from an
            # old ID after reset.
            try:
                if "p" in st.query_params:
                    del st.query_params["p"]
            except Exception:
                pass
            reset_all()
            st.rerun()

        # Delete-project button — only meaningful when a cloud project exists
        if persistence.is_configured() and st.session_state.get("project_id"):
            with st.expander("⚠ Delete this project"):
                st.markdown(
                    '<p class="wz-tiny">'
                    "This permanently removes the project from the cloud, "
                    "including its character images and any rendered videos. "
                    "You'll be reset to a fresh blank project."
                    '</p>',
                    unsafe_allow_html=True,
                )
                confirm = st.text_input(
                    'Type DELETE to confirm',
                    key="sb_delete_confirm",
                    placeholder="DELETE",
                )
                if st.button(
                    "Delete permanently",
                    key="sb_delete_go",
                    disabled=(confirm.strip() != "DELETE"),
                    width="stretch",
                ):
                    pid = st.session_state.project_id
                    try:
                        persistence.delete_project(pid)
                        st.toast(f"Deleted project `{pid}`", icon="🗑️")
                    except Exception as e:
                        st.toast(f"Delete failed: {type(e).__name__}", icon="⚠️")
                    try:
                        if "p" in st.query_params:
                            del st.query_params["p"]
                    except Exception:
                        pass
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

# Debug endpoint — manually verify Supabase wiring + UPDATE permissions.
# Visit ?debug=verify to inspect a project row and probe whether UPDATE works.
def _debug_persistence():
    st.markdown("# Persistence diagnostic")
    pid = (st.query_params.get("p") or "").strip()
    st.write(f"**pid**: `{pid or '(none — add ?p=<id>)'}`")
    st.write(f"**persistence.is_configured()**: `{persistence.is_configured()}`")

    if not pid:
        st.info("Append `&p=<project-id>` to inspect a specific row.")
        return

    st.divider()
    st.markdown("### Current row")
    try:
        row = persistence.load_project(pid)
    except Exception as e:
        st.exception(e); return
    if row is None:
        st.warning("Row not found in DB.")
    else:
        st.json(row)

    st.divider()
    st.markdown("### Probe UPDATE permissions")
    st.markdown(
        '<p class="wz-quiet" style="font-size:0.85rem;">'
        "Sends <code>UPDATE projects SET step=999 WHERE id=&lt;pid&gt;</code>. "
        "If <strong>rows_returned == 0</strong>, the anon key cannot UPDATE the "
        "row — that's why state isn't persisting across sessions."
        '</p>',
        unsafe_allow_html=True,
    )
    if st.button("Run probe", type="primary", key="dbg_probe"):
        try:
            res = (
                persistence._client()
                .table("projects")
                .update({"step": 999})
                .eq("id", pid)
                .execute()
            )
            st.json({
                "rows_returned": len(res.data) if isinstance(res.data, list) else None,
                "data": res.data,
            })
        except Exception as e:
            st.exception(e)
        st.markdown("#### Re-read row after probe")
        try:
            row2 = persistence.load_project(pid)
            st.write(f"step now: {row2.get('step') if row2 else None}")
            st.json(row2 or {})
        except Exception as e:
            st.exception(e)


if (st.query_params.get("debug") or "") == "verify":
    _debug_persistence()
    st.stop()


_gate()
init_state()


# Cloud project hydration: if URL has ?p=<id>, load that project's state.
# Idempotent — only runs once per session, even on reruns.
def _hydrate_from_url():
    if st.session_state.get("_hydrated_from_url"):
        return
    pid = (st.query_params.get("p") or "").strip() if hasattr(st, "query_params") else ""
    log.info("hydrate_from_url pid=%r configured=%r",
             pid, persistence.is_configured())
    if not pid:
        st.session_state._hydrated_from_url = True
        return
    if not persistence.is_configured():
        log.warning("hydrate_from_url: persistence is_configured()=False; skipping")
        st.session_state._hydrated_from_url = True
        return
    try:
        ok = hydrate_from_project(pid)
    except Exception:
        log.exception("hydrate_from_url: hydrate_from_project(%s) raised", pid)
        ok = False
    if ok:
        log.info("hydrate_from_url: hydrated OK from pid=%s", pid)
        st.session_state._hydrated_from_url = True
    else:
        log.warning("hydrate_from_url: hydrate_from_project(%s) returned False; clearing ?p=", pid)
        # Project doesn't exist — clear the URL param so we don't get stuck
        try:
            del st.query_params["p"]
        except Exception:
            pass
        st.session_state._hydrated_from_url = True
        st.toast(f"Project `{pid}` not found", icon="⚠️")


_hydrate_from_url()
_settings_drawer()

# ---------------------------------------------------------------------------
# Share dialog — opens from a prominent header button when a project exists.
# Hides the "URL is buried in the sidebar" friction; gives the keys-toggle
# its own visual weight so people don't miss it.
# ---------------------------------------------------------------------------

@st.dialog("🔗 Share this project", width="large")
def _share_dialog():
    pid = st.session_state.get("project_id")
    if not pid:
        st.info(
            "Add a character or load the demo first — that creates the project "
            "in the cloud so we have a URL to share."
        )
        return

    base = "https://mind-video-play.streamlit.app"
    share_url = f"{base}/?p={pid}"

    st.markdown("**Send this URL to anyone you want to collaborate with:**")
    st.code(share_url, language=None)
    st.markdown(
        '<p class="wz-tiny">'
        "They'll land on the project's current state. Browser bookmarks work "
        "across full sessions. <em>Don't share with strangers — the URL is the "
        "only access token.</em>"
        "</p>",
        unsafe_allow_html=True,
    )

    st.divider()

    # Key handoff — make this VERY visible since it's the user's "PIs intact"
    # ask. Default OFF; opt-in only.
    current_share_keys = bool(st.session_state.get("share_keys", False))
    st.markdown(
        f'<div style="background:{("#3a2c1c" if current_share_keys else "#21242c")}; '
        f'border:1px solid {("#E8B14F" if current_share_keys else "#363B47")}; '
        f'border-radius:8px; padding:0.9rem 1rem; margin-bottom:0.6rem;">'
        f'<strong style="font-size:1rem;">'
        f'{"🔑 API keys are INCLUDED in this link" if current_share_keys else "🔒 API keys are NOT in this link"}'
        f'</strong><br>'
        f'<span class="wz-quiet" style="font-size:0.85rem;">'
        f'{("Recipients spend YOUR fal.ai / ElevenLabs balance. Only enable for people you trust." if current_share_keys else "Recipients will need to paste their own keys. Toggle on if you want them to use yours.")}'
        f'</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    new_share_keys = st.toggle(
        "Include my API keys in the link",
        value=current_share_keys,
        key="share_dialog_keys_toggle",
        help=(
            "OFF (default + safe): the recipient sees a Settings panel and "
            "must paste their own keys to render. "
            "ON: the keys are stored on the project row, and anyone who opens "
            "the link can spend YOUR fal.ai + ElevenLabs balance."
        ),
    )
    if new_share_keys != current_share_keys:
        st.session_state.share_keys = new_share_keys
        api_keys: dict = {}
        if new_share_keys:
            api_keys = {
                "fal": st.session_state.get("_key_FAL_KEY", "") or "",
                "elevenlabs": st.session_state.get("_key_ELEVENLABS_API_KEY", "") or "",
                "google": st.session_state.get("_key_GOOGLE_API_KEY", "") or "",
            }
            # Warn if the toggle is on but keys are empty — recipient gets nothing.
            empty = [k for k, v in api_keys.items() if not v]
            if empty:
                st.warning(
                    f"You toggled ON but these keys are empty in your session: "
                    f"**{', '.join(empty)}**. Open the Settings panel and paste them, "
                    "then re-toggle to push them to the share link."
                )
        try:
            persistence.save_state(
                pid, share_keys=new_share_keys, api_keys=api_keys,
            )
            st.toast(
                "Keys added to share link" if new_share_keys
                else "Keys removed from share link",
                icon="🔑" if new_share_keys else "✅",
            )
            st.rerun()
        except Exception as e:
            st.error(f"Couldn't update share settings: {type(e).__name__}: {e}")


# Header — Mind Video title + prominent Share button (when project exists)
has_project = bool(st.session_state.get("project_id"))
if has_project:
    header_left, header_right = st.columns([4, 1])
else:
    header_left, header_right = st.columns([5, 1])

with header_left:
    st.markdown(
        f'<h1 style="margin:0; font-size:1.4rem;">'
        f'🎬 <span style="color:{PALETTE["accent"]};">Mind</span> Video'
        f'</h1>',
        unsafe_allow_html=True,
    )
with header_right:
    if has_project:
        # Show whether keys are bundled at a glance
        share_state_icon = "🔑" if st.session_state.get("share_keys") else "🔗"
        if st.button(f"{share_state_icon}  Share project", key="hdr_share_btn",
                     width="stretch"):
            _share_dialog()
    else:
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
