"""
Plotting components for the AI Race Engineer dashboard.

All chart functions follow the same contract:
  - Accept a DataFrame (or telemetry Series) plus driver name strings.
  - Return nothing; they render directly into the active Streamlit page via
    _safe_plotly_chart(), which handles exceptions gracefully.
  - Apply the shared dark theme through dark_layout().

Section index
─────────────
  1  Time Loss Bar Chart
  2  Speed Deltas – Apex & Exit (combined subplot)
  3  Speed Profile – line plot
  4  Brake & Throttle Inputs
  5  Gear Usage – donut chart
  6  Standalone Speed Delta Charts (apex / exit wrappers)
  7  Driver DNA Comparison – horizontal grouped bars
  8  Corner Type Performance
"""

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import streamlit as st
from plotly.subplots import make_subplots

from src.logging import get_logger

logger = get_logger(__name__)

# -------------------------------------------------------
# GLOBAL DARK THEME
# -------------------------------------------------------
DARK_BG = "#141414"
DARK_PAPER = "#191919"
TEXT_COLOR = "#FFFFFF"
TITLE_LINE_SPACER = "<br><span style='font-size:8px;line-height:8px'>&nbsp;</span>"

PASTEL_COLORS = ["#A48FFF", "#FFB7D5", "#8FD3FE", "#FFDD94", "#C9F7C5", "#FDCFE8"]
APEX_SPEED_TIE_THRESHOLD = 0.1
TIME_LOSS_TIE_THRESHOLD = 0.010  # 10 ms – below this a corner time delta is negligible

DNA_METRIC_META = {
    "Aggressiveness": {
        "label": "Braking Aggressiveness",
        "description": "Derived from high deceleration events in braking zones.",
    },
    "Cornering": {
        "label": "Corner Speed Profile",
        "description": "Derived from average speed in cornering phases.",
    },
    "Smoothness": {
        "label": "Throttle Smoothness",
        "description": "Derived from throttle input stability during transitions.",
    },
    "FullThrottle": {
        "label": "Full-Throttle Usage",
        "description": "Derived from the share of telemetry samples at near-full throttle.",
    },
    "GearWorkload": {
        "label": "Gear Shift Activity",
        "description": "Derived from total gear-change activity over the lap.",
    },
}

DNA_METRIC_ORDER = [
    "Aggressiveness",
    "Cornering",
    "Smoothness",
    "FullThrottle",
    "GearWorkload",
]


def _safe_plotly_chart(fig, key=None, context="plot"):
    """Render a Plotly figure inside Streamlit, catching and logging any errors.

    Args:
        fig:     The Plotly figure object to render.
        key:     Optional Streamlit widget key (prevents re-render collisions).
        context: Human-readable label used in error logs to identify the chart.
    """
    try:
        st.plotly_chart(fig, width="stretch", key=key)
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


def _format_corner_label(corner_value):
    """Convert a raw corner identifier to a human-readable label.

    Converts numeric values to integers to avoid labels like "Corner 3.0".
    Falls back to a string representation when conversion is not possible.
    """
    try:
        return f"Corner {int(corner_value)}"
    except (TypeError, ValueError):
        return f"Corner {corner_value}"


def _sort_by_corner(df):
    """Return a copy of *df* sorted by corner number in ascending order.

    Coerces the Corner column to numeric for correct ordering (so Corner 10
    comes after Corner 9, not after Corner 1). Non-numeric corners are sorted
    after numeric ones via the stable secondary sort on the raw Corner column.
    The temporary sort key column is dropped before returning.
    """
    plot_df = df.copy()
    plot_df["_corner_sort"] = pd.to_numeric(plot_df["Corner"], errors="coerce")
    plot_df = plot_df.sort_values(["_corner_sort", "Corner"], kind="stable")
    return plot_df.drop(columns=["_corner_sort"])


def _classify_apex_advantage(delta, driver_a, driver_b):
    """Map a signed speed delta (driver_a − driver_b) to a categorical advantage label.

    Values within ±APEX_SPEED_TIE_THRESHOLD are treated as a tie to avoid
    surfacing noise in the telemetry as meaningful differences.
    """
    if delta > APEX_SPEED_TIE_THRESHOLD:
        return f"{driver_a} faster"
    if delta < -APEX_SPEED_TIE_THRESHOLD:
        return f"{driver_b} faster"
    return "Nearly equal"


