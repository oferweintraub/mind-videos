"""Step 3 — Render + result.

Sub-phases (st.session_state.render_phase):
- "preflight": summary card + Generate button
- "audio":     run TTS for any segment whose hash-keyed file is missing
               (cache hits for anything pre-generated on Step 2), then
               auto-advance to lipsync
- "lipsync":   live progress while VEED renders each segment + concat
- "done":      inline player + download + buttons
- "refine":    post-render per-segment regen (audio + lipsync)

Audio + video files are cached by content hash (see pipeline/cache_keys.py)
so changing one segment doesn't bust the others — fixes the "fix one
pronunciation, lose another" complaint with eleven_v3's non-determinism.

Per-segment audio preview lives on Step 2 (the Script page) — see
step2_script.py. That's why there's no in-step-3 "review" phase anymore.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import streamlit as st

from src.pipeline.episode import generate_tts, lipsync, concat
from src.pipeline.cache_keys import video_cache_key
from src.wizard.state import (
    estimate_episode, safe_episode_slug, export_project_zip, go_to,
    auto_save, episode_dir as _episode_dir, audio_path_for_segment as _audio_path_for,
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
    # "review" is a legacy phase value from earlier code; saved sessions on
    # it should jump straight to lipsync (audio is already there) rather than
    # back to preflight.
    if phase == "review":
        st.session_state.render_phase = "lipsync"
        st.session_state.render_started_at = time.time()
        phase = "lipsync"
    if phase == "audio":
        _render_audio_phase()
    elif phase == "lipsync":
        _render_lipsync_phase()
    elif phase == "refine":
        _render_refine_phase()
    elif phase == "done":
        _render_done()
    else:
        _render_preflight()


# --- Path helpers ------------------------------------------------------------
# _episode_dir() and _audio_path_for() are imported from state.py so step2
# (per-segment audio gen) and step3 (audio/lipsync/refine) share the same
# hash-keyed cache layout.


def _video_path_for(i: int) -> Path | None:
    """Content-hash-derived video path for segment i. Returns None if the
    audio doesn't exist yet (the video hash includes audio bytes)."""
    segments = st.session_state.segments
    cast = st.session_state.cast
    seg = segments[i]
    char = cast[seg["character"]]
    audio_path = _audio_path_for(i)
    if not audio_path.exists():
        return None
    counters = st.session_state.get("seg_lipsync_counter") or {}
    key = video_cache_key(
        audio_path, char.image_path,
        regen_counter=int(counters.get(str(i), 0)),
    )
    return _episode_dir() / "videos" / f"{key}.mp4"


# --- Preflight ---------------------------------------------------------------

def _render_preflight():
    cast = st.session_state.cast
    segments = st.session_state.segments
    title = st.session_state.title.strip() or "Untitled"

    st.markdown("# Ready to render?")
    st.markdown(
        '<p class="wz-quiet">Generates any audio you haven\'t already previewed '
        'on Step 2, then runs lip-sync and stitches the final video. Anything you '
        'pre-generated on the Script page is a cache hit — no double-pay.</p>',
        unsafe_allow_html=True,
    )

    est = estimate_episode(segments)
    st.markdown(
        f'<div class="wz-card">'
        f'<h3 class="wz-serif" style="margin:0 0 0.4rem 0; font-size:1.4rem;">{title}</h3>'
        f'<p class="wz-quiet" style="margin:0;">'
        f'{len(cast)} character{"s" if len(cast) != 1 else ""} · '
        f'{est["segments"]} segment{"s" if est["segments"] != 1 else ""} · '
        f'{est["audio_secs"]:.0f}s of audio · '
        f'<strong style="color:{PALETTE["accent"]};">~${est["cost_usd"]:.2f}</strong> at lip-sync'
        f'</p>'
        f'</div>',
        unsafe_allow_html=True,
    )

    cols = st.columns(max(1, len(cast)))
    for col, char in zip(cols, cast.values()):
        with col:
            st.image(str(char.image_path), caption=char.display_name,
                     width="stretch")

    st.markdown('<div style="margin-top:1.5rem;"></div>', unsafe_allow_html=True)

    c = creds.read()
    missing = c.missing("fal", "elevenlabs")
    if missing:
        st.warning(
            f"Add **{', '.join(missing)}** key(s) in the Settings panel before rendering."
        )

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
            st.session_state.render_phase = "audio"
            st.session_state.render_started_at = time.time()
            st.rerun()


# --- Audio phase -------------------------------------------------------------

