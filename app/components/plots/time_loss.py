"""
Time Loss Bar Chart (Section 1).

Exposes one public function:
    plot_time_loss_bar – signed diverging bar chart of per-corner time delta,
                         with open-circle markers for nearly-equal corners and
                         a guaranteed complete legend regardless of which
                         advantage categories appear in the data.
"""

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.logging import get_logger

from ._helpers import _format_corner_label, _format_time_label, _sort_by_corner
from ._theme import (
    TIME_LOSS_TIE_THRESHOLD,
    TITLE_LINE_SPACER,
    _safe_plotly_chart,
    dark_layout,
)

logger = get_logger(__name__)


def plot_time_loss_bar(
    df,
    driver_a: str = "Driver A",
    driver_b: str = "Driver B",
    key: str = "time_loss_bar",
):
    """Signed diverging bar chart: Lap Time Delta per Corner (driver_a − driver_b).

    Sign convention (mirrors speed-delta charts):
      TimeLoss > 0  →  driver_a gains time  (driver_b is slower)
      TimeLoss < 0  →  driver_b gains time  (driver_a is slower)
      |TimeLoss| ≤ TIME_LOSS_TIE_THRESHOLD  →  Nearly equal

    Args:
        df:       DataFrame with columns Corner and TimeLoss.
        driver_a: Reference driver name (positive delta = this driver gains time).
        driver_b: Comparison driver name.
        key:      Streamlit widget key.
    """
    if (
        df is None
        or df.empty
        or "TimeLoss" not in df.columns
        or "Corner" not in df.columns
    ):
        logger.info("No data for time loss chart")
        st.info("No time loss data available.")
        return

    plot_df = _sort_by_corner(df).dropna(subset=["Corner", "TimeLoss"]).copy()
    if plot_df.empty:
        st.info("No time loss data available.")
        return

    plot_df["CornerLabel"] = plot_df["Corner"].apply(_format_corner_label)
    plot_df["DeltaLabel"] = plot_df["TimeLoss"].map(_format_time_label)
    plot_df["Advantage"] = plot_df["TimeLoss"].apply(
        lambda v: (
            f"{driver_a} gains"
            if v > TIME_LOSS_TIE_THRESHOLD
            else (
                f"{driver_b} gains" if v < -TIME_LOSS_TIE_THRESHOLD else "Nearly equal"
            )
        )
    )

    legend_states = [f"{driver_a} gains", f"{driver_b} gains", "Nearly equal"]
    legend_colors = {
        f"{driver_a} gains": "#A48FFF",
        f"{driver_b} gains": "#FFB7D5",
        "Nearly equal": "#FFDD94",
    }
    a_col = legend_colors[f"{driver_a} gains"]
    b_col = legend_colors[f"{driver_b} gains"]
    ne_col = legend_colors["Nearly equal"]

    # Build the inline colour-coded legend embedded in the chart title.
    legend_line = (
        f"<span style='color:{a_col}'>▲</span> {driver_a} gains time"
        f" &nbsp;&nbsp;·&nbsp;&nbsp; "
        f"<span style='color:{b_col}'>▼</span> {driver_b} gains time"
        f" &nbsp;&nbsp;·&nbsp;&nbsp; "
        f"<span style='color:{ne_col}'>●</span> Nearly equal"
    )
    chart_title = (
        f"Lap Time Delta per Corner"
        f"{TITLE_LINE_SPACER}<sup>Δ Time ({driver_a} − {driver_b}) [s]</sup>"
        f"{TITLE_LINE_SPACER}<sup>{legend_line}</sup>"
    )

    fig = px.bar(
        plot_df,
        x="CornerLabel",
        y="TimeLoss",
        color="Advantage",
        text="DeltaLabel",
        custom_data=["Advantage"],
        category_orders={
            "CornerLabel": plot_df["CornerLabel"].tolist(),
            "Advantage": legend_states,
        },
        color_discrete_map=legend_colors,
        labels={
            "CornerLabel": "Corner",
            "TimeLoss": f"Δ Time ({driver_a} − {driver_b}) [s]",
            "Advantage": "Advantage",
        },
        height=420,
        title=chart_title,
    )

    fig = dark_layout(fig)
    fig.update_layout(margin=dict(t=170, b=50))
    fig.update_traces(
        textposition="outside",
        cliponaxis=False,
        hovertemplate=(
            "<b>%{x}</b><br>"
            + "Δ Time: %{y:+.3f}s<br>"
            + "Outcome: %{customdata[0]}<br>"
            + "<extra></extra>"
        ),
    )
    fig.update_xaxes(title_text="Corner")
    fig.update_yaxes(
        title_text=f"Δ Time ({driver_a} − {driver_b}) [s]",
        zeroline=True,
        zerolinecolor="#888",
    )
    fig.add_hline(y=0, line_width=1, line_dash="dash", line_color="#777")

    # Overlay open-circle markers on nearly-equal corners so they are visible
    # at y=0 even though their bar height is effectively zero.
    ne_df = plot_df[plot_df["Advantage"] == "Nearly equal"]
    if not ne_df.empty:
        fig.add_trace(
            go.Scatter(
                x=ne_df["CornerLabel"],
                y=[0.0] * len(ne_df),
                mode="markers",
                name="Nearly equal marker",
                marker=dict(
                    symbol="circle-open",
                    size=12,
                    color=ne_col,
                    line=dict(color=ne_col, width=2),
                ),
                text=ne_df["DeltaLabel"],
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    + "Δ Time: %{text}<br>"
                    + "Status: Nearly equal<extra></extra>"
                ),
                showlegend=False,
            )
        )

    # Guarantee all three legend entries are always present, even when a
    # category has no data rows (shown as legend-only, non-interactive items).
    present_states = set(plot_df["Advantage"].unique())
    for state in legend_states:
        if state not in present_states:
            fig.add_trace(
                go.Bar(
                    x=[None],
                    y=[None],
                    name=state,
                    marker_color=legend_colors[state],
                    showlegend=True,
                    visible="legendonly",
                    hoverinfo="skip",
                )
            )

    _safe_plotly_chart(fig, key=key, context="time_loss_bar")