def _format_delta_label(value):
    """Format a speed delta value for display on bar chart labels.

    Returns '≈0 km/h' for values within the tie threshold to make
    negligible differences visually obvious at a glance.
    """
    return "≈0 km/h" if abs(value) <= APEX_SPEED_TIE_THRESHOLD else f"{value:+.1f} km/h"


def _format_time_label(value: float) -> str:
    """Format a lap-time delta value for bar labels (millisecond precision)."""
    return "≈0s" if abs(value) <= TIME_LOSS_TIE_THRESHOLD else f"{value:+.3f}s"


def _near_equal_mask(series: pd.Series) -> pd.Series:
    """Return a boolean mask that is True where values are within the tie threshold.

    Used to identify 'Nearly equal' corners so they can receive a special
    open-circle marker on delta charts instead of a bar.
    """
    return series.abs() <= APEX_SPEED_TIE_THRESHOLD


# -------------------------------------------------------
# 1) TIME LOSS BAR CHART
# -------------------------------------------------------
def plot_time_loss_bar(
    df,
    driver_a: str = "Driver A",
    driver_b: str = "Driver B",
    key: str = "time_loss_bar",
):
    """
    Signed diverging bar chart: Lap Time Delta per Corner (driver_a − driver_b).

    Sign convention (mirrors speed-delta charts):
      TimeLoss > 0  →  driver_a gains time  (driver_b is slower)
      TimeLoss < 0  →  driver_b gains time  (driver_a is slower)
      |TimeLoss| ≤ TIME_LOSS_TIE_THRESHOLD  →  Nearly equal
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


# -------------------------------------------------------
# 2) SPEED DELTAS – APEX & EXIT
# -------------------------------------------------------
def plot_speed_deltas(df, driver_a, driver_b, key="speed_deltas"):
    """Render a two-panel subplot showing apex and exit speed deltas per corner.

    Both panels share the same x-axis (corner labels) and display signed deltas
    (driver_a − driver_b). Corners within the tie threshold are highlighted with
    open-circle scatter markers instead of bars.

    Args:
        df:       DataFrame with columns: Corner, Delta_ApexSpeed, Delta_ExitSpeed.
        driver_a: Name of the reference driver (positive delta = this driver faster).
        driver_b: Name of the comparison driver.
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


# -------------------------------------------------------
# 3) SPEED PROFILE – LINE PLOT
# -------------------------------------------------------
def plot_speed_profile(telA, telB, driverA, driverB, key="speed_profile"):
    """Overlay both drivers' speed traces on a single Distance vs Speed line chart.

    Args:
        telA:    Telemetry DataFrame for driver A (must contain Distance, Speed).
        telB:    Telemetry DataFrame for driver B (must contain Distance, Speed).
        driverA: Display name for driver A.
        driverB: Display name for driver B.
        key:     Streamlit widget key.
    """
    if telA is None or telB is None or telA.empty or telB.empty:
        logger.warning(
            "Missing telemetry for speed profile", driver_a=driverA, driver_b=driverB
        )
        st.info("Speed profile unavailable.")
        return

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=telA["Distance"],
            y=telA["Speed"],
            mode="lines",
            name=f"{driverA} Speed",
            line=dict(color="#A48FFF", width=2),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=telB["Distance"],
            y=telB["Speed"],
            mode="lines",
            name=f"{driverB} Speed",
            line=dict(color="#FFB7D5", width=2),
        )
    )

    fig = dark_layout(fig, f"Speed Profile – {driverA} vs {driverB}")
    fig.update_xaxes(title_text="Distance (m)")
    fig.update_yaxes(title_text="Speed (km/h)")

    _safe_plotly_chart(fig, key=key, context="speed_profile")


