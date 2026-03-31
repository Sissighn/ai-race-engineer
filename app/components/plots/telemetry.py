"""
Telemetry Line Charts (Sections 3, 4 & 5).

Exposes three public functions:
    plot_speed_profile  – overlaid speed traces for both drivers vs lap distance
    plot_brake_throttle – overlaid brake and throttle inputs vs lap distance
    plot_gear_usage     – donut chart of gear distribution across a lap
"""

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.logging import get_logger

from ._theme import PASTEL_COLORS, _safe_plotly_chart, dark_layout

logger = get_logger(__name__)


def plot_speed_profile(tel_a, tel_b, driver_a, driver_b, key="speed_profile"):
    """Overlay both drivers' speed traces on a single Distance vs Speed line chart.

    Args:
        tel_a:    Telemetry DataFrame for driver A (must contain Distance, Speed).
        tel_b:    Telemetry DataFrame for driver B (must contain Distance, Speed).
        driver_a: Display name for driver A.
        driver_b: Display name for driver B.
        key:      Streamlit widget key.
    """
    if tel_a is None or tel_b is None or tel_a.empty or tel_b.empty:
        logger.warning(
            "Missing telemetry for speed profile", driver_a=driver_a, driver_b=driver_b
        )
        st.info("Speed profile unavailable.")
        return

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=tel_a["Distance"],
            y=tel_a["Speed"],
            mode="lines",
            name=f"{driver_a} Speed",
            line=dict(color="#A48FFF", width=2),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=tel_b["Distance"],
            y=tel_b["Speed"],
            mode="lines",
            name=f"{driver_b} Speed",
            line=dict(color="#FFB7D5", width=2),
        )
    )

    fig = dark_layout(fig, f"Speed Profile – {driver_a} vs {driver_b}")
    fig.update_xaxes(title_text="Distance (m)")
    fig.update_yaxes(title_text="Speed (km/h)")

    _safe_plotly_chart(fig, key=key, context="speed_profile")


def plot_brake_throttle(tel_a, tel_b, driver_a, driver_b, key="brake_throttle"):
    """Overlay brake and throttle traces for both drivers against lap distance.

    Four traces are drawn in total: brake and throttle for each driver, each
    with a distinct colour so inputs can be compared at every point on track.

    Args:
        tel_a:    Telemetry DataFrame for driver A (must contain Distance, Brake, Throttle).
        tel_b:    Telemetry DataFrame for driver B (must contain Distance, Brake, Throttle).
        driver_a: Display name for driver A.
        driver_b: Display name for driver B.
        key:      Streamlit widget key.
    """
    if tel_a is None or tel_b is None or tel_a.empty or tel_b.empty:
        logger.warning(
            "Missing telemetry for brake/throttle plot",
            driver_a=driver_a,
            driver_b=driver_b,
        )
        st.info("Brake/Throttle plot unavailable.")
        return

    fig = go.Figure()

    # --- Driver A ---
    fig.add_trace(
        go.Scatter(
            x=tel_a["Distance"],
            y=tel_a["Brake"],
            name=f"{driver_a} Brake",
            mode="lines",
            line=dict(color="#A48FFF", width=2),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=tel_a["Distance"],
            y=tel_a["Throttle"],
            name=f"{driver_a} Throttle",
            mode="lines",
            line=dict(color="#8FD3FE", width=2),
        )
    )

    # --- Driver B ---
    fig.add_trace(
        go.Scatter(
            x=tel_b["Distance"],
            y=tel_b["Brake"],
            name=f"{driver_b} Brake",
            mode="lines",
            line=dict(color="#FFB7D5", width=2),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=tel_b["Distance"],
            y=tel_b["Throttle"],
            name=f"{driver_b} Throttle",
            mode="lines",
            line=dict(color="#FFDD94", width=2),
        )
    )

    fig = dark_layout(fig, f"Brake & Throttle – {driver_a} vs {driver_b}")
    fig.update_xaxes(title_text="Distance (m)")
    fig.update_yaxes(title_text="Input (%)")

    _safe_plotly_chart(fig, key=key, context="brake_throttle")


def plot_gear_usage(tel, driver, key=None):
    """Render a donut chart showing the distribution of gear usage across a lap.

    Args:
        tel:    Telemetry DataFrame containing the nGear column.
        driver: Driver display name (used in the chart title and default key).
        key:    Streamlit widget key. Derived from the driver name if omitted.
    """
    # Fall back to a driver-derived key if none is provided by the caller.
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
