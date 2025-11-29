import streamlit as st
import pandas as pd
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
from src.data.load_data import load_session, load_telemetry
from src.data.compare import compare_drivers_corner_level
from src.insights.time_loss_engine import estimate_time_loss_per_corner
from src.insights.coaching_engine import coaching_suggestions

from app.components.plots import (
    plot_time_loss_bar,
    plot_speed_deltas,
    plot_speed_profile,
    plot_brake_throttle,
    plot_gear_usage,
    plot_apex_speed_share
)

# -------------------------------------------------------
# PAGE CONFIG
# -------------------------------------------------------
st.set_page_config(
    page_title="Driver Comparison – AI Race Engineer",
    layout="wide",
)
st.markdown("""
<style>
[data-testid="stSidebar"] { display: none; }
[data-testid="stSidebarNav"] { display: none; }
[data-testid="stSidebarUserContent"] { display: none; }
[data-testid="collapsedControl"] { display: none; }
</style>
""", unsafe_allow_html=True)

navbar()
# -------------------------------------------------------
# GLOBAL PASTEL CSS
# -------------------------------------------------------
st.markdown("""
<style>
html, body, [class*="block-container"] {
    font-family: 'Inter', sans-serif;
}

@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Poppins:wght@600;700;800&display=swap');

h1, h2, h3 {
    font-family: 'Poppins', sans-serif !important;
    font-weight: 700 !important;
}

.section-title {
    font-size: 1.5rem;
    font-weight: 700;
    color: #403075;
    margin-top: 12px;
}

.card {
    background: #FFFFFF;
    border-radius: 18px;
    padding: 20px 24px;
    border: 1px solid #EDE7FF;
    margin-bottom: 14px;
}

.card-title {
    font-size: 0.9rem;
    font-weight: 600;
    color: #6A5ACD;
}

.card-value {
    font-size: 1.7rem;
    font-weight: 700;
    color: #4636C5;
}
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------
# HEADER
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

load_session_button = st.button("Load session")


# -------------------------------------------------------
# LOAD SESSION
# -------------------------------------------------------
if load_session_button:
    try:
        session = load_session(year, track, session_type)

        driver_map = {}
        for code in sorted(session.laps["Driver"].unique()):

            info = session.get_driver(code)

            first = info.get("FirstName", info.get("given_name", ""))
            last = info.get("LastName", info.get("family_name", ""))

            full_name = f"{first} {last} ({code})".strip()
            driver_map[full_name] = code

        st.session_state["session"] = session
        st.session_state["drivers_full"] = list(driver_map.keys())
        st.session_state["driver_map"] = driver_map

        st.success(f"Loaded session: {year} {track} {session_type}")

    except Exception as e:
        st.error(f"Error loading session: {e}")


# -------------------------------------------------------
# DRIVER COMPARISON
# -------------------------------------------------------
if "drivers_full" in st.session_state:

    st.markdown("<h2 class='section-title'>Driver Selection</h2>", unsafe_allow_html=True)

    colA, colB = st.columns(2)

    with colA:
        driverA_full = st.selectbox(
            "Driver A", st.session_state["drivers_full"], key="driverA"
        )

    with colB:
        driverB_full = st.selectbox(
            "Driver B", st.session_state["drivers_full"], key="driverB"
        )

    driverA = st.session_state["driver_map"][driverA_full]
    driverB = st.session_state["driver_map"][driverB_full]

    compare_button = st.button("Compare drivers")

    if compare_button:
        session = st.session_state["session"]

        # Load telemetry
        telA = load_telemetry(session, driverA)
        telB = load_telemetry(session, driverB)

        # Corner-level comparison
        comp = compare_drivers_corner_level(session, driverA, driverB)

        # Time loss model
        tl = estimate_time_loss_per_corner(comp, driverA, driverB)

        st.success(f"Comparison complete: {driverA} vs {driverB}")


        # -------------------------------------------------------
        # TABS
        # -------------------------------------------------------
        tab_overview, tab_inputs, tab_corners, tab_coaching = st.tabs(
            ["Overview", "Driver Inputs", "Corners", "Coaching"]
        )

        # -------------------------------------------------------
        # OVERVIEW TAB
        # -------------------------------------------------------
        with tab_overview:

            st.markdown("<h2 class='section-title'>Summary</h2>", unsafe_allow_html=True)

            time_delta = tl["TimeLoss"].sum()

            # KPIs
            c1, c2, c3 = st.columns(3)

            with c1:
                st.markdown(
                    f"""
                    <div class="card">
                        <div class="card-title">Total Time Delta</div>
                        <div class="card-value">{time_delta:.2f} s</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            with c2:
                st.markdown(
                    f"""
                    <div class="card">
                        <div class="card-title">Best Corners (Apex)</div>
                        <div class="card-value">Top 3 shown below</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            with c3:
                st.markdown(
                    f"""
                    <div class="card">
                        <div class="card-title">Worst Corners (Loss)</div>
                        <div class="card-value">Top 3 shown below</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            # DIAGRAMS
            st.markdown("<h3>Time Loss per Corner</h3>", unsafe_allow_html=True)
            plot_time_loss_bar(tl)

            st.markdown("<h3>Speed Deltas (Apex & Exit)</h3>", unsafe_allow_html=True)
            plot_speed_deltas(tl, driverA, driverB)

            st.markdown("<h3>Apex Speed Share</h3>", unsafe_allow_html=True)
            plot_apex_speed_share(tl)

        # -------------------------------------------------------
        # INPUT TAB
        # -------------------------------------------------------
        with tab_inputs:

            st.markdown("<h2 class='section-title'>Driver Inputs</h2>", unsafe_allow_html=True)

            st.markdown("<h3>Speed Profile</h3>", unsafe_allow_html=True)
            plot_speed_profile(telA, telB, driverA, driverB)

            st.markdown("<h3>Brake & Throttle</h3>", unsafe_allow_html=True)
            plot_brake_throttle(telA, telB, driverA, driverB)

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