# -------------------------------------------------------
# 4) BRAKE & THROTTLE INPUTS
# -------------------------------------------------------
def plot_brake_throttle(telA, telB, driverA, driverB, key="brake_throttle"):
    """Overlay brake and throttle traces for both drivers against lap distance.

    Four traces are drawn in total: brake and throttle for each driver, each
    with a distinct colour so inputs can be compared at every point on track.

    Args:
        telA:    Telemetry DataFrame for driver A (must contain Distance, Brake, Throttle).
        telB:    Telemetry DataFrame for driver B (must contain Distance, Brake, Throttle).
        driverA: Display name for driver A.
        driverB: Display name for driver B.
        key:     Streamlit widget key.
    """
    if telA is None or telB is None or telA.empty or telB.empty:
        logger.warning(
            "Missing telemetry for brake/throttle plot",
            driver_a=driverA,
            driver_b=driverB,
        )
        st.info("Brake/Throttle plot unavailable.")
        return

    fig = go.Figure()

    # --- Driver A ---
    fig.add_trace(
        go.Scatter(
            x=telA["Distance"],
            y=telA["Brake"],
            name=f"{driverA} Brake",
            mode="lines",
            line=dict(color="#A48FFF", width=2),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=telA["Distance"],
            y=telA["Throttle"],
            name=f"{driverA} Throttle",
            mode="lines",
            line=dict(color="#8FD3FE", width=2),
        )
    )

    # --- Driver B ---
    fig.add_trace(
        go.Scatter(
            x=telB["Distance"],
            y=telB["Brake"],
            name=f"{driverB} Brake",
            mode="lines",
            line=dict(color="#FFB7D5", width=2),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=telB["Distance"],
            y=telB["Throttle"],
            name=f"{driverB} Throttle",
            mode="lines",
            line=dict(color="#FFDD94", width=2),
        )
    )

    fig = dark_layout(fig, f"Brake & Throttle – {driverA} vs {driverB}")
    fig.update_xaxes(title_text="Distance (m)")
    fig.update_yaxes(title_text="Input (%)")

    _safe_plotly_chart(fig, key=key, context="brake_throttle")


# -------------------------------------------------------
# 5) GEAR USAGE – DONUT
# -------------------------------------------------------
def plot_gear_usage(tel, driver, key=None):
    """Render a donut chart showing the distribution of gear usage across a lap.

    Args:
        tel:    Telemetry DataFrame containing the nGear column.
        driver: Driver display name (used in the chart title and default key).
        key:    Streamlit widget key. Derived from the driver name if omitted.
    """
    # Fall back to a driver-derived key if none is provided by the caller
    if key is None:
        key = f"gear_usage_{driver}"

    if tel is None or tel.empty or "nGear" not in tel.columns:
        logger.warning("Missing nGear data for gear usage", driver=driver)
        st.info(f"No gear usage data for {driver}.")
        return

    gear_counts = tel["nGear"].value_counts().sort_index()

    fig = px.pie(
        values=gear_counts.values,
        names=gear_counts.index,
        hole=0.55,
        title=f"Gear Usage – {driver}",
        color_discrete_sequence=PASTEL_COLORS,
    )

    fig = dark_layout(fig)
    _safe_plotly_chart(fig, key=key, context="gear_usage")


