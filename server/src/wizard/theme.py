"""Theme + global styling for the wizard.

Single source of truth for all visual choices: palette, fonts, spacing,
component overrides. Inject once near the top of app.py via apply_theme().
"""

import streamlit as st


# --- Palette (also mirrored in .streamlit/config.toml) -------------------------
PALETTE = {
    "bg":          "#1A1D24",   # main background
    "bg_card":     "#252932",   # elevated surface
    "bg_card_hi":  "#2D323D",   # hover / selected
    "border":      "#363B47",
    "border_hi":   "#4A5061",
    "text":        "#F4F2EE",   # main text
    "text_dim":    "#A8AAB1",   # secondary
    "text_quiet":  "#6B6E78",   # tertiary / labels
    "accent":      "#E8B14F",   # warm gold — primary actions
    "accent_dim":  "#C8923A",
    "success":     "#7FBF7F",
    "danger":      "#E07B7B",
}


_CSS = f"""
<style>
  /* ── Fonts ──────────────────────────────────────────────────────── */
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Source+Serif+4:ital,wght@0,400;0,600;1,400&display=swap');

  html, body, [class*="css"], .stApp {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    background: {PALETTE['bg']};
    color: {PALETTE['text']};
  }}

  /* Hide Streamlit's default chrome so the app feels like a product */
  #MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"] {{
    visibility: hidden !important;
    height: 0 !important;
  }}
  header[data-testid="stHeader"] {{
    background: transparent;
    height: auto;
  }}
  /* Pin the sidebar-toggle chevron as a floating button so it's always findable */
  [data-testid="collapsedControl"] {{
    color: {PALETTE['accent']} !important;
    position: fixed !important;
    top: 0.7rem !important;
    left: 0.7rem !important;
    z-index: 999999 !important;
    background: {PALETTE['bg_card']} !important;
    border: 1px solid {PALETTE['border']} !important;
    border-radius: 8px !important;
    padding: 0.35rem 0.55rem !important;
  }}
  [data-testid="collapsedControl"]:hover {{
    background: {PALETTE['bg_card_hi']} !important;
    border-color: {PALETTE['accent']} !important;
  }}
  /* "Settings" hint label next to the chevron, only when sidebar collapsed */
  [data-testid="collapsedControl"]::after {{
    content: " Settings";
    font-size: 0.85rem;
    font-weight: 500;
    margin-left: 0.2rem;
  }}
  .block-container {{
    padding-top: 1.2rem !important;
    padding-bottom: 4rem !important;
    max-width: 1100px;
  }}

  /* ── Typography ─────────────────────────────────────────────────── */
  h1, h2, h3 {{
    font-family: 'Inter', sans-serif !important;
    letter-spacing: -0.015em;
    color: {PALETTE['text']};
  }}
  h1 {{ font-size: 2.0rem; font-weight: 700; line-height: 1.15; }}
  h2 {{ font-size: 1.4rem; font-weight: 600; line-height: 1.2; margin-top: 0.5rem; }}
  h3 {{ font-size: 1.05rem; font-weight: 600; line-height: 1.3; }}

  p, li, .stMarkdown {{ line-height: 1.65; color: {PALETTE['text']}; }}
  .wz-quiet {{ color: {PALETTE['text_dim']}; font-size: 0.9rem; }}
  .wz-tiny  {{ color: {PALETTE['text_quiet']}; font-size: 0.8rem; }}
  .wz-serif {{ font-family: 'Source Serif 4', Georgia, serif !important; }}

  /* ── Step indicator ─────────────────────────────────────────────── */
  .wz-stepper {{
    display: flex; align-items: center; gap: 0;
    margin: 0.5rem 0 2rem 0; padding: 0;
    list-style: none;
  }}
  .wz-step {{
    display: flex; align-items: center; gap: 0.6rem;
    flex: 1;
    color: {PALETTE['text_quiet']}; font-size: 0.92rem; font-weight: 500;
  }}
  .wz-step .dot {{
    width: 28px; height: 28px; border-radius: 999px;
    display: flex; align-items: center; justify-content: center;
    background: {PALETTE['bg_card']};
    border: 1.5px solid {PALETTE['border']};
    font-size: 0.85rem; color: {PALETTE['text_quiet']};
    transition: all 0.2s ease;
  }}
  .wz-step.done .dot {{
    background: {PALETTE['accent']};
    border-color: {PALETTE['accent']};
    color: {PALETTE['bg']};
  }}
  .wz-step.done {{ color: {PALETTE['text_dim']}; }}
  .wz-step.active .dot {{
    background: {PALETTE['accent']};
    border-color: {PALETTE['accent']};
    color: {PALETTE['bg']};
    box-shadow: 0 0 0 4px rgba(232, 177, 79, 0.18);
  }}
  .wz-step.active {{ color: {PALETTE['text']}; }}
  .wz-step .bar {{
    flex: 1; height: 2px; background: {PALETTE['border']};
    margin: 0 0.3rem;
  }}
  .wz-step.done .bar {{ background: {PALETTE['accent']}; }}

  /* ── Cards ───────────────────────────────────────────────────────── */
  .wz-card {{
    background: {PALETTE['bg_card']};
    border: 1px solid {PALETTE['border']};
    border-radius: 12px;
    padding: 1.2rem 1.4rem;
    margin-bottom: 1rem;
    transition: border-color 0.15s, background 0.15s;
  }}
  .wz-card:hover {{ border-color: {PALETTE['border_hi']}; }}
  .wz-card.selected {{
    border-color: {PALETTE['accent']};
    box-shadow: 0 0 0 1px {PALETTE['accent']};
  }}
  .wz-card.empty {{
    border-style: dashed;
    background: transparent;
    color: {PALETTE['text_dim']};
    text-align: center;
    padding: 2.4rem 1rem;
  }}

  /* ── Buttons ─────────────────────────────────────────────────────── */
  .stButton > button, .stDownloadButton > button {{
    border-radius: 8px;
    font-weight: 500;
    border: 1px solid {PALETTE['border']};
    background: {PALETTE['bg_card']};
    color: {PALETTE['text']};
    transition: all 0.15s ease;
    padding: 0.55rem 1.1rem;
  }}
  .stButton > button:hover, .stDownloadButton > button:hover {{
    border-color: {PALETTE['border_hi']};
    background: {PALETTE['bg_card_hi']};
  }}
  /* Primary action: type="primary" */
  .stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] {{
    background: {PALETTE['accent']};
    color: {PALETTE['bg']};
    border-color: {PALETTE['accent']};
    font-weight: 600;
  }}
  .stButton > button[kind="primary"]:hover, .stDownloadButton > button[kind="primary"]:hover {{
    background: {PALETTE['accent_dim']};
    border-color: {PALETTE['accent_dim']};
  }}
  .stButton > button:disabled {{
    opacity: 0.45;
  }}

  /* ── Inputs ──────────────────────────────────────────────────────── */
  .stTextInput > div > div > input,
  .stTextArea textarea,
  .stSelectbox > div > div,
  .stNumberInput > div > div > input {{
    background: {PALETTE['bg']} !important;
    border: 1px solid {PALETTE['border']} !important;
    border-radius: 8px !important;
    color: {PALETTE['text']} !important;
  }}
  .stTextInput > div > div > input:focus,
  .stTextArea textarea:focus {{
    border-color: {PALETTE['accent']} !important;
    box-shadow: 0 0 0 2px rgba(232, 177, 79, 0.18);
  }}
  /* RTL Hebrew textareas — keep this from the original app */
  textarea {{
    direction: rtl;
    text-align: right;
    font-size: 16px;
    line-height: 1.6;
  }}
  /* But the placeholder text should still read LTR */
  textarea::placeholder {{
    direction: rtl;
    text-align: right;
    color: {PALETTE['text_quiet']};
  }}

  /* ── Sidebar (Settings drawer) ───────────────────────────────────── */
  [data-testid="stSidebar"] {{
    background: {PALETTE['bg_card']};
    border-right: 1px solid {PALETTE['border']};
  }}
  [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{
    font-size: 0.95rem; font-weight: 600; letter-spacing: 0.02em;
    text-transform: uppercase;
    color: {PALETTE['text_dim']};
    margin-top: 1.5rem;
  }}

  /* ── Images in candidate grids ───────────────────────────────────── */
  div[data-testid="stImage"] img {{
    border-radius: 10px;
    border: 2px solid transparent;
    transition: border-color 0.15s;
  }}

  /* ── Pills / chips for status badges ─────────────────────────────── */
  .wz-pill {{
    display: inline-block;
    padding: 0.18rem 0.7rem;
    border-radius: 999px;
    font-size: 0.78rem; font-weight: 500;
    background: {PALETTE['bg_card_hi']};
    color: {PALETTE['text_dim']};
    border: 1px solid {PALETTE['border']};
  }}
  .wz-pill.queued  {{ }}
  .wz-pill.running {{ color: {PALETTE['accent']}; border-color: {PALETTE['accent']}; animation: wz-pulse 1.6s ease-in-out infinite; }}
  .wz-pill.done    {{ color: {PALETTE['success']}; border-color: rgba(127,191,127,0.4); }}
  .wz-pill.error   {{ color: {PALETTE['danger']};  border-color: rgba(224,123,123,0.4); }}
  @keyframes wz-pulse {{
    0%, 100% {{ opacity: 1; }}
    50%      {{ opacity: 0.55; }}
  }}

  /* ── Sticky footer for the Continue/Back row ─────────────────────── */
  .wz-footer {{
    position: sticky; bottom: 0;
    background: linear-gradient(to top, {PALETTE['bg']} 70%, rgba(26,29,36,0));
    padding: 1.5rem 0 0.5rem 0;
    margin-top: 2rem;
  }}

  /* ── Misc ────────────────────────────────────────────────────────── */
  hr {{ border-color: {PALETTE['border']}; margin: 1.5rem 0; }}
  /* Smooth out st.divider */
  [data-testid="stDivider"] hr {{ border-color: {PALETTE['border']}; }}
  /* Toast styling */
  div[data-testid="stToast"] {{ background: {PALETTE['bg_card']}; border: 1px solid {PALETTE['border']}; }}
</style>
"""


def apply_theme():
    """Inject the wizard's CSS. Call once at the top of app.py."""
    st.markdown(_CSS, unsafe_allow_html=True)


def step_indicator(current: int, labels: list[str]) -> None:
    """Render a horizontal step indicator. `current` is 1-indexed.

    Each step is 'done' if its index < current, 'active' if ==, otherwise idle.
    """
    parts = ['<ol class="wz-stepper">']
    for i, label in enumerate(labels, start=1):
        klass = "done" if i < current else ("active" if i == current else "")
        glyph = "✓" if i < current else str(i)
        parts.append(
            f'<li class="wz-step {klass}">'
            f'<div class="dot">{glyph}</div>'
            f'<span>{label}</span>'
            + ('<div class="bar"></div>' if i < len(labels) else '')
            + '</li>'
        )
    parts.append("</ol>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def pill(text: str, status: str = "queued") -> str:
    """Return HTML for a status pill. Use inside an st.markdown call."""
    return f'<span class="wz-pill {status}">{text}</span>'
