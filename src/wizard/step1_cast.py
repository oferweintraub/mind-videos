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
    go_to,
)
from src.wizard.theme import PALETTE
from src.wizard import creds
from src.wizard.errors import friendly_error


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

    mode = st.session_state.step1_mode
    if mode == "edit":
        _render_edit()
    elif mode == "edit_existing":
        _render_edit_existing()
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
            go_to(2)
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
                # load_demo already sets step=2 internally + auto_saves
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
            edit_col, rm_col = st.columns(2)
            with edit_col:
                if st.button("Edit", key=f"cast_edit_{char.slug}", width="stretch"):
                    _enter_edit_existing(char.slug)
                    st.rerun()
            with rm_col:
                if st.button("Remove", key=f"cast_rm_{char.slug}", width="stretch"):
                    remove_character(char.slug)
                    st.toast(f"Removed {char.display_name}", icon="🗑️")
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
        "last_failures": [],  # list of {style, error} from last generation attempt
        "picked": None,       # idx int, or None
        "voice_id": "",
        "tempo_label": "Natural",
        "display_name": "",
        "slug": "",
        # Optional reference image — when provided, generation routes through
        # FLUX Kontext Pro (fal.ai) instead of Nano Banana Pro
        "ref_image_bytes": None,
        "ref_image_name": "",
    }


def _exit_edit_mode():
    st.session_state.step1_mode = "list"
    if "draft" in st.session_state:
        del st.session_state.draft
    if "edit_existing" in st.session_state:
        del st.session_state.edit_existing


def _enter_edit_existing(slug: str):
    """Open the edit-existing-character form for the given slug."""
    char = st.session_state.cast.get(slug)
    if char is None:
        return
    # Inverse-lookup tempo label
    tempo_label = next(
        (label for label, val in TEMPO_PRESETS.items() if val == char.voice.tempo),
        "Natural",
    )
    st.session_state.step1_mode = "edit_existing"
    st.session_state.edit_existing = {
        "slug": slug,
        "display_name": char.display_name,
        "description": char.description,
        "style": char.style,
        "voice_id": char.voice.voice_id,
        "tempo_label": tempo_label,
        # Regen sub-state — populated when user clicks "Regenerate images"
        "regen_active": False,
        "regen_candidates": [],     # [{idx, style, path}]
        "regen_failures": [],       # [{style, error}]
        "regen_picked": None,       # idx of chosen candidate, or None
    }


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

    # 1b. Optional reference image
    st.markdown("### Reference image (optional)")
    st.markdown(
        '<p class="wz-quiet" style="font-size:0.88rem;">'
        'Upload a photo of a real person or another character to lock in the face. '
        'When provided, generation routes through <strong>FLUX Kontext Pro</strong> '
        '(fal.ai) — better at preserving identity than text-only prompts. '
        'Skip this for fully imagined characters.'
        '</p>',
        unsafe_allow_html=True,
    )
    ref_upload = st.file_uploader(
        "Reference image",
        type=["png", "jpg", "jpeg", "webp"],
        label_visibility="collapsed",
        key="draft_ref_upload",
    )
    if ref_upload is not None:
        draft["ref_image_bytes"] = ref_upload.getvalue()
        draft["ref_image_name"] = ref_upload.name

    if draft["ref_image_bytes"]:
        c1, c2 = st.columns([1, 5])
        with c1:
            st.image(draft["ref_image_bytes"], width=120)
        with c2:
            st.markdown(
                f'<p class="wz-quiet" style="margin-top:0.6rem;">'
                f'Reference: <strong>{draft["ref_image_name"]}</strong> · '
                f'using FLUX Kontext Pro (~$0.05 per candidate)'
                f'</p>',
                unsafe_allow_html=True,
            )
            if st.button("Remove reference", key="draft_ref_remove"):
                draft["ref_image_bytes"] = None
                draft["ref_image_name"] = ""
                st.rerun()

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

    # 4b. Show any generation errors so failures are diagnosable.
    # Use the friendly-error helper to translate the FIRST failure's exception
    # into actionable prose; show the per-style raw errors below for context.
    failures = draft.get("last_failures") or []
    if failures and not draft["candidates"]:
        # Reconstruct an Exception-shaped object from the first failure to
        # feed friendly_error. We stored the message string, not the exception
        # object; build a synthetic one whose str() matches.
        first = failures[0]
        synthetic = type(
            first["error"].split(":", 1)[0],
            (Exception,),
            {},
        )(": ".join(first["error"].split(": ", 1)[1:]) or first["error"])
        st.error(f"**All candidates failed.** {friendly_error(synthetic)}")
        with st.expander("Per-style raw errors"):
            for f in failures:
                st.code(f"[{f['style']}]  {f['error']}", language=None)
    elif failures:
        with st.expander(f"⚠ {len(failures)} candidate(s) failed — see details"):
            for f in failures:
                st.code(f"[{f['style']}]  {f['error']}", language=None)

    # 5. Voice + tempo + name + save (only after a pick)
    if draft["picked"] is not None:
        st.divider()
        _render_voice_and_save(draft)


