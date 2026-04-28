"""Mind Video — local Streamlit UI for episode generation.

Run with:  streamlit run app.py
"""

import asyncio
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

import streamlit as st
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from src.pipeline.episode import generate_tts, lipsync, concat

st.set_page_config(page_title="Mind Video", page_icon="🎬", layout="wide")

st.markdown(
    """<style>
       textarea { direction: rtl; text-align: right; font-family: Arial, sans-serif; font-size: 16px; }
       div[data-testid="stImage"] img { border-radius: 8px; }
    </style>""",
    unsafe_allow_html=True,
)

# --- Cast (pinned for visual consistency) -------------------------------------

CHARACTERS = {
    "Female anchor (Channel 14)": {
        "image": str(ROOT / "examples" / "anchor_female_inlove.png"),
        "voice_id": "FGY2WhTYpPnrIDTdsKH5",  # Laura
        "stability": 0.25, "similarity": 0.75, "style": 0.85, "tempo": 1.25,
        "default_text": "אני מאוהבת, איזה מנהיג חזק, איזה מנהיג דגול יש לנו, קרה לנו נס!",
    },
    "Male anchor (Channel 14)": {
        "image": str(ROOT / "examples" / "anchor_male_desk.png"),
        "voice_id": "IKne3meq5aSn9XLyUdCD",  # Charlie
        "stability": 0.20, "similarity": 0.75, "style": 0.90, "tempo": 1.25,
        "default_text": "לגמרי! איזו מנהיגות, אין לנו יותר אויבים!",
    },
    "Eden (the kid)": {
        "image": str(ROOT / "examples" / "eden_puzzled.png"),
        "voice_id": "cgSgspJ2msm6clMCkdW9",  # Jessica
        "stability": 0.55, "similarity": 0.7, "style": 0.25, "tempo": 1.0,
        "default_text": "אבל אמא, ככה נראה ניצחון? ככה נראה ביטחון?",
    },
}

DEFAULT_CAST = ["Female anchor (Channel 14)", "Male anchor (Channel 14)", "Eden (the kid)"]


# --- Auth gate (shared password) ---------------------------------------------

def _expected_password():
    """Read APP_PASSWORD from Streamlit secrets, falling back to env. Returns None if unset."""
    try:
        return st.secrets["APP_PASSWORD"]
    except Exception:
        return os.environ.get("APP_PASSWORD")


def _gate():
    expected = _expected_password()
    if not expected:
        # No password configured — local dev mode, skip gate.
        return
    if st.session_state.get("authed"):
        return
    st.title("🔒 Mind Video")
    st.caption("Enter password to continue")
    pw = st.text_input("Password", type="password", label_visibility="collapsed")
    if st.button("Enter", type="primary", disabled=not pw):
        if pw == expected:
            st.session_state.authed = True
            st.rerun()
        else:
            st.error("Wrong password")
    st.stop()


# --- Bring-your-own-keys sidebar ---------------------------------------------

def _init_keys():
    """Sidebar with three password inputs. Sets os.environ for the pipeline."""
    with st.sidebar:
        st.header("🔑 API Keys")
        st.caption(
            "Your keys stay in your browser session — they're never logged or stored. "
            "Get them at:"
        )
        st.markdown(
            "- [fal.ai](https://fal.ai/dashboard/keys) — needs paid balance\n"
            "- [ElevenLabs](https://elevenlabs.io/app/settings/api-keys) — needs Creator+ plan\n"
            "- [Google AI Studio](https://aistudio.google.com/app/apikey) — *optional*"
        )
        for k in ("FAL_KEY", "ELEVENLABS_API_KEY", "GOOGLE_API_KEY"):
            default = os.environ.get(k, "")
            v = st.text_input(
                k,
                value=st.session_state.get(f"_key_{k}", default),
                type="password",
                key=f"_key_{k}",
            )
            if v:
                os.environ[k] = v
        if st.button("Sign out"):
            st.session_state.clear()
            st.rerun()


# --- Environment checks -------------------------------------------------------

