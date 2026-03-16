import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import streamlit as st

from src.logging import get_logger

logger = get_logger(__name__)

# -------------------------------------------------------
# GLOBAL DARK THEME
# -------------------------------------------------------
DARK_BG = "#141414"
DARK_PAPER = "#191919"
TEXT_COLOR = "#FFFFFF"

PASTEL_COLORS = ["#A48FFF", "#FFB7D5", "#8FD3FE", "#FFDD94", "#C9F7C5", "#FDCFE8"]
APEX_SPEED_TIE_THRESHOLD = 0.1


def _safe_plotly_chart(fig, key=None, context="plot"):
    try:
        st.plotly_chart(fig, width="stretch", key=key)
    except Exception as e:
        logger.error(
            "Failed to render plot", context=context, key=str(key), error=str(e)
        )
        st.warning("A chart could not be rendered.")


def dark_layout(fig, title=None):
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
    try:
        return f"Corner {int(corner_value)}"
    except (TypeError, ValueError):
        return f"Corner {corner_value}"


def _sort_by_corner(df):
    plot_df = df.copy()
    plot_df["_corner_sort"] = pd.to_numeric(plot_df["Corner"], errors="coerce")
    plot_df = plot_df.sort_values(["_corner_sort", "Corner"], kind="stable")
    return plot_df.drop(columns=["_corner_sort"])


def _classify_apex_advantage(delta, driver_a, driver_b):
    if delta > APEX_SPEED_TIE_THRESHOLD:
        return f"{driver_a} faster"
    if delta < -APEX_SPEED_TIE_THRESHOLD:
        return f"{driver_b} faster"
    return "Nearly equal"


def _format_delta_label(value):
    return "≈0 km/h" if abs(value) <= APEX_SPEED_TIE_THRESHOLD else f"{value:+.1f} km/h"


# -------------------------------------------------------
# 1) TIME LOSS BAR CHART
# -------------------------------------------------------
def plot_time_loss_bar(df, key="time_loss_bar"):
    if df is None or df.empty:
        logger.info("No data for time loss chart")
        st.info("No time loss data available.")
        return

    fig = px.bar(
        df,
        x="Corner",
        y="TimeLoss",
        color="TimeLoss",
        color_continuous_scale=px.colors.sequential.Purples,
        height=380,
    )

    fig = dark_layout(fig, "Time Loss per Corner")
    fig.update_traces(marker_line_width=0)
    fig.update_xaxes(title_text="Corner")
    fig.update_yaxes(title_text="Time Loss (s)")

    _safe_plotly_chart(fig, key=key, context="time_loss_bar")


# -------------------------------------------------------
# 2) SPEED DELTAS – APEX & EXIT
# -------------------------------------------------------
def plot_speed_deltas(df, driver_a, driver_b, key="speed_deltas"):
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

    plot_df["CornerLabel"] = plot_df["Corner"].apply(_format_corner_label)
    apex_winner = plot_df["Delta_ApexSpeed"].apply(
        lambda delta: _classify_apex_advantage(delta, driver_a, driver_b)
    )
    exit_winner = plot_df["Delta_ExitSpeed"].apply(
        lambda delta: _classify_apex_advantage(delta, driver_a, driver_b)
    )

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=plot_df["CornerLabel"],
            y=plot_df["Delta_ApexSpeed"],
            text=plot_df["Delta_ApexSpeed"].map(_format_delta_label),
            textposition="outside",
            cliponaxis=False,
            customdata=apex_winner,
            name=f"Δ Apex ({driver_a} - {driver_b})",
            marker_color="#A48FFF",
            hovertemplate=(
                "<b>%{x}</b><br>"
                + "Metric: Apex Speed<br>"
                + "Delta: %{y:+.1f} km/h<br>"
                + "Faster: %{customdata}<extra></extra>"
            ),
        )
    )

    fig.add_trace(
        go.Bar(
            x=plot_df["CornerLabel"],
            y=plot_df["Delta_ExitSpeed"],
            text=plot_df["Delta_ExitSpeed"].map(_format_delta_label),
            textposition="outside",
            cliponaxis=False,
            customdata=exit_winner,
            name=f"Δ Exit ({driver_a} - {driver_b})",
            marker_color="#8FD3FE",
            hovertemplate=(
                "<b>%{x}</b><br>"
                + "Metric: Exit Speed<br>"
                + "Delta: %{y:+.1f} km/h<br>"
                + "Faster: %{customdata}<extra></extra>"
            ),
        )
    )

    fig = dark_layout(fig, f"Δ Speed by Corner (Apex & Exit, {driver_a} - {driver_b})")
    fig.update_layout(barmode="group")
    fig.update_xaxes(title_text="Corner")
    fig.update_yaxes(
        title_text=f"Δ Speed ({driver_a} - {driver_b}) [km/h]",
        zeroline=True,
        zerolinecolor="#888",
    )
    fig.add_hline(y=0, line_width=1, line_dash="dash", line_color="#777")
    fig.add_annotation(
        text=(
            f"Positive: {driver_a} faster | Negative: {driver_b} faster | "
            f"0: effectively equal"
        ),
        xref="paper",
        yref="paper",
        x=0,
        y=1.08,
        showarrow=False,
        align="left",
        font=dict(size=12, color="#BBBBBB"),
    )

    _safe_plotly_chart(fig, key=key, context="speed_deltas")


