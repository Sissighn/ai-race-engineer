import streamlit as st
import pandas as pd
import sys
import os

# -------------------------------
# FIX PYTHON PATH
# -------------------------------
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(project_root)

# -------------------------------
# IMPORTS
# -------------------------------
from src.data.load_data import load_session, load_telemetry
from src.data.compare import compare_drivers_corner_level
from src.insights.time_loss_engine import estimate_time_loss_per_corner
from src.insights.coaching_engine import coaching_suggestions

from app.components.plots import plot_time_loss_bar, plot_speed_deltas


# -------------------------------
# PAGE CONFIG
# -------------------------------
st.set_page_config(
    page_title="AI Race Engineer",
    layout="wide",
)

st.title("🏎️ AI Race Engineer – Telemetry & Corner Performance Dashboard")


# -----------------------------------
# SESSION SELECTION
# -----------------------------------

col1, col2, col3 = st.columns(3)

with col1:
    year = st.selectbox("Year", [2023, 2022, 2021])

with col2:
    track = st.text_input("Track (e.g. Silverstone)", "Silverstone")

with col3:
    session_type = st.selectbox("Session", ["Q", "R", "FP1", "FP2", "FP3"])


# -----------------------------------
# LOAD SESSION BUTTON
# -----------------------------------
if st.button("Load Session", type="primary"):
    try:
        session = load_session(year, track, session_type)
        st.success(f"Session loaded: {year} {track} {session_type}")

        # save in session state
        st.session_state["session"] = session
        st.session_state["drivers"] = sorted(list(session.laps["Driver"].unique()))

    except Exception as e:
        st.error(f"Error loading session: {e}")


# -----------------------------------
# DRIVER COMPARISON SECTION
# -----------------------------------

if "drivers" in st.session_state:

    st.subheader("👥 Compare Two Drivers")

    colA, colB = st.columns(2)

    with colA:
        driverA = st.selectbox(
            "Driver A",
            st.session_state["drivers"],
            key="driverA"
        )

    with colB:
        driverB = st.selectbox(
            "Driver B",
            st.session_state["drivers"],
            key="driverB"
        )

    compare_button = st.button("Compare Drivers 🚀")


    # -----------------------------------
    # RUN COMPARISON
    # -----------------------------------
    if compare_button:

        session = st.session_state["session"]
        driver_a = st.session_state["driverA"]
        driver_b = st.session_state["driverB"]

        st.info("Computing telemetry & metrics…")

        # corner-level metrics
        comp = compare_drivers_corner_level(session, driver_a, driver_b)

        # time loss engine
        tl = estimate_time_loss_per_corner(comp, driver_a, driver_b)

        st.success(f"Comparison complete: {driver_a} vs {driver_b}")

        # -------------------------------
        # METRICS TABLE
        # -------------------------------
        st.subheader("📊 Corner-by-Corner Performance")
        st.dataframe(tl)

        # -------------------------------
        # PLOTS
        # -------------------------------
        st.subheader("⏱️ Time Loss per Corner")
        plot_time_loss_bar(tl)

        st.subheader("📉 Speed Delta Overview")
        plot_speed_deltas(tl, driver_a, driver_b)

        # -------------------------------
        # COACHING
        # -------------------------------
        st.subheader("🧠 AI Coaching Suggestions")

        suggestions = coaching_suggestions(tl, driver_a, driver_b)

        for s in suggestions:
            st.markdown(f"- {s}")
