"""Step 2 — Script (segment builder).

Title field + vertical list of segment cards. Each card has:
- Avatar + character dropdown (from the cast)
- RTL Hebrew textarea
- Live audio-length estimate
- Per-segment "🎙 Generate audio" preview + 🔄 Regenerate (lets the user
  catch pronunciation issues here before paying for lip-sync)
- Reorder up/down + remove buttons

A live "running cost" rail shows total seconds + cost.
"""

from __future__ import annotations

import asyncio

import streamlit as st

from src.pipeline.episode import generate_tts
from src.wizard import creds
from src.wizard.errors import friendly_error
from src.wizard.state import (
    add_segment, remove_segment, move_segment, estimate_segment_seconds,
    estimate_episode, go_to, audio_path_for_segment,
    push_segment_audio_to_storage, pull_segment_audio_from_storage,
)
from src.wizard.theme import PALETTE


def render():
    cast = st.session_state.cast
    if not cast:
        st.warning("No cast yet — go back to Step 1 to add characters.")
        if st.button("← Back to Step 1"):
            go_to(1)
            st.rerun()
        return

    st.markdown("# Write the script")
    st.markdown(
        '<p class="wz-quiet">Each segment is one character speaking one line in Hebrew. '
        'Add as many as you like. Use <strong>🎙 Generate audio</strong> on any segment '
        'to preview the TTS before paying for lip-sync — cheap (~$0.05) and catches '
        'pronunciation issues early.<br/>'
        '<strong>💡 Stubborn word?</strong> Type it with niqqud — e.g. '
        '<code>חַסְקָה</code> instead of <code>חסקה</code>. eleven_v3 reads Hebrew '
        'vowel marks.</p>',
        unsafe_allow_html=True,
    )

    # --- Title ----------------------------------------------------------------

    st.session_state.title = st.text_input(
        "Episode title",
        value=st.session_state.title,
        placeholder="e.g. Hostages, Victory, The Visit",
        max_chars=80,
        key="step2_title",
    )

    # --- Segments -------------------------------------------------------------

    st.markdown("### Segments")

    segments = st.session_state.segments

    # Side-by-side: segment list (wide) + cost rail (narrow)
    main, side = st.columns([3, 1])

    to_remove = None
    to_move: tuple[int, int] | None = None

    with main:
        if not segments:
            st.markdown(
                '<div class="wz-card empty"><p>No segments yet. Click <strong>+ Add segment</strong> below to start.</p></div>',
                unsafe_allow_html=True,
            )

        for i, seg in enumerate(segments):
            with st.container(border=True):
                # Top row: avatar + character + reorder/remove
                row = st.columns([0.7, 3, 0.5, 0.5, 0.5])
                slug = seg.get("character", "")

                # Render the selectbox FIRST so we have the up-to-date slug
                # before drawing the avatar. Otherwise the avatar shows the
                # previous selection until a second rerun catches up.
                with row[1]:
                    slugs = list(cast.keys())
                    idx = slugs.index(slug) if slug in slugs else 0
                    new_slug = st.selectbox(
                        " ",
                        options=slugs,
                        index=idx,
                        format_func=lambda s: cast[s].display_name,
                        label_visibility="collapsed",
                        key=f"seg_char_{i}",
                    )
                    if new_slug != slug:
                        seg["character"] = new_slug
                        slug = new_slug
                char = cast.get(slug)

                with row[0]:
                    if char:
                        st.image(str(char.image_path), width="stretch")
                    else:
                        st.markdown(
                            '<div style="height:64px; background:#363B47; border-radius:8px; '
                            'display:flex; align-items:center; justify-content:center; '
                            'color:#A8AAB1; font-size:0.8rem;">?</div>',
                            unsafe_allow_html=True,
                        )

                with row[2]:
                    if st.button("↑", key=f"seg_up_{i}", disabled=(i == 0),
                                 help="Move up"):
                        to_move = (i, -1)
                with row[3]:
                    if st.button("↓", key=f"seg_dn_{i}",
                                 disabled=(i == len(segments) - 1),
                                 help="Move down"):
                        to_move = (i, +1)
                with row[4]:
                    if st.button("✕", key=f"seg_rm_{i}", help="Remove"):
                        to_remove = i

                # Hebrew textarea
                seg["text"] = st.text_area(
                    " ",
                    value=seg.get("text", ""),
                    placeholder="הקלד כאן את הטקסט בעברית…",
                    height=110,
                    label_visibility="collapsed",
                    key=f"seg_text_{i}",
                )

                # Estimate
                est = estimate_segment_seconds(seg["text"])
                st.markdown(
                    f'<p class="wz-tiny" style="margin-top:-0.4rem;">'
                    f'≈ {est:.1f}s of audio · {len(seg["text"])} chars'
                    f'</p>',
                    unsafe_allow_html=True,
                )

                # Inline audio preview / regen. Uses the same content-hash
                # cache as step3 (and Supabase Storage), so anything generated
                # here is a cache hit when the user proceeds to render → no
                # double-pay.
                if char and seg.get("text", "").strip():
                    audio_path = audio_path_for_segment(i)
                    # Cheap recovery: if local disk was wiped (Streamlit Cloud
                    # restart) but the audio is in Supabase Storage, pull it
                    # so the player shows on reload. Storage hit is ~100ms,
                    # bit-identical to the original take.
                    if not audio_path.exists():
                        pull_segment_audio_from_storage(audio_path)
                    counters_state = (
                        st.session_state.get("seg_regen_counter") or {}
                    )
                    attempts = int(counters_state.get(str(i), 0))
                    audio_row = st.columns([2.5, 1])
                    with audio_row[0]:
                        if audio_path.exists():
                            st.audio(str(audio_path))
                        else:
                            st.markdown(
                                '<p class="wz-tiny" style="margin:0.4rem 0 0 0;">'
                                'no audio yet — generate to preview pronunciation'
                                '</p>',
                                unsafe_allow_html=True,
                            )
                    with audio_row[1]:
                        label = (
                            "🔄 Regenerate" if audio_path.exists()
                            else "🎙 Generate audio"
                        )
                        if attempts > 0:
                            label += f"  ·  #{attempts + 1}"
                        if st.button(
                            label, key=f"seg_audiogen_{i}", width="stretch",
                            help="Run ElevenLabs TTS for this segment only. "
                                 "Edit the text first to fix a pronunciation; "
                                 "text changes auto-bust the cache.",
                        ):
                            c = creds.read()
                            if not c.elevenlabs:
                                st.error(
                                    "Add **ElevenLabs** key in the Settings panel first."
                                )
                            else:
                                # If the file already exists, the user must
                                # want a fresh V3 take of the same text →
                                # bump the counter so the hash changes.
                                # Otherwise the text just changed or this is
                                # the first take → run with current hash.
                                if audio_path.exists():
                                    new_counters = dict(counters_state)
                                    new_counters[str(i)] = attempts + 1
                                    st.session_state.seg_regen_counter = new_counters
                                target = audio_path_for_segment(i)
                                target.parent.mkdir(parents=True, exist_ok=True)
                                try:
                                    with st.spinner(
                                        f"Generating audio for segment #{i+1}…"
                                    ):
                                        asyncio.run(generate_tts(
                                            text=seg["text"],
                                            voice_id=char.voice.voice_id,
                                            output_path=target,
                                            elevenlabs_api_key=c.elevenlabs,
                                            stability=char.voice.stability,
                                            similarity=char.voice.similarity,
                                            style=char.voice.style,
                                            tempo=char.voice.tempo,
                                        ))
                                    # Persist to cloud so this take survives
                                    # disk wipes and is bit-identical on
                                    # later refine/recovery.
                                    push_segment_audio_to_storage(target)
                                    paths = dict(
                                        st.session_state.get("seg_audio_paths") or {}
                                    )
                                    paths[str(i)] = str(target)
                                    st.session_state.seg_audio_paths = paths
                                except Exception as e:
                                    st.error(f"Audio gen failed: {friendly_error(e)}")
                                else:
                                    st.rerun()

        # Add segment button
        if st.button("+ Add segment", key="seg_add", width="stretch"):
            default_slug = next(iter(cast.keys()))
            add_segment(default_slug, "")
            st.rerun()

    with side:
        # Cost / duration rail
        est = estimate_episode(segments)
        st.markdown(
            f'<div class="wz-card" style="position:sticky; top:1rem;">'
            f'<p class="wz-tiny" style="margin:0 0 0.4rem 0;">ESTIMATE</p>'
            f'<h2 style="margin:0;">{est["audio_secs"]:.0f}s</h2>'
            f'<p class="wz-quiet" style="margin:0.2rem 0 1rem 0;">total audio</p>'
            f'<h2 style="margin:0;">${est["cost_usd"]:.2f}</h2>'
            f'<p class="wz-quiet" style="margin:0.2rem 0 0 0;">render cost</p>'
            f'<hr style="margin:0.8rem 0;">'
            f'<p class="wz-tiny" style="margin:0;">'
            f'{est["segments"]} segment{"s" if est["segments"] != 1 else ""}'
            f'</p>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # Apply mutations after the loop (avoids reordering during render)
    if to_remove is not None:
        remove_segment(to_remove)
        st.rerun()
    if to_move:
        move_segment(*to_move)
        st.rerun()

    # --- Footer nav -----------------------------------------------------------

    st.markdown('<div class="wz-footer"></div>', unsafe_allow_html=True)
    nav_back, _, nav_fwd = st.columns([1, 2, 1])

    with nav_back:
        if st.button("← Back", key="step2_back", width="stretch"):
            go_to(1)
            st.rerun()

    with nav_fwd:
        # Don't disable the button — Streamlit's text_area only commits its
        # value on blur, so a click on a disabled button consumes the blur
        # event and the user has to click again. Instead, leave the button
        # active and validate on click. By the time the click is processed,
        # the textarea has already committed via blur.
        if st.button(
            "Continue to Render  →",
            type="primary",
            width="stretch",
            key="step2_continue",
        ):
            if not segments:
                st.toast("Add at least one segment first", icon="⚠️")
            elif any(not seg.get("text", "").strip() for seg in segments):
                st.toast("Every segment needs Hebrew text", icon="⚠️")
            elif any(seg.get("character") not in cast for seg in segments):
                st.toast("One segment points to a character that no longer exists", icon="⚠️")
            else:
                go_to(3)
                st.rerun()