def _generate_candidates_for_draft():
    """Run image generation for the draft. Routes between Nano Banana Pro
    (text-only) and FLUX Kontext Pro (when a reference image is attached)."""
    draft = st.session_state.draft

    c = creds.read()
    use_ref = bool(draft.get("ref_image_bytes"))

    # Key requirements differ per route
    if use_ref and not c.fal:
        st.toast("Add fal.ai key in the Settings panel — needed for FLUX Kontext (ref image)", icon="⚠️")
        return
    if not use_ref and not c.google:
        st.toast("Add Google AI key in the Settings panel first", icon="⚠️")
        return

    # Generate a session-local slug for the candidates dir
    if not draft["slug"]:
        draft["slug"] = safe_slug(draft["description"], fallback="character")

    out_dir = CANDIDATES_DIR / draft["slug"]
    # Wipe stale candidates from previous attempts in this session
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # If ref bytes are attached, save them to the candidates dir so FLUX Kontext
    # has a stable file path to upload.
    ref_path: Optional[Path] = None
    if use_ref:
        ref_path = out_dir / "_ref.png"
        ref_path.write_bytes(draft["ref_image_bytes"])

    # Build the (idx, style) plan
    if draft["compare_styles"]:
        plan = list(enumerate(draft["compare_pick"], start=1))
    else:
        plan = [(i, draft["single_style"]) for i in range(1, draft["count"] + 1)]

    from src.pipeline.character_gen import generate_text_only, generate_with_ref
    from scripts.character_lab import build_prompt

    async def run_all():
        coros = []
        for i, style in plan:
            (out_dir / f"option_{i}_style.txt").write_text(style)
            out_path = out_dir / f"option_{i}.png"
            if use_ref:
                coros.append(generate_with_ref(
                    ref_path, draft["description"], style, out_path,
                    fal_key=c.fal,
                ))
            else:
                coros.append(generate_text_only(
                    draft["description"], style, out_path,
                    google_api_key=c.google,
                ))
        return await asyncio.gather(*coros, return_exceptions=True)

    label_route = "FLUX Kontext (ref)" if use_ref else "Nano Banana Pro"
    with st.spinner(f"Generating {len(plan)} candidate{'s' if len(plan) != 1 else ''} via {label_route}…"):
        results = asyncio.run(run_all())

    candidates = []
    failures: list[tuple[int, str, Exception]] = []
    for (i, style), r in zip(plan, results):
        if isinstance(r, Exception):
            failures.append((i, style, r))
            continue
        candidates.append({"idx": i, "style": style, "path": str(out_dir / f"option_{i}.png")})

    draft["candidates"] = candidates
    draft["picked"] = None  # reset selection on re-generate
    # Stash failures so the UI can render them after the rerun
    draft["last_failures"] = [
        {"style": style, "error": f"{type(e).__name__}: {str(e)[:240]}"}
        for _, style, e in failures
    ] if failures else []

    if not candidates:
        st.toast("All candidates failed — see error below", icon="❌")
    elif failures:
        st.toast(f"{len(candidates)} ok · {len(failures)} failed", icon="⚠️")
    else:
        st.toast(f"Generated {len(candidates)} candidate{'s' if len(candidates) != 1 else ''}",
                 icon="✅")


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
    st.toast(f"Added {char.display_name} to your cast", icon="✅")


# --- Edit-existing view -------------------------------------------------------