# -------------------------------------------------------
# 6) STANDALONE SPEED DELTA CHARTS
# -------------------------------------------------------
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
    """Internal helper that renders a single signed speed-delta bar chart.

    Shared by plot_apex_speed_share() and plot_exit_speed_delta() to avoid
    code duplication. Colours bars by advantage category, overlays open-circle
    markers for near-equal corners, and ensures all legend states are present
    even when a category has no data (shown as legend-only entries).

    Args:
        df:          DataFrame with columns Corner and *delta_col*.
        delta_col:   Column name holding the signed speed delta values.
        metric_name: Human-readable metric name used in axis/title labels.
        driver_a:    Name of the reference driver (positive = this driver faster).
        driver_b:    Name of the comparison driver.
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

    legend_states = [
        f"{driver_a} faster",
        f"{driver_b} faster",
        "Nearly equal",
    ]
    legend_colors = {
        f"{driver_a} faster": color,
        f"{driver_b} faster": "#FFB7D5",
        "Nearly equal": "#FFDD94",
    }
    a_col = legend_colors[f"{driver_a} faster"]
    b_col = legend_colors[f"{driver_b} faster"]
    ne_col = legend_colors["Nearly equal"]
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


# -------------------------------------------------------
# 7) DRIVER DNA COMPARISON
# -------------------------------------------------------
def plot_driver_dna(dna_df, driver_a, driver_b, key="driver_dna_radar"):
    """
    Plots telemetry-derived driver style scores in a grouped horizontal bar chart.

    Note: Scores are normalized heuristics on a 0-100 scale and should be read as
    relative style indicators, not absolute performance ratings.
    """
    if dna_df is None or dna_df.empty:
        logger.warning(
            "No data for driver DNA chart", driver_a=driver_a, driver_b=driver_b
        )
        st.info("Driver DNA chart unavailable.")
        return

    required_cols = {"Metric", driver_a, driver_b}
    if not required_cols.issubset(set(dna_df.columns)):
        logger.warning(
            "Driver DNA chart missing required columns",
            required=list(required_cols),
            available=list(dna_df.columns),
            driver_a=driver_a,
            driver_b=driver_b,
        )
        st.info("Driver DNA chart unavailable.")
        return

    plot_df = dna_df.copy()
    plot_df["MetricLabel"] = plot_df["Metric"].apply(
        lambda m: DNA_METRIC_META.get(m, {}).get("label", m)
    )
    plot_df["MetricDescription"] = plot_df["Metric"].apply(
        lambda m: DNA_METRIC_META.get(
            m,
            {},
        ).get(
            "description",
            "Telemetry-derived normalized style score.",
        )
    )

    ordered_metrics = [m for m in DNA_METRIC_ORDER if m in plot_df["Metric"].values]
    ordered_metrics += [
        m for m in plot_df["Metric"].values if m not in set(ordered_metrics)
    ]
    ordered_labels = [
        DNA_METRIC_META.get(metric, {}).get("label", metric)
        for metric in ordered_metrics
    ]

    long_df = plot_df.melt(
        id_vars=["Metric", "MetricLabel", "MetricDescription"],
        value_vars=[driver_a, driver_b],
        var_name="Driver",
        value_name="Score",
    )

    fig = px.bar(
        long_df,
        x="Score",
        y="MetricLabel",
        color="Driver",
        orientation="h",
        barmode="group",
        text="Score",
        custom_data=["Metric", "MetricDescription"],
        category_orders={"MetricLabel": ordered_labels, "Driver": [driver_a, driver_b]},
        color_discrete_map={driver_a: "#A48FFF", driver_b: "#FFB7D5"},
        labels={"Score": "Derived Driver Style Score [0-100]", "MetricLabel": "Metric"},
        title=(
            "Driver Style Profile Comparison"
            f"{TITLE_LINE_SPACER}<sup><span style='color:#AEB4BE;font-weight:400'>{driver_a} vs {driver_b}  -  "
            "Telemetry-derived normalized heuristic scores (0-100)</span></sup>"
            f"{TITLE_LINE_SPACER}<sup><span style='color:#AEB4BE;font-weight:400'>Higher score = stronger expression "
            "of that style characteristic, not universally faster performance</span></sup>"
        ),
        height=480,
    )

    fig = dark_layout(fig)
    fig.update_layout(
        margin=dict(l=60, r=40, t=170, b=50),
        legend=dict(
            orientation="h",
            x=0.5,
            xanchor="center",
            y=1.02,
            yanchor="bottom",
            title_text="",
        ),
    )
    fig.update_xaxes(range=[0, 100], dtick=20)
    fig.update_yaxes(categoryorder="array", categoryarray=ordered_labels)
    fig.update_traces(
        texttemplate="%{x:.1f}",
        textposition="outside",
        cliponaxis=False,
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            + "Driver: %{fullData.name}<br>"
            + "Score: %{x:.1f}/100<br>"
            + "Meaning: %{customdata[1]}"
            + "<extra></extra>"
        ),
    )

    _safe_plotly_chart(fig, key=key, context="driver_dna")


# -------------------------------------------------------
# 8) CORNER TYPE PERFORMANCE
# -------------------------------------------------------
def plot_corner_type_performance(agg_df, key="corner_type_perf"):
    """
    Bar chart showing cumulative time delta grouped by corner speed category
    (Low / Medium / High Speed).
    """
    if agg_df is None or agg_df.empty:
        st.info("No classification data available.")
        return

    color_map = {
        "Low Speed": "#FFDD94",  # yellow
        "Medium Speed": "#8FD3FE",  # blue
        "High Speed": "#FFB7D5",  # pink/red
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
