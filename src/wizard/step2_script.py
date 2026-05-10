"""Step 2 — Script (segment builder).

Title field + vertical list of segment cards. Each card has:
- Avatar + character dropdown (from the cast)
- RTL Hebrew textarea
- Live audio-length estimate
- Reorder up/down + remove buttons

A live "running cost" rail shows total seconds + cost.
"""

from __future__ import annotations

import streamlit as st

from src.wizard.state import (
    add_segment, remove_segment, move_segment, estimate_segment_seconds,
    estimate_episode, go_to,
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
        'Add as many as you like.</p>',
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
        valid = (
            len(segments) > 0
            and all(seg.get("text", "").strip() for seg in segments)
            and all(seg.get("character") in cast for seg in segments)
        )
        if st.button(
            "Continue to Render  →",
            type="primary",
            disabled=not valid,
            width="stretch",
            key="step2_continue",
        ):
            go_to(3)
            st.rerun()