def _render_edit_existing():
    """Edit metadata of an existing character; optionally regenerate the image."""
    edit = st.session_state.edit_existing
    slug = edit["slug"]
    char = st.session_state.cast.get(slug)
    if char is None:
        st.warning("Character no longer exists.")
        if st.button("← Back to cast"):
            _exit_edit_mode()
            st.rerun()
        return

    if st.button("← Back to cast", key="edit_existing_back"):
        _exit_edit_mode()
        st.rerun()

    st.markdown(f"# Edit *{char.display_name}*")
    st.markdown(
        '<p class="wz-quiet">Change voice, tempo, or display name. '
        'Regenerate the image with new candidates if you want a different look.</p>',
        unsafe_allow_html=True,
    )

    # Two columns: image + regen control on left; metadata fields on right
    img_col, form_col = st.columns([1, 1.6], gap="large")

    with img_col:
        # Show current image OR the picked regen candidate
        if edit["regen_picked"] is not None:
            picked_path = next(
                c["path"] for c in edit["regen_candidates"] if c["idx"] == edit["regen_picked"]
            )
            st.image(picked_path, width="stretch")
            st.markdown(
                f'<p class="wz-tiny" style="text-align:center;">'
                f'<strong style="color:{PALETTE["accent"]};">New image</strong> '
                f'(saves on Apply)</p>',
                unsafe_allow_html=True,
            )
        else:
            st.image(str(char.image_path), width="stretch")
            st.markdown(
                '<p class="wz-tiny" style="text-align:center;">Current image</p>',
                unsafe_allow_html=True,
            )

        if not edit["regen_active"]:
            if st.button("🎨 Regenerate images", key="regen_start", width="stretch"):
                edit["regen_active"] = True
                st.rerun()
        else:
            if st.button("Cancel regenerate", key="regen_cancel", width="stretch"):
                edit["regen_active"] = False
                edit["regen_candidates"] = []
                edit["regen_picked"] = None
                edit["regen_failures"] = []
                st.rerun()

    with form_col:
        # Description (read-only, shown as context)
        if edit["description"]:
            st.markdown("##### Description")
            st.markdown(
                f'<p class="wz-quiet" style="font-size:0.9rem;">{edit["description"]}</p>',
                unsafe_allow_html=True,
            )
            st.markdown("&nbsp;", unsafe_allow_html=True)

        # Display name
        edit["display_name"] = st.text_input(
            "Display name",
            value=edit["display_name"],
            key="ee_display_name",
        )

        # Voice picker
        st.markdown("##### Voice")
        catalog = _voice_catalog()
        voice_ids = [v["id"] for v in catalog]
        # If the character's voice isn't in the catalog (custom/cloned), insert it.
        if edit["voice_id"] and edit["voice_id"] not in voice_ids:
            voice_ids.insert(0, edit["voice_id"])

        try:
            voice_idx = voice_ids.index(edit["voice_id"])
        except ValueError:
            voice_idx = 0
        voice_lookup = {v["id"]: v for v in catalog}

        def _fmt(vid):
            v = voice_lookup.get(vid)
            return _voice_label(v) if v else f"{vid} (custom)"

        new_voice = st.selectbox(
            "Select voice",
            options=voice_ids,
            index=voice_idx,
            format_func=_fmt,
            label_visibility="collapsed",
            key="ee_voice",
        )
        edit["voice_id"] = new_voice
        preview = _preview_path(new_voice)
        if preview:
            st.audio(str(preview), format="audio/mp3")

        # Tempo
        st.markdown("##### Tempo")
        edit["tempo_label"] = st.segmented_control(
            " ",
            options=list(TEMPO_PRESETS.keys()),
            default=edit["tempo_label"],
            label_visibility="collapsed",
            key="ee_tempo",
        ) or "Natural"

    # Regenerate flow (full-width below the two-col layout)
    if edit["regen_active"]:
        st.divider()
        _render_regen_section(edit)

    st.divider()

    # Save / Cancel
    cols = st.columns([1, 1, 2])
    with cols[0]:
        if st.button("Cancel", key="ee_cancel", width="stretch"):
            _exit_edit_mode()
            st.rerun()
    with cols[2]:
        save_label = "Apply changes"
        if edit["regen_picked"] is not None:
            save_label = "Apply (with new image)"
        if st.button(save_label, type="primary", width="stretch", key="ee_save"):
            _apply_edit_existing()
            _exit_edit_mode()
            st.rerun()


