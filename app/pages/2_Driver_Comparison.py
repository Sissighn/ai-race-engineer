import streamlit as st
import pandas as pd
import numpy as np
import sys
import os

# -------------------------------------------------------
# FIX PYTHON PATH
# -------------------------------------------------------
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# -------------------------------------------------------
# IMPORTS
# -------------------------------------------------------
from app.components.navbar import navbar
from app.components.styling import apply_custom_theme
from app.components.glow_card import GlowCard  # <--- NEU: GlowCard importiert
from app.components.plots import (
    plot_time_loss_bar,
    plot_speed_deltas,
    plot_speed_profile,
    plot_brake_throttle,
    plot_gear_usage,
    plot_apex_speed_share,
)
from app.components.track_map import plot_track_map
from app.components.advanced_plots.plot_delta_lap import (
    compute_delta_lap,
    plot_delta_lap,
)

from src.data.load_data import load_session, load_telemetry
from src.data.compare import compare_drivers_corner_level, sync_telemetry
from src.insights.time_loss_engine import estimate_time_loss_per_corner
from src.insights.coaching_engine import coaching_suggestions


# -------------------------------------------------------
# UTILS — RESET CACHE
# -------------------------------------------------------
def reset_cache():
    keys = ["session", "drivers_full", "driver_map", "compare_result"]
    for k in keys:
        if k in st.session_state:
            st.session_state[k] = None


# -------------------------------------------------------
# PAGE CONFIG
# -------------------------------------------------------
st.set_page_config(
    page_title="Driver Comparison – AI Race Engineer",
    layout="wide",
)

apply_custom_theme()

navbar()

# -------------------------------------------------------
# PAGE HEADER
# -------------------------------------------------------
st.markdown("<h1>Driver Comparison</h1>", unsafe_allow_html=True)

# -------------------------------------------------------
# SESSION SELECTION
# -------------------------------------------------------
st.markdown("<h2 class='section-title'>Session Selection</h2>", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)

with col1:
    year = st.selectbox("Year", [2025, 2024, 2023, 2022, 2021])

TRACKS = [
    "Bahrain",
    "Jeddah",
    "Melbourne",
    "Imola",
    "Miami",
    "Monaco",
    "Barcelona",
    "Montreal",
    "Spielberg",
    "Silverstone",
    "Hungaroring",
    "Spa",
    "Zandvoort",
    "Monza",
    "Singapore",
    "Suzuka",
    "Lusail",
    "Austin",
    "Mexico City",
    "Sao Paulo",
    "Las Vegas",
    "Abu Dhabi",
]

with col2:
    # Fallback, falls Silverstone nicht in der Liste wäre
    idx = TRACKS.index("Silverstone") if "Silverstone" in TRACKS else 0
    track = st.selectbox("Track", TRACKS, index=idx)

with col3:
    session_type = st.selectbox("Session", ["Q", "R", "FP1", "FP2", "FP3"])

# -------------------------------------------------------
# AUTO-RESET LOGIC
# -------------------------------------------------------
sel_tuple = (year, track, session_type)

if "last_selection" not in st.session_state:
    st.session_state["last_selection"] = sel_tuple

if st.session_state["last_selection"] != sel_tuple:
    reset_cache()
    st.session_state["last_selection"] = sel_tuple
    st.rerun()

# -------------------------------------------------------
# LOAD SESSION BUTTON
# -------------------------------------------------------
if st.button("Load session"):
    try:
        session = load_session(year, track, session_type)

        driver_map = {}
        # Sicherheitscheck, falls 'laps' noch nicht geladen ist
        unique_drivers = (
            sorted(session.laps["Driver"].unique()) if hasattr(session, "laps") else []
        )

        for code in unique_drivers:
            info = session.get_driver(code)
            fn = info.get("FirstName", info.get("given_name", ""))
            ln = info.get("LastName", info.get("family_name", ""))
            full = f"{fn} {ln} ({code})"
            driver_map[full] = code

        st.session_state["session"] = session
        st.session_state["drivers_full"] = list(driver_map.keys())
        st.session_state["driver_map"] = driver_map

        st.success("Session loaded.")
        st.rerun()

    except Exception as e:
        st.error(f"Error loading session: {e}")