def _preflight():
    missing = [k for k in ("FAL_KEY", "ELEVENLABS_API_KEY") if not os.environ.get(k)]
    if missing:
        st.warning(
            f"Add your **{', '.join(missing)}** in the sidebar (←) to start generating."
        )
        st.stop()
    if not shutil.which("ffmpeg"):
        st.error("`ffmpeg` not found on $PATH.")
        st.stop()
    import subprocess
    probe = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
    if probe.returncode != 0:
        st.error(
            "`ffmpeg` is installed but broken. Stderr:\n```\n"
            + probe.stderr.strip().splitlines()[0] + "\n```"
        )
        st.stop()
    for ch, cfg in CHARACTERS.items():
        if not Path(cfg["image"]).exists():
            st.error(f"Character image missing: `{cfg['image']}` (for *{ch}*).")
            st.stop()


# --- State --------------------------------------------------------------------

def _init_state():
    if "mode" not in st.session_state:
        st.session_state.mode = "input"
    if "segments" not in st.session_state:
        st.session_state.segments = [
            {"character": ch, "text": CHARACTERS[ch]["default_text"]}
            for ch in DEFAULT_CAST
        ]
    if "episode_name" not in st.session_state:
        st.session_state.episode_name = "my_episode"


def _estimate_cost(segments) -> float:
    """Rough: ~15 Hebrew chars per second of audio. VEED $0.08/s + ElevenLabs flat ~$0.10."""
    total_chars = sum(len(s["text"]) for s in segments) or 1
    audio_sec = total_chars / 15.0
    return audio_sec * 0.08 + 0.10 * len(segments)


# --- Screens ------------------------------------------------------------------

