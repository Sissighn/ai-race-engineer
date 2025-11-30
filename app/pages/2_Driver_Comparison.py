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
from app.components.plots import (
    plot_time_loss_bar,
    plot_speed_deltas,
    plot_speed_profile,
    plot_brake_throttle,
    plot_gear_usage,
    plot_apex_speed_share
)
from app.components.track_map import plot_track_map

from src.data.load_data import (
    load_session,
    load_telemetry,
    load_telemetry_with_position
)
from src.data.compare import compare_drivers_corner_level
from src.insights.time_loss_engine import estimate_time_loss_per_corner
from src.insights.coaching_engine import coaching_suggestions


# -------------------------------------------------------
# UTILS — RESET CACHE
# -------------------------------------------------------
def reset_cache():
    for k in ["session", "drivers_full", "driver_map", "compare_result"]:
        st.session_state[k] = None


# -------------------------------------------------------
# PAGE CONFIG
# -------------------------------------------------------
st.set_page_config(
    page_title="Driver Comparison – AI Race Engineer",
    layout="wide",
)

# Hide Streamlit sidebar
st.markdown("""
<style>
[data-testid="stSidebar"] { display:none; }
header {visibility:hidden;}
</style>
""", unsafe_allow_html=True)

navbar()


# -------------------------------------------------------
# DARK THEME GLOBAL CSS
# -------------------------------------------------------
st.markdown("""
<style>

@import url('https://fonts.googleapis.com/css2?family=Tektur:wght@400..900&family=Playfair:ital,opsz,wght@0,5..1200,300..900;1,5..1200,300..900&display=swap');

html, body, [class*="block-container"] {
    background-color: #191919 !important;
    color: #FFFFFF !important;
    font-family: 'Playfair', serif;
    font-optical-sizing: auto;
}

h1, h2, h3 {
    font-family: 'Tektur', sans-serif !important;
    font-weight: 700 !important;
    color: #FFFFFF !important;
    font-optical-sizing: auto !important;
    font-variation-settings: "wdth" 100 !important;
}

/* Section Titles */
.section-title {
    font-size: 1.6rem;
    font-weight: 700;
    font-family: 'Tektur', sans-serif;
    font-optical-sizing: auto;
    font-variation-settings: "wdth" 100;
    margin-top: 1.2rem;
    color: #FFFFFF;
}

/* Cards */
.card {
    background: #141414;
    border-radius: 14px;
    padding: 16px 20px;
    border: 1px solid #1F1F1F;
    margin-bottom: 14px;
    box-shadow: 0px 0px 10px rgba(211, 0, 0, 0.15);
}

.card-title {
    font-size: 0.8rem;
    color: #8e1f1f;
    font-weight: 600;
    margin-bottom: 5px;
}

.card-value {
    font-size: 1.3rem;
    font-weight: 700;
    color: #FFFFFF;
}

/* Selectbox styling */
.stSelectbox > div > div {
    background-color: #141414 !important;
    border: 1px solid #1F1F1F !important;
    color: #FFFFFF !important;
}

/* Button styling */
.stButton > button {
    background-color: #7d0e0e !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 10px 24px !important;
    font-weight: 600 !important;
    transition: all 0.3s ease !important;
}

.stButton > button:hover {
    background-color: #8e1f1f !important;
    box-shadow: 0px 0px 15px rgba(211, 0, 0, 0.4) !important;
}

/* Tabs styling */
.stTabs [data-baseweb="tab-list"] {
    background-color: #141414 !important;
    border-bottom: 2px solid #1F1F1F !important;
}

.stTabs [data-baseweb="tab"] {
    color: #888888 !important;
    background-color: transparent !important;
    border: none !important;
    font-weight: 600 !important;
}

.stTabs [aria-selected="true"] {
    color: #8e1f1f !important;
    border-bottom: 3px solid #8e1f1f !important;
}

/* Dataframe styling */
.stDataFrame {
    background-color: #141414 !important;
}

.stDataFrame [data-testid="stDataFrameResizable"] {
    background-color: #141414 !important;
    border: 1px solid #1F1F1F !important;
}

/* Success/Error messages */
.stSuccess {
    background-color: #1a2f1a !important;
    color: #4ade80 !important;
    border: 1px solid #22c55e !important;
}

.stError {
    background-color: #2f1a1a !important;
    color: #f87171 !important;
    border: 1px solid #ef4444 !important;
}

.stInfo {
    background-color: #1a1f2f !important;
    color: #60a5fa !important;
    border: 1px solid #3b82f6 !important;
}

/* Input fields */
input, textarea, select {
    background-color: #141414 !important;
    color: #FFFFFF !important;
    border: 1px solid #1F1F1F !important;
}

</style>
""", unsafe_allow_html=True)


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
    "Bahrain", "Jeddah", "Melbourne", "Imola", "Miami", "Monaco",
    "Barcelona", "Montreal", "Spielberg", "Silverstone", "Hungaroring",
    "Spa", "Zandvoort", "Monza", "Singapore", "Suzuka", "Lusail",
    "Austin", "Mexico City", "Sao Paulo", "Las Vegas", "Abu Dhabi"
]