# -------------------------------------------------------
# 3) SPEED PROFILE – LINE PLOT
# -------------------------------------------------------
def plot_speed_profile(telA, telB, driverA, driverB, key="speed_profile"):
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
    # Falls key nicht übergeben wurde, generieren wir einen aus dem Fahrernamen
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
# 6) APEX SPEED DELTA – SIGNED BAR CHART
# -------------------------------------------------------
def plot_apex_speed_share(
    df,
    driver_a="Driver A",
    driver_b="Driver B",
    key="apex_share",
):
    """
    Plot signed apex-speed deltas by corner.

    `Delta_ApexSpeed` follows the comparison-layer convention `driver_a - driver_b`.
    Positive values therefore mean `driver_a` carried more apex speed.
    """
    if (
        df is None
        or df.empty
        or "Delta_ApexSpeed" not in df.columns
        or "Corner" not in df.columns
    ):
        logger.info("Apex speed delta chart skipped due to missing data")
        st.info("No apex speed delta data available.")
        return

    plot_df = _sort_by_corner(df)
    plot_df = plot_df.dropna(subset=["Corner", "Delta_ApexSpeed"]).copy()

    if plot_df.empty:
        logger.info("Apex speed delta chart skipped after dropping invalid rows")
        st.info("No apex speed delta data available.")
        return

    plot_df["CornerLabel"] = plot_df["Corner"].apply(_format_corner_label)
    plot_df["ApexAdvantage"] = plot_df["Delta_ApexSpeed"].apply(
        lambda delta: _classify_apex_advantage(delta, driver_a, driver_b)
    )
    plot_df["DeltaLabel"] = plot_df["Delta_ApexSpeed"].map(_format_delta_label)
    plot_df["ApexSpeed_A_Display"] = (
        plot_df["ApexSpeed_A"].map(lambda value: f"{value:.1f} km/h")
        if "ApexSpeed_A" in plot_df.columns
        else "n/a"
    )
    plot_df["ApexSpeed_B_Display"] = (
        plot_df["ApexSpeed_B"].map(lambda value: f"{value:.1f} km/h")
        if "ApexSpeed_B" in plot_df.columns
        else "n/a"
    )

    legend_states = [
        f"{driver_a} faster",
        f"{driver_b} faster",
        "Nearly equal",
    ]
    legend_colors = {
        f"{driver_a} faster": "#A48FFF",
        f"{driver_b} faster": "#FFB7D5",
        "Nearly equal": "#8FD3FE",
    }

    fig = px.bar(
        plot_df,
        x="CornerLabel",
        y="Delta_ApexSpeed",
        color="ApexAdvantage",
        text="DeltaLabel",
        custom_data=[
            "ApexAdvantage",
            "ApexSpeed_A_Display",
            "ApexSpeed_B_Display",
        ],
        category_orders={
            "CornerLabel": plot_df["CornerLabel"].tolist(),
            "ApexAdvantage": legend_states,
        },
        color_discrete_map=legend_colors,
        labels={
            "CornerLabel": "Corner",
            "Delta_ApexSpeed": f"Δ Apex Speed ({driver_a} - {driver_b}) [km/h]",
            "ApexAdvantage": "Advantage",
        },
        height=420,
        title=f"Δ Apex Speed by Corner ({driver_a} - {driver_b})",
    )

    fig = dark_layout(fig)
    fig.update_traces(
        textposition="outside",
        cliponaxis=False,
        hovertemplate=(
            "<b>%{x}</b><br>"
            + "Delta: %{y:+.1f} km/h<br>"
            + "Faster at apex: %{customdata[0]}<br>"
            + f"{driver_a}: %{{customdata[1]}}<br>"
            + f"{driver_b}: %{{customdata[2]}}"
            + "<extra></extra>"
        ),
    )
    fig.update_xaxes(title_text="Corner")
    fig.update_yaxes(
        title_text=f"Δ Apex Speed ({driver_a} - {driver_b}) [km/h]",
        zeroline=True,
        zerolinecolor="#888",
    )
    fig.add_hline(y=0, line_width=1, line_dash="dash", line_color="#777")
    fig.add_annotation(
        text=(
            f"Positive: {driver_a} faster | Negative: {driver_b} faster | "
            f"0: effectively equal"
        ),
        xref="paper",
        yref="paper",
        x=0,
        y=1.08,
        showarrow=False,
        align="left",
        font=dict(size=12, color="#BBBBBB"),
    )

    present_states = set(plot_df["ApexAdvantage"].unique())
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

    _safe_plotly_chart(fig, key=key, context="apex_speed_share")


