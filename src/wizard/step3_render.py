"""Step 3 — Render + result.

Three sub-states (st.session_state.render_phase):
- "preflight": summary card + Generate button
- "running":   live progress per segment
- "done":      inline player + download + buttons
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import streamlit as st

from src.pipeline.episode import generate_tts, lipsync, concat
from src.wizard.state import (
    estimate_episode, safe_episode_slug, export_project_zip, go_to,
    auto_save,
)
from src.wizard.theme import PALETTE, pill
from src.wizard import creds, persistence
from src.wizard.errors import friendly_error


ROOT = Path(__file__).resolve().parent.parent.parent
EPISODES_DIR = ROOT / "episodes"


def render():
    if "render_phase" not in st.session_state:
        st.session_state.render_phase = "preflight"

    phase = st.session_state.render_phase
    if phase == "running":
        _render_running()
    elif phase == "done":
        _render_done()
    else:
        _render_preflight()


# --- Preflight ---------------------------------------------------------------

def _render_preflight():
    cast = st.session_state.cast
    segments = st.session_state.segments
    title = st.session_state.title.strip() or "Untitled"

    st.markdown("# Ready to render?")
    st.markdown(
        '<p class="wz-quiet">This takes about 5–10 minutes for a typical 30-second video. '
        'You can leave this tab open and check back.</p>',
        unsafe_allow_html=True,
    )

    # Summary card
    est = estimate_episode(segments)
    st.markdown(
        f'<div class="wz-card">'
        f'<h3 class="wz-serif" style="margin:0 0 0.4rem 0; font-size:1.4rem;">{title}</h3>'
        f'<p class="wz-quiet" style="margin:0;">'
        f'{len(cast)} character{"s" if len(cast) != 1 else ""} · '
        f'{est["segments"]} segment{"s" if est["segments"] != 1 else ""} · '
        f'{est["audio_secs"]:.0f}s of audio · '
        f'<strong style="color:{PALETTE["accent"]};">~${est["cost_usd"]:.2f}</strong>'
        f'</p>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Cast strip
    cols = st.columns(max(1, len(cast)))
    for col, char in zip(cols, cast.values()):
        with col:
            st.image(str(char.image_path), caption=char.display_name,
                     width="stretch")

    st.markdown('<div style="margin-top:1.5rem;"></div>', unsafe_allow_html=True)

    # Preflight: keys must be present in this user's session
    c = creds.read()
    missing = c.missing("fal", "elevenlabs")
    if missing:
        st.warning(
            f"Add **{', '.join(missing)}** key(s) in the Settings panel before rendering."
        )

    # Footer nav
    st.markdown('<div class="wz-footer"></div>', unsafe_allow_html=True)
    nav_back, _, nav_fwd = st.columns([1, 1, 1.5])

    with nav_back:
        if st.button("← Edit script", key="r_back", width="stretch"):
            go_to(2)
            st.rerun()

    with nav_fwd:
        if st.button(
            f"▶  Generate video  ·  ~${est['cost_usd']:.2f}",
            type="primary",
            disabled=bool(missing) or len(segments) == 0,
            width="stretch",
            key="r_generate",
        ):
            st.session_state.render_phase = "running"
            st.session_state.render_started_at = time.time()
            st.rerun()


# --- Running -----------------------------------------------------------------

def _render_running():
    cast = st.session_state.cast
    segments = st.session_state.segments
    title = st.session_state.title.strip() or "Untitled"
    slug = safe_episode_slug(title)
    episode_dir = EPISODES_DIR / slug

    st.markdown(f'# Generating *{title}*…')
    st.markdown(
        '<p class="wz-quiet">Don\'t refresh the page. You can switch to another tab — '
        'we\'ll keep working in the background.</p>',
        unsafe_allow_html=True,
    )

    # Per-segment placeholders
    seg_placeholders = []
    for i, seg in enumerate(segments):
        char = cast[seg["character"]]
        with st.container(border=True):
            row = st.columns([0.7, 4, 1.5])
            with row[0]:
                st.image(str(char.image_path), width="stretch")
            with row[1]:
                st.markdown(f"**{char.display_name}**")
                st.markdown(
                    f'<p class="wz-quiet" style="margin:0;">{seg["text"][:80]}'
                    f'{"…" if len(seg["text"]) > 80 else ""}</p>',
                    unsafe_allow_html=True,
                )
            with row[2]:
                seg_placeholders.append(st.empty())

    # Concat placeholder
    with st.container(border=True):
        cols = st.columns([4, 1.5])
        cols[0].markdown("**Stitching all segments together**")
        concat_placeholder = cols[1].empty()

    # Drive the async pipeline using a thread + asyncio queue. We periodically
    # snapshot the status dict and rerun until it's done. To keep this
    # implementation simple and Streamlit-idiomatic, we run the pipeline
    # synchronously here (Streamlit's exec model means each rerun blocks
    # this entire function — but that's fine because long-running awaits
    # are inside lipsync()). Streamlit's connection layer keeps the UI alive.

    # We use a shared dict that the cb writes to. Initial paint:
    for i in range(len(segments)):
        seg_placeholders[i].markdown(pill("queued", "queued"), unsafe_allow_html=True)
    concat_placeholder.markdown(pill("queued", "queued"), unsafe_allow_html=True)

    # Inline progress wrapper: we render once, then ask asyncio to run the
    # pipeline. Per-step UI updates happen via a callback that writes to a
    # placeholder. The placeholders are captured above so the callback can
    # reach them via closure.

    status_holder: dict = {}

    def render_status(i: int, status: str, msg: str = "", elapsed: float = 0):
        if status == "audio":
            label = f"🎙 Speech…"
            seg_placeholders[i].markdown(pill(label, "running"), unsafe_allow_html=True)
        elif status == "lipsync":
            secs_in = f"{elapsed:.0f}s" if elapsed else "starting"
            label = f"🎬 Lip-sync · {secs_in}"
            seg_placeholders[i].markdown(pill(label, "running"), unsafe_allow_html=True)
        elif status == "done":
            seg_placeholders[i].markdown(pill("✓ done", "done"), unsafe_allow_html=True)
        elif status == "error":
            seg_placeholders[i].markdown(pill(f"✗ {msg[:30]}", "error"),
                                         unsafe_allow_html=True)

    # Read this user's keys ONCE before the render starts. They're passed
    # explicitly into each pipeline call so a concurrent user can't race on
    # them via os.environ.
    c = creds.require("fal", "elevenlabs")

    # Inline async-await of the pipeline. Streamlit's render is paused
    # during this — but since lipsync() awaits real network I/O most of the
    # time, the runtime keeps the UI tab responsive.
    async def driver():
        for i, seg in enumerate(segments):
            char = cast[seg["character"]]
            seg_id = f"seg{i:02d}_{char.slug}"

            audio_dir = episode_dir / "audio"; audio_dir.mkdir(parents=True, exist_ok=True)
            video_dir = episode_dir / "videos"; video_dir.mkdir(parents=True, exist_ok=True)
            audio_path = audio_dir / f"{seg_id}.mp3"
            video_path = video_dir / f"{seg_id}.mp4"

            try:
                render_status(i, "audio")
                await generate_tts(
                    text=seg["text"], voice_id=char.voice.voice_id,
                    output_path=audio_path,
                    elevenlabs_api_key=c.elevenlabs,
                    stability=char.voice.stability, similarity=char.voice.similarity,
                    style=char.voice.style, tempo=char.voice.tempo,
                )

                render_status(i, "lipsync", elapsed=0)
                def cb(elapsed, msg, _i=i):
                    render_status(_i, "lipsync", msg=msg, elapsed=elapsed)
                await lipsync(
                    char.image_path, audio_path, video_path,
                    fal_key=c.fal, progress_cb=cb,
                )
                render_status(i, "done")
            except Exception as e:
                render_status(i, "error", msg=f"{type(e).__name__}")
                raise

        # Concat
        concat_placeholder.markdown(pill("⏳ stitching", "running"), unsafe_allow_html=True)
        final_path = episode_dir / "final.mp4"
        video_paths = [episode_dir / "videos" / f"seg{i:02d}_{cast[seg['character']].slug}.mp4"
                       for i, seg in enumerate(segments)]
        await concat(video_paths, final_path)
        concat_placeholder.markdown(pill("✓ done", "done"), unsafe_allow_html=True)

        return final_path

    # Capture pid + configured BEFORE the long asyncio.run() block. Streamlit
    # Cloud may roll/reconnect the session during a 2+ minute blocking call
    # and session_state can come back without project_id — that's how the
    # post-render auto_save silently lost step=3 + result.
    captured_pid = st.session_state.get("project_id")
    persistence_configured = persistence.is_configured()
    started_at = st.session_state.get("render_started_at", time.time())

    try:
        episode_dir.mkdir(parents=True, exist_ok=True)
        final_path = asyncio.run(driver())
        elapsed = time.time() - started_at

        # Upload the rendered video to Storage so it survives Streamlit Cloud's
        # disk wipe + lets recipients of the share-link play it without rerendering.
        video_storage_key = None
        if captured_pid and persistence_configured and final_path.exists():
            try:
                video_storage_key = persistence.upload_episode_video(
                    captured_pid, slug, final_path.read_bytes(),
                )
            except Exception as e:
                st.toast(f"Cloud upload failed: {type(e).__name__}", icon="⚠️")

        result_blob = {
            "elapsed": elapsed,
            "cost": estimate_episode(segments)["cost_usd"],
            "title": title,
            "slug": slug,
            "video_storage_key": video_storage_key,
        }

        st.session_state.result = result_blob
        st.session_state.render_phase = "done"
        st.session_state.step = 3
        # Restore project_id if Streamlit dropped it during the await.
        if captured_pid and not st.session_state.get("project_id"):
            st.session_state.project_id = captured_pid

        # Direct save using captured_pid — avoids relying on session_state
        # being intact after the long async block.
        if captured_pid and persistence_configured:
            try:
                n = persistence.save_state(
                    captured_pid,
                    step=3,
                    result=result_blob,
                )
                if n == 0:
                    persistence.upsert_state(
                        captured_pid,
                        step=3,
                        result=result_blob,
                    )
            except Exception:
                st.toast("Failed to persist render result to cloud", icon="⚠️")

        # Also call auto_save for the full state snapshot (cast, segments, …).
        auto_save()
        st.rerun()
    except Exception as e:
        st.error(f"**Render failed.** {friendly_error(e)}")
        nav = st.columns([1, 1, 1])
        with nav[0]:
            if st.button("← Edit script"):
                st.session_state.render_phase = "preflight"
                go_to(2)
                st.rerun()
        with nav[2]:
            if st.button("↻ Try again", type="primary"):
                st.session_state.render_phase = "preflight"
                st.rerun()


# --- Done -------------------------------------------------------------------

def _render_done():
    result = st.session_state.result or {}
    # Older saved rows may not have "title" in the result blob — fall back to
    # session_state.title (or "Untitled") so the Done page renders cleanly
    # instead of crashing on a missing key.
    title = (
        result.get("title")
        or (st.session_state.get("title") or "").strip()
        or "Untitled"
    )

    # Reconstruct the local path from the slug (cloud-portable) — older rows
    # stored an absolute "path" that's only valid on the rendering machine.
    slug = result.get("slug") or safe_episode_slug(title)
    final_path = EPISODES_DIR / slug / "final.mp4"

    # Cross-session resume: when a recipient opens the share-link, the local
    # disk doesn't have the rendered file. Pull it from Storage.
    if not final_path.exists() and persistence.is_configured():
        pid = st.session_state.get("project_id")
        if pid:
            data = persistence.download_episode_video(pid, slug)
            if data:
                final_path.parent.mkdir(parents=True, exist_ok=True)
                final_path.write_bytes(data)

    st.markdown(f'# *{title}* is ready')
    st.markdown(
        '<p class="wz-quiet">Watch it below. Download the MP4 to share, '
        'or export the project as a .zip to keep working on it later.</p>',
        unsafe_allow_html=True,
    )

    main, side = st.columns([2, 1])

    with main:
        if final_path.exists():
            st.video(str(final_path))
        else:
            st.error(f"Output missing: {final_path}")

    with side:
        # Older saved rows may not carry elapsed/cost — default rather than crash.
        elapsed = float(result.get("elapsed") or 0.0)
        cost = float(result.get("cost") or 0.0)
        st.markdown(
            f'<div class="wz-card">'
            f'<p class="wz-tiny" style="margin:0;">RENDERED IN</p>'
            f'<h2 style="margin:0;">{int(elapsed//60)}m {int(elapsed%60):02d}s</h2>'
            f'<p class="wz-tiny" style="margin:1rem 0 0 0;">SPENT</p>'
            f'<h2 style="margin:0;">~${cost:.2f}</h2>'
            f'</div>',
            unsafe_allow_html=True,
        )

        if final_path.exists():
            with open(final_path, "rb") as f:
                st.download_button(
                    "⬇  Download MP4",
                    data=f.read(),
                    file_name=f"{result.get('slug') or slug}.mp4",
                    mime="video/mp4",
                    type="primary",
                    width="stretch",
                    key="r_download_video",
                )

        # Export project zip (keep working on it later)
        zip_bytes = export_project_zip(
            title, st.session_state.cast, st.session_state.segments,
        )
        st.download_button(
            "📦  Export project (.zip)",
            data=zip_bytes,
            file_name=f"{result['slug']}.zip",
            mime="application/zip",
            width="stretch",
            key="r_download_zip",
        )

    st.divider()

    nav = st.columns([1, 1])
    with nav[0]:
        if st.button("← Edit script", key="done_back", width="stretch"):
            st.session_state.render_phase = "preflight"
            go_to(2)
            st.rerun()
    with nav[1]:
        if st.button("↻  Start a new project", width="stretch", key="done_new"):
            from src.wizard.state import reset_all
            reset_all()
            st.rerun()
