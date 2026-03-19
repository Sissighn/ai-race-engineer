"""
Speed Delta Charts (Sections 2 & 6).

Exposes three public functions:
    plot_speed_deltas      – combined apex + exit subplot (two-panel)
    plot_apex_speed_share  – standalone apex speed delta bar chart
    plot_exit_speed_delta  – standalone exit speed delta bar chart

The internal helper _plot_single_speed_delta eliminates code duplication
between the two standalone wrapper functions.
"""

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src.logging import get_logger

from ._helpers import (
    _classify_apex_advantage,
    _format_corner_label,
    _format_delta_label,
    _near_equal_mask,
    _sort_by_corner,
)
from ._theme import (
    APEX_SPEED_TIE_THRESHOLD,
    TITLE_LINE_SPACER,
    _safe_plotly_chart,
    dark_layout,
)

logger = get_logger(__name__)


# ── Internal shared renderer ─────────────────────────────────────────────────


def _plot_single_speed_delta(
    df,
    delta_col,
    metric_name,
    driver_a,
    driver_b,
    key,
    context,
    color,
):
    """Render a single signed speed-delta bar chart.

    Shared by plot_apex_speed_share() and plot_exit_speed_delta() to avoid
    code duplication. Colours bars by advantage category, overlays open-circle
    markers for near-equal corners, and ensures all legend states are present
    even when a category has no data (shown as legend-only entries).

    Args:
        df:          DataFrame with columns Corner and *delta_col*.
        delta_col:   Column name holding the signed speed delta values.
        metric_name: Human-readable metric name used in axis/title labels.
        driver_a:    Reference driver name (positive delta = this driver faster).
        driver_b:    Comparison driver name.
        key:         Streamlit widget key.
        context:     Label passed to _safe_plotly_chart for error logging.
        color:       Hex colour for the driver_a advantage bars.
    """
    if (
        df is None
        or df.empty
        or delta_col not in df.columns
        or "Corner" not in df.columns
    ):
        logger.info(
            "Speed delta chart skipped due to missing data",
            metric=metric_name,
            missing_column=delta_col,
        )
        st.info(f"No {metric_name.lower()} delta data available.")
        return

    plot_df = _sort_by_corner(df)
    plot_df = plot_df.dropna(subset=["Corner", delta_col]).copy()

    if plot_df.empty:
        logger.info(
            "Speed delta chart skipped after dropping invalid rows",
            metric=metric_name,
        )
        st.info(f"No {metric_name.lower()} delta data available.")
        return

    plot_df["CornerLabel"] = plot_df["Corner"].apply(_format_corner_label)
    plot_df["Advantage"] = plot_df[delta_col].apply(
        lambda delta: _classify_apex_advantage(delta, driver_a, driver_b)
    )
    plot_df["DeltaLabel"] = plot_df[delta_col].map(_format_delta_label)

    legend_states = [f"{driver_a} faster", f"{driver_b} faster", "Nearly equal"]
    legend_colors = {
        f"{driver_a} faster": color,
        f"{driver_b} faster": "#FFB7D5",
        "Nearly equal": "#FFDD94",
    }
    a_col = legend_colors[f"{driver_a} faster"]
    b_col = legend_colors[f"{driver_b} faster"]
    ne_col = legend_colors["Nearly equal"]

    # Inline colour-coded legend embedded in the chart title.
    legend_line = (
        f"<span style='color:{a_col}'>▲</span> {driver_a} faster"
        f" &nbsp;&nbsp;·&nbsp;&nbsp; "
        f"<span style='color:{b_col}'>▼</span> {driver_b} faster"
        f" &nbsp;&nbsp;·&nbsp;&nbsp; "
        f"<span style='color:{ne_col}'>●</span> Nearly equal"
    )
    chart_title = (
        f"{metric_name} Delta by Corner"
        f"{TITLE_LINE_SPACER}<sup>Δ {metric_name} ({driver_a} - {driver_b})</sup>"
        f"{TITLE_LINE_SPACER}<sup>{legend_line}</sup>"
    )

    fig = px.bar(
        plot_df,
        x="CornerLabel",
        y=delta_col,
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
            delta_col: f"Δ {metric_name} ({driver_a} - {driver_b}) [km/h]",
            "Advantage": "Advantage",
        },
        height=460,
        title=chart_title,
    )

    fig = dark_layout(fig)
    fig.update_layout(margin=dict(t=170, b=50))
    fig.update_traces(
        textposition="outside",
        cliponaxis=False,
        hovertemplate=(
            "<b>%{x}</b><br>"
            + "Delta: %{y:+.1f} km/h<br>"
            + "Faster: %{customdata[0]}"
            + "<extra></extra>"
        ),
    )
    fig.update_xaxes(title_text="Corner")
    fig.update_yaxes(
        title_text=f"Δ {metric_name} ({driver_a} - {driver_b}) [km/h]",
        zeroline=True,
        zerolinecolor="#888",
    )
    fig.add_hline(y=0, line_width=1, line_dash="dash", line_color="#777")

    # Overlay open-circle markers for nearly-equal corners at y=0.
    nearly_equal_df = plot_df[plot_df["Advantage"] == "Nearly equal"]
    if not nearly_equal_df.empty:
        fig.add_trace(
            go.Scatter(
                x=nearly_equal_df["CornerLabel"],
                y=[0.0] * len(nearly_equal_df),
                mode="markers",
                name="Nearly equal marker",
                marker=dict(
                    symbol="circle-open",
                    size=12,
                    color=legend_colors["Nearly equal"],
                    line=dict(color=legend_colors["Nearly equal"], width=2),
                ),
                text=nearly_equal_df["DeltaLabel"],
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    + "Delta: %{text}<br>"
                    + "Status: Nearly equal<extra></extra>"
                ),
                showlegend=False,
            )
        )

    # Guarantee all three legend entries exist even when a category is absent.
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

    _safe_plotly_chart(fig, key=key, context=context)


