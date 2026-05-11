"""
Shared dark-theme constants, layout helper, and safe render wrapper.

All chart modules import their visual settings from here to ensure
consistent styling across the entire dashboard. Nothing in this module
produces side effects on import.
"""

import streamlit as st

from src.logging import get_logger

logger = get_logger(__name__)

# ── Background & text ────────────────────────────────────────────────────────
DARK_BG = "#141414"
DARK_PAPER = "#191919"
TEXT_COLOR = "#FFFFFF"

# Invisible spacer injected between title rows to add vertical breathing room.
TITLE_LINE_SPACER = "<br><span style='font-size:8px;line-height:8px'>&nbsp;</span>"

# Ordered colour palette used across all charts.
PASTEL_COLORS = ["#A48FFF", "#FFB7D5", "#8FD3FE", "#FFDD94", "#C9F7C5", "#FDCFE8"]

# ── Tie thresholds ───────────────────────────────────────────────────────────
# Speed differences below this value (km/h) are displayed as "Nearly equal".
APEX_SPEED_TIE_THRESHOLD = 0.1
# Time differences below this value (s) are treated as negligible.
TIME_LOSS_TIE_THRESHOLD = 0.010  # 10 ms – below this a corner time delta is negligible


def _safe_plotly_chart(fig, key=None, context="plot"):
    """Render a Plotly figure inside Streamlit, catching and logging any errors.

    Args:
        fig:     The Plotly figure object to render.
        key:     Optional Streamlit widget key (prevents re-render collisions).
        context: Human-readable label used in error logs to identify the chart.
    """
    try:
        st.plotly_chart(fig, use_column_width=True, key=key)
    except Exception as e:
        logger.error(
            "Failed to render plot", context=context, key=str(key), error=str(e)
        )
        st.warning("A chart could not be rendered.")


def dark_layout(fig, title=None):
    """Apply the shared dark-theme layout to a Plotly figure.

    Sets background colours, font colour, hover mode, and default margins.
    Optionally updates the chart title if provided.

    Args:
        fig:   Plotly figure to modify in-place.
        title: Optional title string (supports HTML/Plotly markup).

    Returns:
        The same figure with the dark theme applied.
    """
    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor=DARK_BG,
        paper_bgcolor=DARK_PAPER,
        font_color=TEXT_COLOR,
        title_font=dict(size=22, color=TEXT_COLOR),
        hovermode="x unified",
        margin=dict(l=40, r=40, t=80, b=40),
    )
    if title:
        fig.update_layout(title=title)
    return fig
