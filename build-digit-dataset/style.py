"""
style.py
--------
Shared CSS + tiny layout helpers so the Collect and Review pages look like
one app instead of two independently-styled scripts.
"""

from typing import Optional

import streamlit as st

CUSTOM_CSS = """
<style>
    .block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 1200px; }

    h1.app-title { font-size: 2.1rem; font-weight: 800; margin-bottom: 0.1rem; }
    p.app-subtitle { color: #64748b; font-size: 1.02rem; margin-top: 0; margin-bottom: 1.6rem; }

    .stage-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 14px 14px 10px 14px;
        text-align: center;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
    }
    .stage-card h4 { margin: 0 0 8px 0; font-size: 0.92rem; color: #334155; font-weight: 700; }

    .final-card {
        background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
        border: 1px solid #e2e8f0;
        border-radius: 18px;
        padding: 20px;
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.06);
    }

    .metric-pill {
        display: inline-block;
        background: #eef2ff;
        color: #4338ca;
        border-radius: 999px;
        padding: 3px 12px;
        font-size: 0.8rem;
        font-weight: 600;
        margin: 0 6px 6px 0;
    }
    /* Digit counters on the Collect sidebar: green once a digit has enough
       approved samples, so a contributor can see at a glance what's still
       thin without reading ten numbers. */
    .metric-pill.done { background: #dcfce7; color: #15803d; }
    .metric-pill.thin { background: #fef3c7; color: #b45309; }

    [data-testid="stVerticalBlockBorderWrapper"] { border-radius: 14px; }
    section[data-testid="stSidebar"] { border-right: 1px solid #e2e8f0; }
</style>
"""


def inject() -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def page_header(title: str, subtitle: str) -> None:
    st.markdown(f'<h1 class="app-title">{title}</h1>', unsafe_allow_html=True)
    st.markdown(f'<p class="app-subtitle">{subtitle}</p>', unsafe_allow_html=True)


def image_card(
    data_uri: str,
    title: Optional[str] = None,
    css_class: str = "stage-card",
    alt: str = "",
    stretch: bool = True,
    pixelated: bool = False,
) -> str:
    """One self-contained card -- optional heading plus the image -- as a
    single HTML string.

    Streamlit sanitizes every st.markdown call on its own, so an opening
    <div> in one call and a closing </div> in another never wrap anything:
    the div gets auto-closed where it opened and renders as an empty box,
    with the st.image below it sitting outside the card entirely. Emitting
    the heading, the border and the picture together (the image inlined as a
    data: URI) is what makes the card actually enclose its contents.
    """
    heading = f"<h4>{title}</h4>" if title else ""
    width = "width:100%;" if stretch else "max-width:100%;"
    rendering = "image-rendering:pixelated;" if pixelated else ""
    return (
        f'<div class="{css_class}">{heading}'
        f'<img src="{data_uri}" alt="{alt}" '
        f'style="{width}{rendering}display:block;margin:0 auto;border-radius:8px" />'
        f"</div>"
    )


def pills(values: dict, target: Optional[int] = None) -> str:
    """Render {label: count} as rounded pill badges.

    With `target`, each pill is colored by how close it is to that many
    samples -- green at or above, amber below.
    """
    out = []
    for k, v in values.items():
        cls = "metric-pill"
        if target:
            cls += " done" if v >= target else " thin"
        out.append(f'<span class="{cls}">{k}: {v}</span>')
    return "".join(out)