# ── Public functions ──────────────────────────────────────────────────────────


def plot_speed_deltas(df, driver_a, driver_b, key="speed_deltas"):
    """Render a two-panel subplot showing apex and exit speed deltas per corner.

    Both panels share the same x-axis (corner labels) and display signed deltas
    (driver_a − driver_b). Corners within the tie threshold are highlighted with
    open-circle scatter markers instead of bars.

    Args:
        df:       DataFrame with columns: Corner, Delta_ApexSpeed, Delta_ExitSpeed.
        driver_a: Reference driver name (positive delta = this driver faster).
        driver_b: Comparison driver name.
        key:      Streamlit widget key.
    """
    if (
        df is None
        or df.empty
        or "Corner" not in df.columns
        or "Delta_ApexSpeed" not in df.columns
        or "Delta_ExitSpeed" not in df.columns
    ):
        logger.info("No data for speed deltas", driver_a=driver_a, driver_b=driver_b)
        st.info("No speed delta data available.")
        return

    plot_df = _sort_by_corner(df)
    plot_df = plot_df.dropna(subset=["Corner", "Delta_ApexSpeed", "Delta_ExitSpeed"])

    if plot_df.empty:
        logger.info(
            "Speed deltas skipped after dropping invalid rows",
            driver_a=driver_a,
            driver_b=driver_b,
        )
        st.info("No speed delta data available.")
        return

    plot_df = plot_df.copy()
    plot_df["CornerLabel"] = plot_df["Corner"].apply(_format_corner_label)
    plot_df["ApexWinner"] = plot_df["Delta_ApexSpeed"].apply(
        lambda delta: _classify_apex_advantage(delta, driver_a, driver_b)
    )
    plot_df["ExitWinner"] = plot_df["Delta_ExitSpeed"].apply(
        lambda delta: _classify_apex_advantage(delta, driver_a, driver_b)
    )

    title_main = "Speed Delta Comparison by Corner"
    title_sub = f"Signed Δ Speed ({driver_a} - {driver_b})"
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.14,
        subplot_titles=("Apex Speed Delta", "Exit Speed Delta"),
    )

    # Panel 1 – Apex Speed Delta
    fig.add_trace(
        go.Bar(
            x=plot_df["CornerLabel"],
            y=plot_df["Delta_ApexSpeed"],
            text=plot_df["Delta_ApexSpeed"].map(_format_delta_label),
            textposition="outside",
            cliponaxis=False,
            customdata=plot_df["ApexWinner"],
            name="Apex Speed Delta",
            marker_color="#A48FFF",
            hovertemplate=(
                "<b>%{x}</b><br>"
                + "Metric: Apex Speed<br>"
                + "Delta: %{y:+.1f} km/h<br>"
                + "Status: %{customdata}<extra></extra>"
            ),
            showlegend=False,
        ),
        row=1,
        col=1,
    )

    # Panel 2 – Exit Speed Delta
    fig.add_trace(
        go.Bar(
            x=plot_df["CornerLabel"],
            y=plot_df["Delta_ExitSpeed"],
            text=plot_df["Delta_ExitSpeed"].map(_format_delta_label),
            textposition="outside",
            cliponaxis=False,
            customdata=plot_df["ExitWinner"],
            name="Exit Speed Delta",
            marker_color="#8FD3FE",
            hovertemplate=(
                "<b>%{x}</b><br>"
                + "Metric: Exit Speed<br>"
                + "Delta: %{y:+.1f} km/h<br>"
                + "Status: %{customdata}<extra></extra>"
            ),
            showlegend=False,
        ),
        row=2,
        col=1,
    )

    # Overlay nearly-equal markers on both panels.
    apex_nearly_equal = plot_df[_near_equal_mask(plot_df["Delta_ApexSpeed"])]
    if not apex_nearly_equal.empty:
        fig.add_trace(
            go.Scatter(
                x=apex_nearly_equal["CornerLabel"],
                y=[0.0] * len(apex_nearly_equal),
                mode="markers",
                marker=dict(
                    symbol="circle-open",
                    size=11,
                    color="#8FD3FE",
                    line=dict(color="#8FD3FE", width=2),
                ),
                text=apex_nearly_equal["Delta_ApexSpeed"].map(_format_delta_label),
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    + "Metric: Apex Speed<br>"
                    + "Delta: %{text}<br>"
                    + "Status: Nearly equal<extra></extra>"
                ),
                showlegend=False,
            ),
            row=1,
            col=1,
        )

    exit_nearly_equal = plot_df[_near_equal_mask(plot_df["Delta_ExitSpeed"])]
    if not exit_nearly_equal.empty:
        fig.add_trace(
            go.Scatter(
                x=exit_nearly_equal["CornerLabel"],
                y=[0.0] * len(exit_nearly_equal),
                mode="markers",
                marker=dict(
                    symbol="circle-open",
                    size=11,
                    color="#8FD3FE",
                    line=dict(color="#8FD3FE", width=2),
                ),
                text=exit_nearly_equal["Delta_ExitSpeed"].map(_format_delta_label),
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    + "Metric: Exit Speed<br>"
                    + "Delta: %{text}<br>"
                    + "Status: Nearly equal<extra></extra>"
                ),
                showlegend=False,
            ),
            row=2,
            col=1,
        )

    fig = dark_layout(fig, f"{title_main}<br><sup>{title_sub}</sup>")
    fig.update_layout(
        height=640,
        margin=dict(l=40, r=40, t=140, b=40),
        title=dict(x=0.0, xanchor="left", y=0.98, yanchor="top"),
    )
    fig.update_xaxes(title_text="Corner", row=2, col=1)
    fig.update_yaxes(
        title_text=f"Δ Apex Speed ({driver_a} - {driver_b}) [km/h]",
        zeroline=True,
        zerolinecolor="#888",
        row=1,
        col=1,
    )
    fig.update_yaxes(
        title_text=f"Δ Exit Speed ({driver_a} - {driver_b}) [km/h]",
        zeroline=True,
        zerolinecolor="#888",
        row=2,
        col=1,
    )
    fig.add_hline(y=0, line_width=1, line_dash="dash", line_color="#777", row=1, col=1)
    fig.add_hline(y=0, line_width=1, line_dash="dash", line_color="#777", row=2, col=1)
    fig.add_annotation(
        text=(
            f"Positive: {driver_a} faster | Negative: {driver_b} faster | "
            f"0: effectively equal"
        ),
        xref="paper",
        yref="paper",
        x=0,
        y=1.06,
        showarrow=False,
        align="left",
        font=dict(size=11, color="#BBBBBB"),
    )

    _safe_plotly_chart(fig, key=key, context="speed_deltas")


def plot_apex_speed_share(
    df,
    driver_a="Driver A",
    driver_b="Driver B",
    key="apex_share",
):
    """Bar chart of apex speed delta (driver_a − driver_b) per corner.

    Wrapper around _plot_single_speed_delta for the Delta_ApexSpeed column.
    """
    _plot_single_speed_delta(
        df=df,
        delta_col="Delta_ApexSpeed",
        metric_name="Apex Speed",
        driver_a=driver_a,
        driver_b=driver_b,
        key=key,
        context="apex_speed_share",
        color="#A48FFF",
    )


def plot_exit_speed_delta(
    df,
    driver_a="Driver A",
    driver_b="Driver B",
    key="exit_speed_delta",
):
    """Bar chart of exit speed delta (driver_a − driver_b) per corner.

    Wrapper around _plot_single_speed_delta for the Delta_ExitSpeed column.
    """
    _plot_single_speed_delta(
        df=df,
        delta_col="Delta_ExitSpeed",
        metric_name="Exit Speed",
        driver_a=driver_a,
        driver_b=driver_b,
        key=key,
        context="exit_speed_delta",
        color="#8FD3FE",
    )
