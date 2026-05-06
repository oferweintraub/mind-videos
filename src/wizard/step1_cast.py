"""Step 1 — Cast (character builder).

Two sub-views, controlled by st.session_state.step1_mode:
- "list"  : show the cast tiles + Add button
- "edit"  : the inline character form (description → style → generate → pick → voice → save)

Generation is in-process (calls Nano Banana Pro directly) so we can stream
progress via st.spinner. No subprocess calls, no temp files outside the
canonical _candidates/ work area.
"""

from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path
from typing import Optional

import streamlit as st
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent

from src.character import Character, Voice
from src.wizard.state import (
    add_character, remove_character, load_demo, safe_slug, DEMO_CAST_SLUGS,
)
from src.wizard.theme import PALETTE


CHARACTERS_DIR = ROOT / "characters"
CANDIDATES_DIR = CHARACTERS_DIR / "_candidates"
VOICES_YAML = ROOT / "config" / "voices.yaml"
PREVIEWS_DIR = ROOT / "config" / "voice_previews"
MAX_CAST_SIZE = 4

STYLE_OPTIONS = ["lego", "muppet", "pixar", "ghibli", "comic", "anime", "south_park"]
TEMPO_PRESETS = {"Calm": 1.0, "Natural": 1.0, "Urgent": 1.25}


# --- Voice catalog ------------------------------------------------------------

@st.cache_data
def _voice_catalog() -> list[dict]:
    if not VOICES_YAML.exists():
        return []
    data = yaml.safe_load(VOICES_YAML.read_text()) or {}
    return data.get("voices", [])


def _voice_label(v: dict) -> str:
    return f"{v['name']} — {v['tone']}"


def _preview_path(voice_id: str) -> Optional[Path]:
    p = PREVIEWS_DIR / f"{voice_id}.mp3"
    return p if p.exists() else None


# --- Step 1 dispatcher --------------------------------------------------------

def render():
    """Entry point — Step 1 router."""
    if "step1_mode" not in st.session_state:
        st.session_state.step1_mode = "list"

    if st.session_state.step1_mode == "edit":
        _render_edit()
    else:
        _render_list()


# --- List view ----------------------------------------------------------------

def _render_list():
    cast = st.session_state.cast

    st.markdown("# Build your cast")
    st.markdown(
        f'<p class="wz-quiet">Add 1 to {MAX_CAST_SIZE} characters. '
        f'Each gets a still image and a Hebrew voice.</p>',
        unsafe_allow_html=True,
    )

    if not cast:
        _render_empty_state()
    else:
        _render_cast_tiles(cast)

    st.markdown('<div class="wz-footer"></div>', unsafe_allow_html=True)
    _, _, right = st.columns([1, 1, 1])
    with right:
        valid = 1 <= len(cast) <= MAX_CAST_SIZE
        if st.button(
            "Continue to Step 2  →",
            type="primary",
            disabled=not valid,
            width="stretch",
            key="step1_continue",
        ):
            st.session_state.step = 2
            st.rerun()


