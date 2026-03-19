"""
Corner Type Performance Chart (Section 8).

Exposes one public function:
    plot_corner_type_performance – bar chart of cumulative time delta grouped
                                   by corner speed category (Low / Medium / High).
"""

import plotly.express as px
import streamlit as st

from ._theme import DARK_BG, DARK_PAPER, TEXT_COLOR, _safe_plotly_chart


def plot_corner_type_performance(agg_df, key="corner_type_perf"):
    """Bar chart showing cumulative time delta grouped by corner speed category
    (Low / Medium / High Speed).

    Each bar represents the total signed time delta accumulated across all
    corners of that speed category, giving a quick overview of where a driver
    loses or gains time most systematically.

    Args:
        agg_df: Aggregated DataFrame with columns CornerType and TimeLoss.
        key:    Streamlit widget key.
    """
    if agg_df is None or agg_df.empty:
        st.info("No classification data available.")
        return

    color_map = {
        "Low Speed": "#FFDD94",    # yellow
        "Medium Speed": "#8FD3FE", # blue
        "High Speed": "#FFB7D5",   # pink/red
    }

    fig = px.bar(
        agg_df,
        x="CornerType",
        y="TimeLoss",
        text="TimeLoss",
        title="Time Loss by Corner Category",
        color="CornerType",
        color_discrete_map=color_map,
    )

    fig.update_traces(
        texttemplate="%{text:.3f}s",
        textposition="outside",
        width=0.5,  # keep bars from looking too heavy
    )

    fig.update_layout(
        template="plotly_dark",
        plot_bgcolor=DARK_BG,
        paper_bgcolor=DARK_PAPER,
        font_color=TEXT_COLOR,
        showlegend=False,
        yaxis=dict(title="Total Time Delta (s)", zeroline=True, zerolinecolor="#555"),
        xaxis=dict(title=""),
    )

    _safe_plotly_chart(fig, key=key, context="corner_type_performance")