def _render_audio_phase():
    cast = st.session_state.cast
    segments = st.session_state.segments
    title = st.session_state.title.strip() or "Untitled"
    episode_dir = _episode_dir()

    st.markdown(f'# Generating audio for *{title}*…')
    st.markdown(
        '<p class="wz-quiet">Fast part — anything you previewed on Step 2 is a cache hit; only new/edited segments run TTS.</p>',
        unsafe_allow_html=True,
    )

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

    for i in range(len(segments)):
        seg_placeholders[i].markdown(pill("queued", "queued"), unsafe_allow_html=True)

    c = creds.require("elevenlabs")
    audio_dir = episode_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    async def driver():
        paths: dict[str, str] = {}
        for i, seg in enumerate(segments):
            char = cast[seg["character"]]
            audio_path = _audio_path_for(i)
            paths[str(i)] = str(audio_path)

            if audio_path.exists():
                seg_placeholders[i].markdown(pill("✓ cached", "done"),
                                             unsafe_allow_html=True)
                continue

            seg_placeholders[i].markdown(pill("🎙 generating", "running"),
                                         unsafe_allow_html=True)
            try:
                await generate_tts(
                    text=seg["text"], voice_id=char.voice.voice_id,
                    output_path=audio_path,
                    elevenlabs_api_key=c.elevenlabs,
                    stability=char.voice.stability, similarity=char.voice.similarity,
                    style=char.voice.style, tempo=char.voice.tempo,
                )
                seg_placeholders[i].markdown(pill("✓ done", "done"),
                                             unsafe_allow_html=True)
            except Exception as e:
                seg_placeholders[i].markdown(
                    pill(f"✗ {type(e).__name__}", "error"),
                    unsafe_allow_html=True,
                )
                raise
        return paths

    try:
        episode_dir.mkdir(parents=True, exist_ok=True)
        audio_paths = asyncio.run(driver())
        st.session_state.seg_audio_paths = audio_paths
        # Skip the (removed) review page; user already iterated on Step 2.
        # Keep render_started_at as it was set at preflight so the Done page
        # reports correct total elapsed wall-clock for the full render.
        st.session_state.render_phase = "lipsync"
        st.rerun()
    except Exception as e:
        st.error(f"**Audio generation failed.** {friendly_error(e)}")
        if st.button("← Back to preflight"):
            st.session_state.render_phase = "preflight"
            st.rerun()


def _clear_refine_text_keys() -> None:
    """Drop all `refine_text_*` session_state keys. Streamlit's controlled
    components persist by key, so leaving them around would shadow a
    programmatic update to segments[i].text (e.g. an edit the user made on
    step 2 after navigating back from refine)."""
    stale = [k for k in list(st.session_state.keys())
             if isinstance(k, str) and k.startswith("refine_text_")]
    for k in stale:
        del st.session_state[k]


# --- Lipsync phase -----------------------------------------------------------