# -------------------------------------------------------
# DRIVER COMPARISON LOGIC
# -------------------------------------------------------
if st.session_state.get("drivers_full"):

    st.markdown(
        "<h2 class='section-title'>Driver Selection</h2>", unsafe_allow_html=True
    )

    colA, colB = st.columns(2)
    with colA:
        driverA_full = st.selectbox(
            "Driver A", st.session_state["drivers_full"], key="drvA"
        )
    with colB:
        driverB_full = st.selectbox(
            "Driver B", st.session_state["drivers_full"], key="drvB"
        )

    if st.button("Compare drivers"):
        try:
            driverA = st.session_state["driver_map"][driverA_full]
            driverB = st.session_state["driver_map"][driverB_full]
            session = st.session_state["session"]

            with st.spinner("Analyzing Telemetry..."):
                telA = load_telemetry(session, driverA)
                telB = load_telemetry(session, driverB)
                comp = compare_drivers_corner_level(session, driverA, driverB)
                tl = estimate_time_loss_per_corner(comp, driverA, driverB)

            st.session_state["compare_result"] = {
                "session": session,
                "driverA": driverA,
                "driverB": driverB,
                "telA": telA,
                "telB": telB,
                "comp": comp,
                "tl": tl,
            }
            st.rerun()

        except Exception as e:
            st.error(f"Compare failed: {e}")

# -------------------------------------------------------
# RENDER RESULTS
# -------------------------------------------------------
if st.session_state.get("compare_result"):
    data = st.session_state["compare_result"]
    tl = data["tl"]
    telA = data["telA"]
    telB = data["telB"]
    driverA = data["driverA"]
    driverB = data["driverB"]
    session = data["session"]

    # Tabs
    tab_overview, tab_inputs, tab_corners, tab_coaching = st.tabs(
        ["Overview", "Driver Inputs", "Corners", "Coaching"]
    )

    # --- Overview ---
    with tab_overview:
        st.markdown("<h2 class='section-title'>Summary</h2>", unsafe_allow_html=True)
        total_delta = tl["TimeLoss"].sum()

        # FIX: Hier jetzt GlowCard statt manuellem HTML nutzen
        c1, c2, c3 = st.columns(3)
        with c1:
            GlowCard.render("Total Time Delta", f"{total_delta:.2f}s")
        with c2:
            GlowCard.render("Best Corners", "See charts")
        with c3:
            GlowCard.render("Worst Corners", "See charts")

        st.markdown("<h3>Time Loss per Corner</h3>", unsafe_allow_html=True)
        plot_time_loss_bar(tl)

        st.markdown("<h3>Speed Delta (Apex & Exit)</h3>", unsafe_allow_html=True)
        plot_speed_deltas(tl, driverA, driverB)

        st.markdown("<h3>Apex Speed Share</h3>", unsafe_allow_html=True)
        plot_apex_speed_share(tl)

    # --- Inputs ---
    with tab_inputs:
        st.markdown(
            "<h2 class='section-title'>Driver Inputs</h2>", unsafe_allow_html=True
        )
        ctm1, ctm2 = st.columns(2)
        with ctm1:
            plot_track_map(session, driverA, track)
        with ctm2:
            plot_track_map(session, driverB, track)

        plot_speed_profile(telA, telB, driverA, driverB)
        plot_brake_throttle(telA, telB, driverA, driverB)
        plot_gear_usage(telA, driverA)
        plot_gear_usage(telB, driverB)

    # --- Corners ---
    with tab_corners:
        st.markdown(
            "<h2 class='section-title'>Corner-by-Corner Data</h2>",
            unsafe_allow_html=True,
        )

        st.dataframe(tl, width="stretch")

    # --- Coaching ---
    with tab_coaching:
        st.markdown(
            "<h2 class='section-title'>AI Coaching</h2>", unsafe_allow_html=True
        )
        suggestions = coaching_suggestions(tl, driverA, driverB)
        if not suggestions:
            st.info("No significant weaknesses found.")
        else:
            for s in suggestions:
                st.markdown(f"- {s}")

    # --- Delta Lap ---
    st.markdown("<h3>Delta Lap Overlay</h3>", unsafe_allow_html=True)
    try:
        tel_sync = sync_telemetry(telA, telB)
        dfA = tel_sync.rename(columns={"Speed_1": "Speed_A", "Time_1": "Time_A"})[
            ["Distance", "Speed_A", "Time_A"]
        ]
        dfB = tel_sync.rename(columns={"Speed_2": "Speed_B", "Time_2": "Time_B"})[
            ["Distance", "Speed_B", "Time_B"]
        ]
        delta_df = compute_delta_lap(dfA, dfB)
        plot_delta_lap(delta_df, driverA, driverB)
    except Exception as e:
        st.warning(f"Could not compute Delta Lap: {e}")