def _render_regen_section(edit: dict):
    """Run another generation pass and let the user pick a new image."""
    st.markdown("### Regenerate the image")
    st.markdown(
        '<p class="wz-quiet">Same description and style — fresh candidates. '
        'Pick one to replace the current image (only saves when you click Apply).</p>',
        unsafe_allow_html=True,
    )

    cols = st.columns([1, 1, 2])
    with cols[0]:
        count = st.slider("Variants", 1, 4, 3, key="regen_count")
    with cols[1]:
        if st.button("▶ Generate", type="primary", key="regen_go", width="stretch"):
            _run_regen(edit, count=count)
            st.rerun()

    if edit["regen_candidates"]:
        st.markdown("#### Pick one to replace the current image")
        grid = st.columns(len(edit["regen_candidates"]))
        for col, cand in zip(grid, edit["regen_candidates"]):
            with col:
                picked = (edit["regen_picked"] == cand["idx"])
                klass = "selected" if picked else ""
                st.markdown(f'<div class="wz-card {klass}" style="padding:0.5rem;">',
                            unsafe_allow_html=True)
                st.image(cand["path"], width="stretch")
                st.markdown(
                    f'<p class="wz-tiny" style="text-align:center; margin:0.4rem 0 0.2rem 0;">'
                    f'{cand["style"]}</p>',
                    unsafe_allow_html=True,
                )
                if st.button("✓ Selected" if picked else "Select",
                             key=f"regen_pick_{cand['idx']}",
                             width="stretch",
                             type="primary" if picked else "secondary"):
                    edit["regen_picked"] = cand["idx"]
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

    if edit["regen_failures"] and not edit["regen_candidates"]:
        first = edit["regen_failures"][0]
        synthetic = type(
            first["error"].split(":", 1)[0],
            (Exception,),
            {},
        )(": ".join(first["error"].split(": ", 1)[1:]) or first["error"])
        st.error(f"**All candidates failed.** {friendly_error(synthetic)}")
        with st.expander("Per-style raw errors"):
            for f in edit["regen_failures"]:
                st.code(f"[{f['style']}]  {f['error']}", language=None)


def _run_regen(edit: dict, count: int):
    """Generate `count` candidates with the existing description + style."""
    c = creds.read()
    if not c.google:
        st.toast("Add Google AI key in the Settings panel first", icon="⚠️")
        return

    out_dir = CANDIDATES_DIR / f"regen_{edit['slug']}"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    style = edit["style"] or "south_park"
    plan = [(i, style) for i in range(1, count + 1)]

    from scripts.character_lab import build_prompt, generate_one
    from google import genai

    async def run_all():
        client = genai.Client(api_key=c.google)
        coros = []
        for i, sty in plan:
            prompt = build_prompt(edit["description"] or edit["display_name"], sty)
            coros.append(generate_one(client, prompt, out_dir / f"option_{i}.png"))
        return await asyncio.gather(*coros, return_exceptions=True)

    with st.spinner(f"Generating {count} candidate{'s' if count != 1 else ''}…"):
        results = asyncio.run(run_all())

    candidates = []
    failures = []
    for (i, sty), r in zip(plan, results):
        if isinstance(r, Exception):
            failures.append({"style": sty, "error": f"{type(r).__name__}: {str(r)[:240]}"})
            continue
        candidates.append({"idx": i, "style": sty, "path": str(out_dir / f"option_{i}.png")})

    edit["regen_candidates"] = candidates
    edit["regen_failures"] = failures
    edit["regen_picked"] = None
    if not candidates:
        st.toast("All candidates failed — see error below", icon="❌")
    else:
        st.toast(f"Generated {len(candidates)} candidate{'s' if len(candidates) != 1 else ''}",
                 icon="✅")


def _apply_edit_existing():
    """Persist the edit_existing state to disk + session cast."""
    edit = st.session_state.edit_existing
    slug = edit["slug"]
    char = st.session_state.cast.get(slug)
    if char is None:
        return

    # Update mutable metadata
    char.display_name = (edit["display_name"] or "").strip() or char.display_name
    char.voice.voice_id = edit["voice_id"]
    char.voice.tempo = TEMPO_PRESETS[edit["tempo_label"]]
    # Refresh voice_name from the catalog if possible
    voice_meta = next((v for v in _voice_catalog() if v["id"] == edit["voice_id"]), None)
    if voice_meta:
        char.voice.voice_name = voice_meta["name"]

    # If the user picked a regen candidate, copy it onto the character image
    if edit["regen_picked"] is not None:
        src_path = Path(next(
            c["path"] for c in edit["regen_candidates"] if c["idx"] == edit["regen_picked"]
        ))
        if char.dir is not None:
            shutil.copy2(src_path, char.dir / char.image)

    # Save manifest
    char.save()

    # Refresh in-memory cast + push to cloud (uploads new image if regen, saves
    # metadata) via add_character which handles both.
    add_character(char)

    st.toast(f"Updated {char.display_name}", icon="✅")