def _render_lipsync_phase():
    cast = st.session_state.cast
    segments = st.session_state.segments
    title = st.session_state.title.strip() or "Untitled"
    slug = safe_episode_slug(title)
    episode_dir = _episode_dir()
    audio_paths = st.session_state.get("seg_audio_paths") or {}

    st.markdown(f'# Rendering *{title}*…')
    st.markdown(
        '<p class="wz-quiet">Lip-syncing each clip. You can switch tabs — '
        'we keep working in the background.</p>',
        unsafe_allow_html=True,
    )

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

    with st.container(border=True):
        cols = st.columns([4, 1.5])
        cols[0].markdown("**Stitching all segments together**")
        concat_placeholder = cols[1].empty()

    for i in range(len(segments)):
        seg_placeholders[i].markdown(pill("queued", "queued"),
                                     unsafe_allow_html=True)
    concat_placeholder.markdown(pill("queued", "queued"),
                                unsafe_allow_html=True)

    def render_status(i, status, msg="", elapsed=0):
        if status == "running":
            secs_in = f"{elapsed:.0f}s" if elapsed else "starting"
            label = f"🎬 Lip-sync · {secs_in}"
            seg_placeholders[i].markdown(pill(label, "running"),
                                         unsafe_allow_html=True)
        elif status == "cached":
            seg_placeholders[i].markdown(pill("✓ cached", "done"),
                                         unsafe_allow_html=True)
        elif status == "done":
            seg_placeholders[i].markdown(pill("✓ done", "done"),
                                         unsafe_allow_html=True)
        elif status == "error":
            seg_placeholders[i].markdown(pill(f"✗ {msg[:30]}", "error"),
                                         unsafe_allow_html=True)

    c = creds.require("fal", "elevenlabs")

    video_dir = episode_dir / "videos"
    video_dir.mkdir(parents=True, exist_ok=True)

    async def driver():
        video_paths: list[Path] = []
        for i, seg in enumerate(segments):
            char = cast[seg["character"]]
            audio_path = Path(audio_paths.get(str(i), ""))
            if not audio_path.exists():
                # User must have hit reload between phases; restart audio.
                raise RuntimeError(
                    f"Audio for segment #{i+1} is missing. "
                    "Go back and regenerate audio."
                )

            lipsync_counters = st.session_state.get("seg_lipsync_counter") or {}
            video_key = video_cache_key(
                audio_path, char.image_path,
                regen_counter=int(lipsync_counters.get(str(i), 0)),
            )
            video_path = video_dir / f"{video_key}.mp4"
            video_paths.append(video_path)

            if video_path.exists():
                render_status(i, "cached")
                continue

            try:
                render_status(i, "running", elapsed=0)
                def cb(elapsed, msg, _i=i):
                    render_status(_i, "running", msg=msg, elapsed=elapsed)
                await lipsync(
                    char.image_path, audio_path, video_path,
                    fal_key=c.fal, progress_cb=cb,
                )
                render_status(i, "done")
            except Exception as e:
                render_status(i, "error", msg=f"{type(e).__name__}")
                raise

        concat_placeholder.markdown(pill("⏳ stitching", "running"),
                                    unsafe_allow_html=True)
        final_path = episode_dir / "final.mp4"
        # Always rebuild final.mp4 — segment order or text may have changed
        # since the last concat, so the cached final.mp4 is unsafe to reuse.
        if final_path.exists():
            final_path.unlink()
        await concat(video_paths, final_path)
        concat_placeholder.markdown(pill("✓ done", "done"),
                                    unsafe_allow_html=True)
        return final_path

    captured_pid = st.session_state.get("project_id")
    persistence_configured = persistence.is_configured()
    started_at = st.session_state.get("render_started_at", time.time())

    try:
        episode_dir.mkdir(parents=True, exist_ok=True)
        final_path = asyncio.run(driver())
        elapsed = time.time() - started_at

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
        if captured_pid and not st.session_state.get("project_id"):
            st.session_state.project_id = captured_pid

        if captured_pid and persistence_configured:
            try:
                n = persistence.save_state(
                    captured_pid, step=3, result=result_blob,
                )
                if n == 0:
                    persistence.upsert_state(
                        captured_pid, step=3, result=result_blob,
                    )
            except Exception:
                st.toast("Failed to persist render result to cloud", icon="⚠️")

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


# --- Refine phase (per-segment post-render iteration) -----------------------