def render_input():
    st.title("🎬 Mind Video — Episode Builder")
    st.caption("Channel 14 anchors + Eden the kid · *The Emperor's New Clothes* format")

    st.text_input("Episode name", key="episode_name",
                  help="Used as the output directory name (output/<name>/final.mp4)")

    st.divider()

    segments = st.session_state.segments
    to_remove = None

    for i, seg in enumerate(segments):
        with st.container(border=True):
            cols = st.columns([1.2, 4, 0.5])
            with cols[0]:
                ch_options = list(CHARACTERS.keys())
                seg["character"] = st.selectbox(
                    f"Character #{i+1}",
                    ch_options,
                    index=ch_options.index(seg["character"]),
                    key=f"_char_{i}_{seg['character']}",
                )
                st.image(CHARACTERS[seg["character"]]["image"], width=140)
            with cols[1]:
                seg["text"] = st.text_area(
                    f"Hebrew text #{i+1}",
                    value=seg["text"],
                    height=120,
                    key=f"_text_{i}",
                )
                est_sec = max(1, len(seg["text"]) // 15)
                st.caption(f"≈ {est_sec}s of audio")
            with cols[2]:
                if len(segments) > 1:
                    if st.button("✕", key=f"_del_{i}", help="Remove segment"):
                        to_remove = i

    if to_remove is not None:
        st.session_state.segments.pop(to_remove)
        st.rerun()

    cols = st.columns([1, 1, 3])
    with cols[0]:
        if st.button("+ Add segment"):
            st.session_state.segments.append({
                "character": "Eden (the kid)",
                "text": CHARACTERS["Eden (the kid)"]["default_text"],
            })
            st.rerun()
    with cols[1]:
        st.metric("Estimated cost", f"${_estimate_cost(segments):.2f}")

    st.divider()

    name = st.session_state.episode_name.strip()
    out_dir = ROOT / "output" / name if name else None
    if out_dir and out_dir.exists():
        st.info(f"`output/{name}/` exists — generation will reuse cached steps "
                f"(re-clicking Generate is cheap and safe).")

    if st.button("▶ Generate video", type="primary", disabled=not name,
                 use_container_width=True):
        st.session_state.mode = "running"
        st.session_state.episode_dir = str(out_dir)
        st.rerun()


async def _run_pipeline(segments, episode_dir: Path, log_cb):
    audio_dir = episode_dir / "audio"
    video_dir = episode_dir / "videos"
    audio_dir.mkdir(parents=True, exist_ok=True)
    video_dir.mkdir(parents=True, exist_ok=True)

    video_paths = []
    for i, seg in enumerate(segments):
        ch = CHARACTERS[seg["character"]]
        slug = seg["character"].split()[0].lower()
        seg_id = f"seg{i:02d}_{slug}"
        audio_path = audio_dir / f"{seg_id}.mp3"
        video_path = video_dir / f"{seg_id}.mp4"

        # Image (pinned; just verify)
        log_cb(i, "image", "done", "(pinned)")

        # Audio
        t0 = time.time()
        log_cb(i, "audio", "running", "")
        await generate_tts(
            text=seg["text"], voice_id=ch["voice_id"], output_path=audio_path,
            stability=ch["stability"], similarity=ch["similarity"],
            style=ch["style"], tempo=ch["tempo"],
        )
        log_cb(i, "audio", "done", f"{time.time()-t0:.1f}s")

        # Lip-sync
        t1 = time.time()
        log_cb(i, "lipsync", "running", "starting…")
        def cb(elapsed, msg, _i=i):
            log_cb(_i, "lipsync", "running", f"{elapsed:.0f}s · {msg}")
        await lipsync(Path(ch["image"]), audio_path, video_path, progress_cb=cb)
        log_cb(i, "lipsync", "done", f"{time.time()-t1:.0f}s")

        video_paths.append(video_path)

    # Concat
    log_cb(-1, "concat", "running", "")
    final_path = episode_dir / "final.mp4"
    await concat(video_paths, final_path)
    log_cb(-1, "concat", "done", "")
    return final_path


def render_running():
    st.title("🎬 Generating…")
    name = st.session_state.episode_name
    episode_dir = Path(st.session_state.episode_dir)
    st.caption(f"Episode: **{name}** · `{episode_dir}`")

    segments = st.session_state.segments

    seg_phs = []
    for i, seg in enumerate(segments):
        with st.container(border=True):
            st.markdown(f"**#{i+1} · {seg['character']}**")
            ph = {step: st.empty() for step in ("image", "audio", "lipsync")}
            for step in ("image", "audio", "lipsync"):
                ph[step].markdown(f"⏸ &nbsp; {step}")
            seg_phs.append(ph)

    with st.container(border=True):
        st.markdown("**Concatenate**")
        concat_ph = st.empty()
        concat_ph.markdown("⏸ &nbsp; concat")

    error_box = st.empty()

    ICONS = {"running": "⟳", "done": "✓", "error": "✗"}
    def log_cb(idx, step, status, msg):
        line = f"{ICONS[status]} &nbsp; **{step}** &nbsp; {msg}"
        if idx == -1:
            concat_ph.markdown(line)
        else:
            seg_phs[idx][step].markdown(line)

    t_start = time.time()
    try:
        final_path = asyncio.run(_run_pipeline(segments, episode_dir, log_cb))
        st.session_state.final_path = str(final_path)
        st.session_state.elapsed = time.time() - t_start
        st.session_state.cost = _estimate_cost(segments)
        st.session_state.mode = "done"
        st.rerun()
    except Exception as e:
        error_box.error(f"Pipeline failed: `{type(e).__name__}: {e}`")
        if st.button("← Back to editor"):
            st.session_state.mode = "input"
            st.rerun()


def render_done():
    st.title("✓ Episode ready")
    final_path = Path(st.session_state.final_path)
    elapsed = st.session_state.elapsed
    cost = st.session_state.get("cost", 0.0)

    cols = st.columns([3, 1])
    with cols[0]:
        st.video(str(final_path))
    with cols[1]:
        st.metric("Wallclock", f"{int(elapsed//60)}m {int(elapsed%60)}s")
        st.metric("Est. cost", f"${cost:.2f}")
        st.write("**Output**")
        st.code(str(final_path), language=None)
        with open(final_path, "rb") as f:
            st.download_button("⬇ Download MP4", f,
                               file_name=final_path.name,
                               mime="video/mp4",
                               use_container_width=True)
        if st.button("↻ New episode", use_container_width=True):
            st.session_state.mode = "input"
            st.rerun()


# --- Main ---------------------------------------------------------------------

_gate()
_init_keys()
_preflight()
_init_state()

mode = st.session_state.mode
if mode == "input":
    render_input()
elif mode == "running":
    render_running()
elif mode == "done":
    render_done()
