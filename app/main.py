import streamlit as st
import pandas as pd
import sys
import os

# -------------------------------
# FIX PYTHON PATH
# -------------------------------
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

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

# -------------------------------
# SIMPLE CSS FOR MODERN LOOK
# -------------------------------
st.markdown(
    """
    <style>
    .kpi-card {
        padding: 16px 18px;
        border-radius: 16px;
        background: #111827;
        color: #F9FAFB;
        border: 1px solid #1F2937;
        box-shadow: 0 10px 30px rgba(15,23,42,0.45);
    }
    .kpi-title {
        font-size: 0.85rem;
        color: #9CA3AF;
        margin-bottom: 4px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .kpi-value {
        font-size: 1.6rem;
        font-weight: 700;
        margin-bottom: 2px;
    }
    .kpi-sub {
        font-size: 0.9rem;
        color: #6B7280;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🏎️ AI Race Engineer – Telemetry & Corner Performance Dashboard")


# -----------------------------------
# SESSION SELECTION
# -----------------------------------
st.markdown("### Session Selection")

col1, col2, col3 = st.columns(3)

with col1:
    year = st.selectbox("Year", [2023, 2022, 2021])

with col2:
    track = st.text_input("Track (e.g. Silverstone)", "Silverstone")

with col3:
    session_type = st.selectbox("Session", ["Q", "R", "FP1", "FP2", "FP3"])

load_session_button = st.button("Load Session", type="primary")


# -----------------------------------
# LOAD SESSION
# -----------------------------------
if load_session_button:
    try:
        session = load_session(year, track, session_type)

        st.session_state["session"] = session
        st.session_state["drivers"] = sorted(list(session.laps["Driver"].unique()))

        st.success(f"Loaded: {year} {track} {session_type} — {len(st.session_state['drivers'])} drivers found.")

    except Exception as e:
        st.error(f"Error loading session: {e}")


# -----------------------------------
# DRIVER COMPARISON SECTION
# -----------------------------------
if "drivers" in st.session_state:

    st.markdown("### Driver Comparison")

    colA, colB = st.columns(2)

    with colA:
        driverA = st.selectbox(
            "Driver A",
            st.session_state["drivers"],
            key="driverA",
        )

    with colB:
        driverB = st.selectbox(
            "Driver B",
            st.session_state["drivers"],
            key="driverB",
        )

    compare_button = st.button("Compare Drivers 🚀")

    if compare_button:
        session = st.session_state["session"]
        driver_a = st.session_state["driverA"]
        driver_b = st.session_state["driverB"]

        st.info(f"Computing corner metrics for {driver_a} vs {driver_b} …")

        # Corner-level comparison
        comp = compare_drivers_corner_level(session, driver_a, driver_b)

        # Time loss model
        tl = estimate_time_loss_per_corner(comp, driver_a, driver_b)

        # Basic aggregates for KPIs
        total_time_diff = tl["TimeLoss"].sum()
        worst_losses = tl.sort_values("TimeLossSeconds_A_loses", ascending=False).head(3)
        worst_corner_text = ", ".join(
            f"T{int(row['Corner'])}: {row['TimeLossSeconds_A_loses']:.2f}s"
            for _, row in worst_losses.iterrows()
            if row["TimeLossSeconds_A_loses"] > 0
        )

        best_gains = tl.sort_values("TimeGainSeconds_A_gains", ascending=False).head(3)
        best_corner_text = ", ".join(
            f"T{int(row['Corner'])}: {row['TimeGainSeconds_A_gains']:.2f}s"
            for _, row in best_gains.iterrows()
            if row["TimeGainSeconds_A_gains"] > 0
        )

        st.success(f"Comparison ready: {driver_a} vs {driver_b}")

        # -----------------------------------
        # TABS FOR MODERN LAYOUT
        # -----------------------------------
        tab_overview, tab_corners, tab_coaching = st.tabs(
            ["📊 Overview", "📋 Corner Details", "🧠 Coaching"]
        )

        # ---------- OVERVIEW TAB ----------
        with tab_overview:
            k1, k2, k3 = st.columns(3)

            with k1:
                html = f"""
                <div class="kpi-card">
                    <div class="kpi-title">Total Time Delta</div>
                    <div class="kpi-value">{total_time_diff:.2f} s</div>
                    <div class="kpi-sub">+ = {driver_a} faster</div>
                </div>
                """
                st.markdown(html, unsafe_allow_html=True)

            with k2:
                html = f"""
                <div class="kpi-card">
                    <div class="kpi-title">Worst Corners for {driver_a if total_time_diff < 0 else driver_b}</div>
                    <div class="kpi-value">{worst_corner_text or "–"}</div>
                    <div class="kpi-sub">Time lost in key corners</div>
                </div>
                """
                st.markdown(html, unsafe_allow_html=True)

            with k3:
                html = f"""
                <div class="kpi-card">
                    <div class="kpi-title">Best Corners for {driver_a if total_time_diff > 0 else driver_b}</div>
                    <div class="kpi-value">{best_corner_text or "–"}</div>
                    <div class="kpi-sub">Strongest segments</div>
                </div>
                """
                st.markdown(html, unsafe_allow_html=True)

            # Charts in two columns
            c1, c2 = st.columns(2)

            with c1:
                st.markdown("#### Time Loss per Corner")
                plot_time_loss_bar(tl)

            with c2:
                st.markdown("#### Speed Deltas (Apex / Exit)")
                plot_speed_deltas(tl, driver_a, driver_b)

        # ---------- CORNERS TAB ----------
        with tab_corners:
            st.markdown("#### Corner-by-Corner Metrics")
            st.dataframe(tl, use_container_width=True)

        # ---------- COACHING TAB ----------
        with tab_coaching:
            st.markdown("#### AI Coaching Suggestions")
            suggestions = coaching_suggestions(tl, driver_a, driver_b)
            if not suggestions:
                st.info("No significant weaknesses detected between these two drivers.")
            else:
                for s in suggestions:
                    st.markdown(f"- {s}")