def _do_refine_one_segment(i: int) -> None:
    """Run TTS (if needed) + lip-sync (if needed) for segment i, then re-concat
    final.mp4 from all segments' current cached videos. Called when a refine-
    page Regenerate button is clicked.

    Counter bumps happen at the button site BEFORE calling this — by the
    time we land here, _audio_path_for / _video_path_for already reflect the
    new desired hash, and the corresponding old file is orphaned on disk.
    """
    segments = st.session_state.segments
    cast = st.session_state.cast
    title = st.session_state.title.strip() or "Untitled"
    slug = safe_episode_slug(title)
    episode_dir = _episode_dir()
    audio_dir = episode_dir / "audio"
    video_dir = episode_dir / "videos"
    audio_dir.mkdir(parents=True, exist_ok=True)
    video_dir.mkdir(parents=True, exist_ok=True)

    c = creds.require("fal", "elevenlabs")
    char = cast[segments[i]["character"]]
    audio_path = _audio_path_for(i)

    async def work():
        if not audio_path.exists():
            await generate_tts(
                text=segments[i]["text"], voice_id=char.voice.voice_id,
                output_path=audio_path,
                elevenlabs_api_key=c.elevenlabs,
                stability=char.voice.stability,
                similarity=char.voice.similarity,
                style=char.voice.style, tempo=char.voice.tempo,
            )
        # video path depends on audio bytes, so it can only be computed now
        video_path = _video_path_for(i)
        if video_path is None:
            raise RuntimeError("Audio missing after generation — bug?")
        if not video_path.exists():
            await lipsync(char.image_path, audio_path, video_path,
                          fal_key=c.fal)

        # Keep seg_audio_paths in sync so other pages can play this audio
        audio_paths = dict(st.session_state.get("seg_audio_paths") or {})
        audio_paths[str(i)] = str(audio_path)
        st.session_state.seg_audio_paths = audio_paths

        # Re-concat from current cached paths for every segment. Streamlit
        # Cloud wipes the ephemeral disk on container restart (only final.mp4
        # is stored in Supabase), so OTHER segments' audio/video files may
        # be gone even though the project itself is healthy. Regenerate
        # anything missing using each segment's CURRENT counter values, so
        # the recovered files match what the user last approved as content.
        # (V3 is non-deterministic so the new take won't sound bit-identical
        # to the lost original, but it's the same approved text + settings.)
        all_videos: list[Path] = []
        recovered: list[int] = []
        for j in range(len(segments)):
            vp = _video_path_for(j)
            if vp is not None and vp.exists():
                all_videos.append(vp)
                continue

            # Need to recover. Generate audio if missing, then lipsync.
            j_char = cast[segments[j]["character"]]
            j_audio = _audio_path_for(j)
            if not j_audio.exists():
                await generate_tts(
                    text=segments[j]["text"],
                    voice_id=j_char.voice.voice_id,
                    output_path=j_audio,
                    elevenlabs_api_key=c.elevenlabs,
                    stability=j_char.voice.stability,
                    similarity=j_char.voice.similarity,
                    style=j_char.voice.style, tempo=j_char.voice.tempo,
                )
            j_video = _video_path_for(j)
            if j_video is None:
                raise RuntimeError(
                    f"Segment #{j+1}: audio missing after recovery — bug?"
                )
            if not j_video.exists():
                await lipsync(
                    j_char.image_path, j_audio, j_video, fal_key=c.fal,
                )
            all_videos.append(j_video)
            if j != i:
                recovered.append(j + 1)  # 1-indexed for the user-facing toast

        if recovered:
            st.toast(
                "Restored segment(s) "
                + ", ".join(f"#{n}" for n in recovered)
                + " from cache (deploy restart wiped local files)",
                icon="♻️",
            )

        final_path = episode_dir / "final.mp4"
        if final_path.exists():
            final_path.unlink()
        await concat(all_videos, final_path)

        # Push the new final.mp4 to storage so the share-link recipient sees it
        captured_pid = st.session_state.get("project_id")
        if captured_pid and persistence.is_configured() and final_path.exists():
            try:
                video_storage_key = persistence.upload_episode_video(
                    captured_pid, slug, final_path.read_bytes(),
                )
                result = dict(st.session_state.get("result") or {})
                result["video_storage_key"] = video_storage_key
                st.session_state.result = result
            except Exception as e:
                st.toast(f"Cloud upload failed: {type(e).__name__}",
                         icon="⚠️")

    asyncio.run(work())
    auto_save()