# -------------------------------------------------------
# 7) DRIVER DNA RADAR CHART (MIT KEY FIX)
# -------------------------------------------------------
def plot_driver_dna(dna_df, driver_a, driver_b, key="driver_dna_radar"):
    """
    Plots a Radar Chart comparing two drivers' characteristics.
    """
    if dna_df is None or dna_df.empty:
        logger.warning(
            "No data for driver DNA chart", driver_a=driver_a, driver_b=driver_b
        )
        st.info("Driver DNA chart unavailable.")
        return

    fig = go.Figure()

    # Trace für Driver A
    fig.add_trace(
        go.Scatterpolar(
            r=dna_df[driver_a],
            theta=dna_df["Metric"],
            fill="toself",
            name=driver_a,
            line=dict(color="#A48FFF", width=2),
            fillcolor="rgba(164, 143, 255, 0.3)",
        )
    )

    # Trace für Driver B
    fig.add_trace(
        go.Scatterpolar(
            r=dna_df[driver_b],
            theta=dna_df["Metric"],
            fill="toself",
            name=driver_b,
            line=dict(color="#FFB7D5", width=2),
            fillcolor="rgba(255, 183, 213, 0.3)",
        )
    )

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                gridcolor="#333",
                linecolor="#333",
                tickfont=dict(color="#888"),
            ),
            angularaxis=dict(
                gridcolor="#333", linecolor="#333", tickfont=dict(color="#FFF", size=12)
            ),
            bgcolor="#141414",
        ),
        title=dict(
            text="<b>Driver DNA Comparison</b>",
            y=0.95,
            x=0.5,
            xanchor="center",
            yanchor="top",
            font=dict(size=20, color="#FFF"),
        ),
        paper_bgcolor="#191919",
        font=dict(color="#FFF"),
        margin=dict(l=40, r=40, t=80, b=40),
        legend=dict(x=0.8, y=0.95),
    )

    # Hier übergeben wir den Key an Streamlit!
    _safe_plotly_chart(fig, key=key, context="driver_dna")


# -------------------------------------------------------
# 8) CORNER TYPE PERFORMANCE
# -------------------------------------------------------
def plot_corner_type_performance(agg_df, key="corner_type_perf"):
    """
    Zeigt den kumulierten Zeitverlust pro Kurventyp an.
    """
    if agg_df is None or agg_df.empty:
        st.info("No classification data available.")
        return

    color_map = {
        "Low Speed": "#FFDD94",  # Gelb
        "Medium Speed": "#8FD3FE",  # Blau
        "High Speed": "#FFB7D5",  # Rot/Rosa
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
        width=0.5,  # Balken nicht zu fett machen
    )

    # Layout Anpassungen
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