def _render_empty_state():
    """Two big CTAs for first-time users: build from scratch OR load the demo."""
    c1, c2 = st.columns(2)

    with c1:
        st.markdown(
            f'<div class="wz-card empty">'
            f'<h3>+  Build your own</h3>'
            f'<p class="wz-quiet">Describe a character — the wizard generates 3 stills '
            f'in your chosen style and lets you pick.</p>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if st.button("Add a character", key="empty_add", width="stretch"):
            _enter_edit_mode()
            st.rerun()

    with c2:
        st.markdown(
            f'<div class="wz-card empty">'
            f'<h3>⚡  Try the demo</h3>'
            f'<p class="wz-quiet">Pre-built Channel 14 anchors + Eden, plus a '
            f'sample script. Goes straight to render.</p>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if st.button("Load demo", key="empty_demo", width="stretch"):
            ok = load_demo()
            if ok:
                st.toast("Demo cast + script loaded", icon="⚡")
                st.session_state.step = 2
            else:
                st.toast("Demo characters not found in repo", icon="⚠️")
            st.rerun()


def _render_cast_tiles(cast: dict):
    cast_list = list(cast.values())
    n_slots = min(MAX_CAST_SIZE, len(cast_list) + 1)
    cols = st.columns(n_slots)

    for i, char in enumerate(cast_list):
        with cols[i]:
            st.markdown(
                f'<div class="wz-card" style="text-align:center; padding:1rem 0.6rem;">',
                unsafe_allow_html=True,
            )
            st.image(str(char.image_path), width="stretch")
            st.markdown(
                f'<div style="margin-top:0.6rem;">'
                f'<strong>{char.display_name}</strong><br>'
                f'<span class="wz-tiny">@{char.slug} · {char.voice.voice_name or "—"}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            if st.button("Remove", key=f"cast_rm_{char.slug}", width="stretch"):
                remove_character(char.slug)
                st.toast(f"Removed {char.display_name}", icon="🗑")
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    # The "+ add" tile, if there's room
    if len(cast_list) < MAX_CAST_SIZE:
        with cols[len(cast_list)]:
            st.markdown('<div class="wz-card empty" style="margin-top:0;">',
                        unsafe_allow_html=True)
            st.markdown('<div style="font-size:1.6rem; margin-bottom:0.4rem;">+</div>',
                        unsafe_allow_html=True)
            st.markdown(
                f'<p class="wz-quiet" style="margin:0 0 0.8rem 0;">Add character</p>',
                unsafe_allow_html=True,
            )
            if st.button("Add", key="cast_add_more", width="stretch"):
                _enter_edit_mode()
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)


# --- Edit view ----------------------------------------------------------------

def _enter_edit_mode():
    st.session_state.step1_mode = "edit"
    st.session_state.draft = {
        "description": "",
        "compare_styles": False,
        "single_style": "lego",
        "compare_pick": ["lego", "south_park"],
        "custom_style": "",
        "count": 3,
        "candidates": [],     # list of {path, style, idx}
        "picked": None,       # idx int, or None
        "voice_id": "",
        "tempo_label": "Natural",
        "display_name": "",
        "slug": "",
    }


def _exit_edit_mode():
    st.session_state.step1_mode = "list"
    if "draft" in st.session_state:
        del st.session_state.draft


def _render_edit():
    draft = st.session_state.draft

    if st.button("← Back to cast", key="edit_back"):
        _exit_edit_mode()
        st.rerun()

    st.markdown("# Add a character")

    # 1. Description
    st.markdown("### Describe the character")
    draft["description"] = st.text_input(
        " ",
        value=draft["description"],
        placeholder="e.g. a 70-year-old grandmother with white hair, round glasses, in pajamas",
        label_visibility="collapsed",
        key="draft_desc",
    )

    # 2. Style — one or compare
    st.markdown("### Style")

    mode = st.segmented_control(
        " ",
        options=["One style, multiple variants", "Compare 2-3 styles"],
        default="One style, multiple variants" if not draft["compare_styles"] else "Compare 2-3 styles",
        label_visibility="collapsed",
        key="draft_style_mode",
    )
    draft["compare_styles"] = (mode == "Compare 2-3 styles")

    if not draft["compare_styles"]:
        # Single-style
        sel = st.pills(
            "Pick one",
            options=STYLE_OPTIONS + ["custom..."],
            default=draft["single_style"] if draft["single_style"] in STYLE_OPTIONS else "custom...",
            selection_mode="single",
            label_visibility="collapsed",
            key="draft_single_pill",
        )
        if sel == "custom...":
            draft["custom_style"] = st.text_input(
                "Custom style description",
                value=draft["custom_style"],
                placeholder="e.g. claymation, watercolor, low-poly 3d",
                key="draft_custom_style",
            )
            draft["single_style"] = draft["custom_style"] or "custom"
        else:
            draft["single_style"] = sel or "lego"

        draft["count"] = st.slider(
            "How many variants to generate?",
            min_value=1, max_value=4,
            value=draft["count"], key="draft_count",
        )
    else:
        # Multi-style compare
        picks = st.pills(
            "Pick 2 or 3 to compare",
            options=STYLE_OPTIONS,
            default=draft["compare_pick"],
            selection_mode="multi",
            label_visibility="collapsed",
            key="draft_compare_pill",
        )
        # Streamlit pills returns the list directly
        draft["compare_pick"] = picks or []
        if len(draft["compare_pick"]) < 2:
            st.markdown(
                '<p class="wz-tiny">Pick at least 2 styles to compare.</p>',
                unsafe_allow_html=True,
            )
        elif len(draft["compare_pick"]) > 3:
            st.markdown(
                '<p class="wz-tiny" style="color:#E07B7B;">Pick at most 3.</p>',
                unsafe_allow_html=True,
            )

    # 3. Generate button
    can_generate = bool(draft["description"].strip()) and (
        not draft["compare_styles"] and bool(draft["single_style"]) or
        draft["compare_styles"] and 2 <= len(draft["compare_pick"]) <= 3
    )

    if st.button(
        "▶  Generate candidates",
        type="primary",
        disabled=not can_generate,
        key="draft_generate",
    ):
        _generate_candidates_for_draft()
        st.rerun()

    # 4. Candidate picker (if generated)
    if draft["candidates"]:
        st.divider()
        _render_candidates_grid(draft)

    # 5. Voice + tempo + name + save (only after a pick)
    if draft["picked"] is not None:
        st.divider()
        _render_voice_and_save(draft)


def _generate_candidates_for_draft():
    """Run Nano Banana Pro and save candidates. Blocking with a spinner."""
    draft = st.session_state.draft

    if not os.environ.get("GOOGLE_API_KEY"):
        st.toast("GOOGLE_API_KEY not set — open Settings (⚙)", icon="⚠️")
        return

    # Generate a session-local slug for the candidates dir
    if not draft["slug"]:
        draft["slug"] = safe_slug(draft["description"], fallback="character")

    out_dir = CANDIDATES_DIR / draft["slug"]
    # Wipe stale candidates from previous attempts in this session
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Build the (idx, style) plan
    if draft["compare_styles"]:
        plan = list(enumerate(draft["compare_pick"], start=1))
    else:
        plan = [(i, draft["single_style"]) for i in range(1, draft["count"] + 1)]

    # Lazy-import the prompt builder + generator from the existing CLI module
    from scripts.character_lab import build_prompt, generate_one
    from google import genai

    async def run_all():
        client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
        coros = []
        for i, style in plan:
            prompt = build_prompt(draft["description"], style)
            (out_dir / f"option_{i}_style.txt").write_text(style)
            coros.append(generate_one(client, prompt, out_dir / f"option_{i}.png"))
        return await asyncio.gather(*coros, return_exceptions=True)

    with st.spinner(f"Generating {len(plan)} candidate{'s' if len(plan) != 1 else ''}…"):
        results = asyncio.run(run_all())

    candidates = []
    fail_count = 0
    for (i, style), r in zip(plan, results):
        if isinstance(r, Exception):
            fail_count += 1
            continue
        candidates.append({"idx": i, "style": style, "path": str(out_dir / f"option_{i}.png")})

    draft["candidates"] = candidates
    draft["picked"] = None  # reset selection on re-generate

    if not candidates:
        st.toast("All candidates failed — check GOOGLE_API_KEY", icon="✗")
    elif fail_count:
        st.toast(f"{len(candidates)} ok · {fail_count} failed", icon="⚠️")
    else:
        st.toast(f"Generated {len(candidates)} candidate{'s' if len(candidates) != 1 else ''}",
                 icon="✓")


def _render_candidates_grid(draft):
    st.markdown("### Pick one")
    st.markdown(
        '<p class="wz-quiet">Look for: clear face, mouth visible, no hands near the face. '
        'These rules matter for lip-sync quality.</p>',
        unsafe_allow_html=True,
    )

    candidates = draft["candidates"]
    cols = st.columns(len(candidates))
    for col, cand in zip(cols, candidates):
        with col:
            picked = (draft["picked"] == cand["idx"])
            klass = "selected" if picked else ""
            st.markdown(f'<div class="wz-card {klass}" style="padding:0.5rem;">',
                        unsafe_allow_html=True)
            st.image(cand["path"], width="stretch")
            st.markdown(
                f'<p class="wz-tiny" style="text-align:center; margin:0.4rem 0 0.2rem 0;">'
                f'{cand["style"]}'
                f'</p>',
                unsafe_allow_html=True,
            )
            label = "✓ Selected" if picked else "Select"
            if st.button(label, key=f"cand_pick_{cand['idx']}", width="stretch",
                         type="primary" if picked else "secondary"):
                draft["picked"] = cand["idx"]
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)


def _render_voice_and_save(draft):
    st.markdown("### Voice")

    catalog = _voice_catalog()
    if not catalog:
        st.error("config/voices.yaml not found or empty.")
        return

    voice_options = {v["id"]: v for v in catalog}
    if not draft["voice_id"] or draft["voice_id"] not in voice_options:
        # Default: a voice that fits the style
        draft["voice_id"] = catalog[0]["id"]

    selected_id = st.selectbox(
        "Select an ElevenLabs voice",
        options=list(voice_options.keys()),
        index=list(voice_options.keys()).index(draft["voice_id"]),
        format_func=lambda vid: _voice_label(voice_options[vid]),
        key="draft_voice",
    )
    draft["voice_id"] = selected_id

    # Voice preview audio
    preview = _preview_path(selected_id)
    if preview:
        st.audio(str(preview), format="audio/mp3")
        st.markdown(
            '<p class="wz-tiny" style="margin-top:-0.5rem;">'
            'Hebrew sample — the actual rendered voice in your video.'
            '</p>',
            unsafe_allow_html=True,
        )

    # Tempo
    st.markdown("### Tempo")
    tempo_label = st.segmented_control(
        " ",
        options=list(TEMPO_PRESETS.keys()),
        default=draft["tempo_label"],
        label_visibility="collapsed",
        key="draft_tempo",
    )
    draft["tempo_label"] = tempo_label or "Natural"

    # Display name (auto-fill from style + slug if user hasn't typed one)
    st.markdown("### Display name")
    if not draft["display_name"]:
        primary_style = (draft["single_style"] if not draft["compare_styles"]
                         else (draft["candidates"] or [{"style": ""}])[0]["style"])
        draft["display_name"] = f"{primary_style.replace('_', ' ').title()} character".strip()

    draft["display_name"] = st.text_input(
        "How this character appears in the cast",
        value=draft["display_name"],
        label_visibility="collapsed",
        key="draft_name",
    )

    st.divider()

    can_save = bool(draft["display_name"].strip()) and bool(draft["voice_id"])
    cols = st.columns([1, 1, 2])
    with cols[0]:
        if st.button("Cancel", key="draft_cancel", width="stretch"):
            _exit_edit_mode()
            st.rerun()
    with cols[2]:
        if st.button(
            "Save character",
            type="primary",
            disabled=not can_save,
            width="stretch",
            key="draft_save",
        ):
            _save_draft_as_character()
            _exit_edit_mode()
            st.rerun()


def _save_draft_as_character():
    """Promote the picked candidate into the character library."""
    draft = st.session_state.draft

    voice_meta = next((v for v in _voice_catalog() if v["id"] == draft["voice_id"]), {})
    voice_name = voice_meta.get("name", "")

    base_slug = safe_slug(draft["display_name"], fallback=draft["slug"] or "character")
    # Avoid collision with existing on-disk characters
    slug = base_slug
    n = 2
    while (CHARACTERS_DIR / slug / "manifest.json").exists() or slug in st.session_state.cast:
        slug = f"{base_slug}_{n}"
        n += 1

    target_dir = CHARACTERS_DIR / slug
    target_dir.mkdir(parents=True, exist_ok=True)

    src_path = Path(next(c["path"] for c in draft["candidates"] if c["idx"] == draft["picked"]))
    shutil.copy2(src_path, target_dir / "image.png")

    style_label = (draft["single_style"] if not draft["compare_styles"]
                   else next(c["style"] for c in draft["candidates"] if c["idx"] == draft["picked"]))

    char = Character(
        slug=slug,
        display_name=draft["display_name"].strip(),
        description=draft["description"].strip(),
        style=style_label,
        voice=Voice(
            voice_id=draft["voice_id"],
            voice_name=voice_name,
            stability=0.5,
            similarity=0.75,
            style=0.5,
            tempo=TEMPO_PRESETS[draft["tempo_label"]],
        ),
    )
    char.save(dir=target_dir)

    add_character(char)
    st.toast(f"Added {char.display_name} to your cast", icon="✓")