def _render_refine_phase():
    cast = st.session_state.cast
    segments = st.session_state.segments
    title = st.session_state.title.strip() or "Untitled"
    episode_dir = _episode_dir()
    audio_counters = st.session_state.get("seg_regen_counter") or {}
    lipsync_counters = st.session_state.get("seg_lipsync_counter") or {}

    final_path = episode_dir / "final.mp4"

    st.markdown(f'# Refine *{title}*')
    st.markdown(
        '<p class="wz-quiet">Each segment shows its current audio + lip-sync. '
        '<strong>You can edit the text</strong> inline and hit 🔄 New audio take — '
        'text changes auto-bust the cache. Other segments stay cached, so it\'s '
        'fast and cheap.<br/>'
        '<strong>💡 Stubborn word?</strong> Type it with niqqud — e.g. '
        '<code>חַסְקָה</code> instead of <code>חסקה</code>. eleven_v3 reads '
        'Hebrew vowel marks and pronounces accordingly.</p>',
        unsafe_allow_html=True,
    )

    if final_path.exists():
        with st.expander("▶  Watch current final video", expanded=False):
            st.video(str(final_path))

    for i, seg in enumerate(segments):
        char = cast.get(seg["character"])
        if char is None:
            continue
        audio_path = _audio_path_for(i)
        video_path = _video_path_for(i)
        with st.container(border=True):
            row = st.columns([0.6, 3.2, 1.8, 1.6])
            with row[0]:
                st.image(str(char.image_path), width="stretch")
            with row[1]:
                st.markdown(f"**{char.display_name}**")
                edited_text = st.text_area(
                    label="segment text",
                    label_visibility="collapsed",
                    value=seg["text"],
                    key=f"refine_text_{i}",
                    height=80,
                )
                if edited_text != seg["text"]:
                    segments[i] = {**seg, "text": edited_text}
                if audio_path.exists():
                    st.audio(str(audio_path))
                else:
                    st.warning("Audio missing — hit New audio take")
            with row[2]:
                if video_path and video_path.exists():
                    st.video(str(video_path))
                else:
                    st.markdown(
                        '<p class="wz-quiet">no video yet — regenerate</p>',
                        unsafe_allow_html=True,
                    )
            with row[3]:
                a_attempts = int(audio_counters.get(str(i), 0))
                v_attempts = int(lipsync_counters.get(str(i), 0))
                a_label = "🔄 New audio take"
                if a_attempts > 0:
                    a_label += f"  ·  #{a_attempts + 1}"
                if st.button(a_label, key=f"refine_audio_{i}",
                             width="stretch",
                             help="Regenerate the speech audio (also re-runs lip-sync since audio changed). Edit the text above first to fix pronunciation."):
                    # Read text_area in case the user just edited it. Text
                    # change alone busts the audio hash; only bump the counter
                    # if the text was left as-is.
                    fresh_text = st.session_state.get(
                        f"refine_text_{i}", seg["text"]
                    )
                    text_changed = fresh_text != seg["text"]
                    if text_changed:
                        segments[i] = {**seg, "text": fresh_text}
                    else:
                        new_counters = dict(audio_counters)
                        new_counters[str(i)] = a_attempts + 1
                        st.session_state.seg_regen_counter = new_counters
                    try:
                        with st.spinner(f"Regenerating segment #{i+1}…"):
                            _do_refine_one_segment(i)
                    except Exception as e:
                        st.error(f"Regen failed: {friendly_error(e)}")
                    else:
                        st.rerun()

                v_label = "🎬 New lip-sync take"
                if v_attempts > 0:
                    v_label += f"  ·  #{v_attempts + 1}"
                v_disabled = not (audio_path.exists())
                if st.button(v_label, key=f"refine_lipsync_{i}",
                             width="stretch", disabled=v_disabled,
                             help="Regenerate just the lip-sync video. Audio stays the same."):
                    new_counters = dict(lipsync_counters)
                    new_counters[str(i)] = v_attempts + 1
                    st.session_state.seg_lipsync_counter = new_counters
                    try:
                        with st.spinner(f"Lip-syncing segment #{i+1} (~30–60s)…"):
                            _do_refine_one_segment(i)
                    except Exception as e:
                        st.error(f"Regen failed: {friendly_error(e)}")
                    else:
                        st.rerun()

    st.markdown('<div class="wz-footer"></div>', unsafe_allow_html=True)
    nav = st.columns([1, 1, 1])
    with nav[0]:
        if st.button("← Back to final", key="refine_back", width="stretch"):
            _clear_refine_text_keys()
            st.session_state.render_phase = "done"
            st.rerun()
    with nav[2]:
        if st.button("↻  Re-render everything", key="refine_full",
                     width="stretch",
                     help="Skip the cache and regenerate every segment from scratch"):
            _clear_refine_text_keys()
            st.session_state.render_phase = "preflight"
            st.rerun()


# --- Done -------------------------------------------------------------------

def _render_done():
    result = st.session_state.result or {}
    title = (
        result.get("title")
        or (st.session_state.get("title") or "").strip()
        or "Untitled"
    )

    slug = result.get("slug") or safe_episode_slug(title)
    pid_done = st.session_state.get("project_id") or "local"
    final_path = EPISODES_DIR / pid_done / slug / "final.mp4"

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

        zip_bytes = export_project_zip(
            title, st.session_state.cast, st.session_state.segments,
        )
        st.download_button(
            "📦  Export project (.zip)",
            data=zip_bytes,
            file_name=f"{result.get('slug') or slug}.zip",
            mime="application/zip",
            width="stretch",
            key="r_download_zip",
        )

    st.divider()

    nav = st.columns([1, 1, 1])
    with nav[0]:
        if st.button("← Edit script", key="done_back", width="stretch"):
            st.session_state.render_phase = "preflight"
            go_to(2)
            st.rerun()
    with nav[1]:
        if st.button("🔄  Refine segments", key="done_refine",
                     width="stretch",
                     help="Per-segment audio + lip-sync regeneration. Other segments stay cached."):
            st.session_state.render_phase = "refine"
            st.rerun()
    with nav[2]:
        if st.button("↻  Start a new project", width="stretch",
                     key="done_new"):
            from src.wizard.state import reset_all
            reset_all()
            st.rerun()
