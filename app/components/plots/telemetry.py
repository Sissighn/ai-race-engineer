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