with col2:
    track = st.selectbox("Track", TRACKS, index=TRACKS.index("Silverstone"))

with col3:
    session_type = st.selectbox("Session", ["Q", "R", "FP1", "FP2", "FP3"])


# -------------------------------------------------------
# AUTO-RESET WHEN USER CHANGES INPUT
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
load_btn = st.button("Load session")

if load_btn:
    try:
        session = load_session(year, track, session_type)

        driver_map = {}
        for code in sorted(session.laps["Driver"].unique()):
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
# DRIVER COMPARISON
# -------------------------------------------------------
if st.session_state.get("drivers_full"):

    st.markdown("<h2 class='section-title'>Driver Selection</h2>", unsafe_allow_html=True)

    colA, colB = st.columns(2)
    with colA:
        driverA_full = st.selectbox("Driver A", st.session_state["drivers_full"], key="drvA")
    with colB:
        driverB_full = st.selectbox("Driver B", st.session_state["drivers_full"], key="drvB")

    driverA = st.session_state["driver_map"][driverA_full]
    driverB = st.session_state["driver_map"][driverB_full]

    compare_btn = st.button("Compare drivers")

    if compare_btn:
        try:
            session = st.session_state["session"]

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
# RENDER RESULTS IF READY
# -------------------------------------------------------
if st.session_state.get("compare_result"):

    data = st.session_state["compare_result"]

    session = data["session"]
    driverA = data["driverA"]
    driverB = data["driverB"]
    telA = data["telA"]
    telB = data["telB"]
    comp = data["comp"]
    tl = data["tl"]

    tab_overview, tab_inputs, tab_corners, tab_coaching = st.tabs(
        ["Overview", "Driver Inputs", "Corners", "Coaching"]
    )


    # -------------------------------------------------------
    # OVERVIEW TAB
    # -------------------------------------------------------
    with tab_overview:

        st.markdown("<h2 class='section-title'>Summary</h2>", unsafe_allow_html=True)

        total_delta = tl["TimeLoss"].sum()

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"""
            <div class="card">
                <div class="card-title">Total Time Delta</div>
                <div class="card-value">{total_delta:.2f}s</div>
            </div>
            """, unsafe_allow_html=True)

        with c2:
            st.markdown(f"""
            <div class="card">
                <div class="card-title">Best Corners</div>
                <div class="card-value">See charts</div>
            </div>
            """, unsafe_allow_html=True)

        with c3:
            st.markdown(f"""
            <div class="card">
                <div class="card-title">Worst Corners</div>
                <div class="card-value">See charts</div>
            </div>
            """, unsafe_allow_html=True)

        # charts
        st.markdown("<h3>Time Loss per Corner</h3>", unsafe_allow_html=True)
        plot_time_loss_bar(tl)

        st.markdown("<h3>Speed Delta (Apex & Exit)</h3>", unsafe_allow_html=True)
        plot_speed_deltas(tl, driverA, driverB)

        st.markdown("<h3>Apex Speed Share</h3>", unsafe_allow_html=True)
        plot_apex_speed_share(tl)


    # -------------------------------------------------------
    # DRIVER INPUTS TAB
    # -------------------------------------------------------
    with tab_inputs:
        st.markdown("<h2 class='section-title'>Driver Inputs</h2>", unsafe_allow_html=True)

        # TRACK MAP
        ctm1, ctm2 = st.columns(2)
        with ctm1:
            plot_track_map(session, driverA, track)
        with ctm2:
            plot_track_map(session, driverB, track)

        # SPEED PROFILE
        st.markdown("<h3>Speed Profile</h3>", unsafe_allow_html=True)
        plot_speed_profile(telA, telB, driverA, driverB)

        # BRAKE / THROTTLE
        st.markdown("<h3>Brake & Throttle</h3>", unsafe_allow_html=True)
        plot_brake_throttle(telA, telB, driverA, driverB)

        # GEAR USAGE
        st.markdown("<h3>Gear Usage</h3>", unsafe_allow_html=True)
        plot_gear_usage(telA, driverA)
        plot_gear_usage(telB, driverB)


    # -------------------------------------------------------
    # CORNERS TAB
    # -------------------------------------------------------
    with tab_corners:
        st.markdown("<h2 class='section-title'>Corner-by-Corner Data</h2>", unsafe_allow_html=True)
        st.dataframe(tl, use_container_width=True)


    # -------------------------------------------------------
    # COACHING TAB
    # -------------------------------------------------------
    with tab_coaching:
        st.markdown("<h2 class='section-title'>AI Coaching</h2>", unsafe_allow_html=True)

        suggestions = coaching_suggestions(tl, driverA, driverB)

        if not suggestions:
            st.info("No significant weaknesses found.")
        else:
            for s in suggestions:
                st.markdown(f"- {s}")