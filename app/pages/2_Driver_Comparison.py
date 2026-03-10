import sys
import os
from datetime import datetime

# Ensure project root is on sys.path so 'src' and 'app' are importable
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import streamlit as st
import pandas as pd
import numpy as np

from src.logging import get_logger

# -------------------------------------------------------
# IMPORTS
# -------------------------------------------------------
from app.utils.ui import load_css
from app.utils.error_ui import show_domain_error, DOMAIN_EXCEPTIONS
from app.components.navbar import navbar
from app.components.glow_card import GlowCard
from app.components.plots import (
    plot_time_loss_bar,
    plot_speed_deltas,
    plot_speed_profile,
    plot_brake_throttle,
    plot_gear_usage,
    plot_apex_speed_share,
    plot_driver_dna,
    plot_corner_type_performance,
)
from app.components.track_map import plot_track_map
from app.components.advanced_plots.plot_delta_lap import (
    compute_delta_lap,
    plot_delta_lap,
)
from src.data.load_data import load_session, load_telemetry, get_tracks_for_year
from src.data.compare import compare_drivers_corner_level, sync_telemetry
from src.insights.time_loss_engine import estimate_time_loss_per_corner
from src.insights.coaching_engine import coaching_suggestions
from src.insights.driver_dna import get_driver_dna_comparison_df
from src.insights.corner_utils import (
    add_corner_classification,
    aggregate_time_loss_by_type,
    get_corner_type_advice,
)
from src.insights.report_engine import generate_race_engineer_report
from app.components.report_view import render_race_engineer_report

logger = get_logger(__name__)


# -------------------------------------------------------
# UTILS — RESET CACHE
# -------------------------------------------------------
def reset_cache():
    """Resets session state variables when selection changes."""
    keys = ["session", "drivers_full", "driver_map", "compare_result"]
    for k in keys:
        if k in st.session_state:
            st.session_state[k] = None
    logger.info("Comparison cache reset")


# -------------------------------------------------------
# PAGE CONFIG
# -------------------------------------------------------
st.set_page_config(
    page_title="Driver Comparison – AI Race Engineer",
    layout="wide",
)

load_css()
navbar()

# -------------------------------------------------------
# SESSION SELECTION
# -------------------------------------------------------
st.markdown("<h2 class='section-title'>Session Selection</h2>", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)

with col1:
    # Auswahl des Jahres triggert einen Rerun, damit die Streckenliste updated
    _current_year = datetime.now().year
    _year_options = list(range(_current_year, 2017, -1))  # current year → 2018
    year = st.selectbox(
        "Year",
        _year_options,
        index=0,  # Default: aktuelles Jahr
    )

with col2:
    # 1. Dynamische Streckenliste laden
    with st.spinner(f"Loading {year} Calendar..."):
        try:
            tracks_for_year = get_tracks_for_year(year)
            logger.debug("Tracks loaded", year=year, count=len(tracks_for_year or []))
        except Exception as e:
            logger.warning(
                "Track list load failed, using fallback", year=year, error=str(e)
            )
            tracks_for_year = []

    # 2. Fallback falls API offline ist (Offline Modus)
    if not tracks_for_year:
        tracks_for_year = [
            "Silverstone",
            "Monza",
            "Monaco",
            "Spa",
            "Red Bull Ring",
            "Suzuka",
            "Interlagos",
            "Bahrain",
            "Barcelona",
        ]
        # Nur eine kleine Warnung, damit man weiß, dass es der Fallback ist
        # st.caption("⚠️ Offline mode: Using fallback track list.")

    # 3. Default Wert finden (Silverstone oder der erste Eintrag)
    default_idx = 0
    if "Silverstone" in tracks_for_year:
        default_idx = tracks_for_year.index("Silverstone")

    track = st.selectbox("Track", tracks_for_year, index=default_idx)

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
        logger.info(
            "Loading session", year=year, track=track, session_type=session_type
        )
        session = load_session(year, track, session_type)

        if session is None:
            st.error("Could not load session data from FastF1.")
        else:
            # --- Detect which drivers have car telemetry available ---
            # FastF1 silently leaves car_data empty for drivers whose
            # telemetry the F1 API could not provide. We check upfront
            # so we can warn the user in the dropdown instead of
            # letting the comparison fail silently later.
            drivers_with_cardata: set[str] = set()
            if hasattr(session, "car_data") and session.car_data:
                try:
                    for drv_num, df in session.car_data.items():
                        if df is not None and not df.empty:
                            drivers_with_cardata.add(str(drv_num))
                except Exception:
                    pass  # If we can't read it, don't block anything

            driver_map = {}
            # Robust check for drivers in the session
            if hasattr(session, "laps"):
                # session.laps kann leer sein, wenn Session noch nicht geladen
                try:
                    unique_drivers = sorted(session.laps["Driver"].unique())
                except Exception:
                    unique_drivers = []
            else:
                unique_drivers = []

            for code in unique_drivers:
                try:
                    info = session.get_driver(code)
                    fn = info.get("FirstName", info.get("given_name", ""))
                    ln = info.get("LastName", info.get("family_name", ""))
                    drv_num = str(info.get("DriverNumber", ""))
                    # Mark drivers without car telemetry
                    has_tel = (
                        not drivers_with_cardata  # couldn't determine → assume OK
                        or drv_num in drivers_with_cardata
                    )
                    label = (
                        f"{fn} {ln} ({code})" if has_tel else f"⚠️ {fn} {ln} ({code})"
                    )
                    driver_map[label] = code
                except Exception as e:
                    logger.warning(
                        "Failed to resolve driver metadata",
                        driver_code=code,
                        error=str(e),
                    )
                    driver_map[code] = code

            st.session_state["session"] = session
            st.session_state["drivers_full"] = list(driver_map.keys())
            st.session_state["driver_map"] = driver_map

            no_tel_drivers = [
                code for label, code in driver_map.items() if label.startswith("⚠️")
            ]
            if no_tel_drivers:
                st.warning(
                    f"⚠️ No car telemetry available for: **{', '.join(no_tel_drivers)}** "
                    "in this session (marked in the dropdowns below). "
                    "These drivers cannot be compared."
                )

            st.success(f"Loaded: {year} {track} {session_type}")
            st.rerun()

    except DOMAIN_EXCEPTIONS as e:
        logger.error(
            "Session load failed (domain exception)",
            year=year,
            track=track,
            session_type=session_type,
            error=str(e),
            exc_info=True,
        )
        show_domain_error(e, fallback="Error loading session.", context="comparison")
    except Exception as e:
        logger.error(
            "Session load failed",
            year=year,
            track=track,
            session_type=session_type,
            error=str(e),
            exc_info=True,
        )
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
            logger.info("Comparing drivers", driver_a=driverA, driver_b=driverB)

            with st.spinner("Analyzing Telemetry..."):
                # Load telemetry data
                telA = load_telemetry(session, driverA)
                telB = load_telemetry(session, driverB)

                if telA is None or telB is None:
                    missing = []
                    if telA is None:
                        missing.append(driverA)
                    if telB is None:
                        missing.append(driverB)
                    st.error(
                        f"❌ No car telemetry data available for: **{', '.join(missing)}** "
                        "in this session. The F1 data API does not provide car data for "
                        "every driver in every session. Please select a different driver."
                    )
                    st.stop()

                # Perform corner analysis
                comp = compare_drivers_corner_level(session, driverA, driverB)
                tl = estimate_time_loss_per_corner(comp, driverA, driverB)

            # Store results in session state
            st.session_state["compare_result"] = {
                "session": session,
                "driverA": driverA,
                "driverB": driverB,
                "telA": telA,
                "telB": telB,
                "comp": comp,
                "tl": tl,
            }
            logger.info("Comparison complete", driver_a=driverA, driver_b=driverB)
            st.rerun()

        except DOMAIN_EXCEPTIONS as e:
            logger.error(
                "Driver comparison failed (domain exception)",
                driver_a=driverA_full,
                driver_b=driverB_full,
                error=str(e),
                exc_info=True,
            )
            show_domain_error(e, fallback="Compare failed.", context="comparison")
            st.caption(f"Details: `{type(e).__name__}: {e}`")
        except Exception as e:
            logger.error(
                "Driver comparison failed",
                error=str(e),
                exc_info=True,
            )
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

    # Create Tabs
    tab_overview, tab_inputs, tab_corners, tab_coaching = st.tabs(
        ["Overview", "Driver Inputs", "Corners", "Coaching"]
    )

    # -------------------------------------------------------
    # 1. OVERVIEW TAB
    # -------------------------------------------------------
    with tab_overview:
        st.markdown("<h2 class='section-title'>Summary</h2>", unsafe_allow_html=True)
        total_delta = tl["TimeLoss"].sum()

        # Key Performance Indicators
        c1, c2, c3 = st.columns(3)
        with c1:
            GlowCard.render("Total Time Delta", f"{total_delta:.3f}s")
        with c2:
            GlowCard.render("Track Status", "Dry")  # Placeholder
        with c3:
            GlowCard.render("Session", session_type)

        # --- DRIVER DNA ANALYSIS ---
        st.markdown("<h3>Driver Style Analysis (DNA)</h3>", unsafe_allow_html=True)
        try:
            dna_df = get_driver_dna_comparison_df(telA, telB, driverA, driverB)

            if dna_df is None or dna_df.empty:
                st.warning(
                    "Driver DNA is unavailable for the selected drivers/session."
                )
            else:
                # Layout: Radar Chart Left, Time Loss Bar Right
                col_dna, col_loss = st.columns([1, 1])

                with col_dna:
                    plot_driver_dna(
                        dna_df, driverA, driverB, key="radar_chart_overview"
                    )
                    st.caption(
                        "Analysis based on telemetry patterns (Aggressiveness, Smoothness, Input Workload)."
                    )

                with col_loss:
                    st.markdown("<b>Time Loss Distribution</b>", unsafe_allow_html=True)
                    plot_time_loss_bar(tl, key="time_loss_bar_overview")

        except Exception as e:
            logger.error(
                "Driver DNA calculation failed",
                driver_a=driverA,
                driver_b=driverB,
                error=str(e),
            )
            st.error(f"Could not calculate Driver DNA: {e}")

        st.markdown("---")

        # --- CORNER TYPE ANALYSIS ---
        st.markdown("<h3>Performance by Corner Type</h3>", unsafe_allow_html=True)

        # 1. Classify corners
        tl_classified = add_corner_classification(tl)

        # 2. Aggregate data
        agg_types = aggregate_time_loss_by_type(tl_classified)

        # 3. Visualization with Safety Check
        if agg_types is not None and not agg_types.empty:

            col_type_chart, col_type_text = st.columns([2, 1])

            with col_type_chart:
                plot_corner_type_performance(agg_types, key="corner_type_chart")

            with col_type_text:
                st.markdown("#### Engineering Insights")
                advice_list = get_corner_type_advice(agg_types)

                if not advice_list:
                    st.info("No major corner type dominance found.")
                else:
                    for advice in advice_list:
                        st.markdown(f"- {advice}")

                st.markdown("###### Breakdown")

                # Safe to render styled dataframe
                st.dataframe(
                    agg_types.style.format({"TimeLoss": "{:.3f}s"}),
                    hide_index=True,
                    width="stretch",
                )
        else:
            # Fallback if classification failed
            st.warning("Could not classify corners (Missing Speed Data).")

        # Additional Charts
        st.markdown("<h3>Speed Delta (Apex & Exit)</h3>", unsafe_allow_html=True)
        plot_speed_deltas(tl, driverA, driverB, key="speed_deltas_overview")

        st.markdown("<h3>Apex Speed Share</h3>", unsafe_allow_html=True)
        plot_apex_speed_share(tl, key="apex_share_overview")

    # -------------------------------------------------------
    # 2. DRIVER INPUTS TAB
    # -------------------------------------------------------
    with tab_inputs:
        st.markdown(
            "<h2 class='section-title'>Driver Inputs</h2>", unsafe_allow_html=True
        )
        ctm1, ctm2 = st.columns(2)
        with ctm1:
            plot_track_map(session, driverA, track)
        with ctm2:
            plot_track_map(session, driverB, track)

        plot_speed_profile(telA, telB, driverA, driverB, key="speed_prof_inputs")

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
            logger.warning(
                "Delta lap computation failed",
                driver_a=driverA,
                driver_b=driverB,
                error=str(e),
            )
            st.warning(f"Could not compute Delta Lap: {e}")

        plot_brake_throttle(telA, telB, driverA, driverB, key="brake_thr_inputs")

        col_gear1, col_gear2 = st.columns(2)
        with col_gear1:
            plot_gear_usage(telA, driverA, key="gear_A")
        with col_gear2:
            plot_gear_usage(telB, driverB, key="gear_B")

    # -------------------------------------------------------
    # 3. CORNERS TAB
    # -------------------------------------------------------
    with tab_corners:
        st.markdown(
            "<h2 class='section-title'>Corner-by-Corner Data</h2>",
            unsafe_allow_html=True,
        )
        # Using 'stretch' for full width in newer Streamlit versions
        # Or None if stretch causes issues on your version
        st.dataframe(tl, width="stretch")

    # -------------------------------------------------------
    # 4. COACHING TAB
    # -------------------------------------------------------
    with tab_coaching:
        st.markdown(
            "<h2 class='section-title'>AI Race Engineer</h2>", unsafe_allow_html=True
        )

        # 1. GENERATE EXECUTIVE REPORT (Macro View)
        if (
            agg_types is not None
            and tl_classified is not None
            and not tl_classified.empty
        ):
            try:
                report_data = generate_race_engineer_report(
                    tl_classified,
                    agg_types,
                    driverA,
                    driverB,
                    track,
                )
                render_race_engineer_report(report_data)
            except DOMAIN_EXCEPTIONS as e:
                logger.error("Report generation failed", error=str(e), exc_info=True)
                show_domain_error(
                    e,
                    fallback="Report could not be generated.",
                    context="comparison",
                )
            except Exception as e:
                logger.error("Unexpected report error", error=str(e), exc_info=True)
                st.warning("Report temporarily unavailable.")
        else:
            st.warning("Insufficient data to generate Executive Report.")

        st.markdown("---")

        # 2. DETAILED CORNER ANALYSIS (Micro View - Deine alte Engine)
        st.markdown("### Detailed Corner Analysis")
        st.caption("Specific telemetry deviations per corner.")

        try:
            suggestions = coaching_suggestions(tl, driverA, driverB)
        except DOMAIN_EXCEPTIONS as e:
            logger.error("Coaching engine failed", error=str(e), exc_info=True)
            show_domain_error(
                e,
                fallback="Coaching analysis unavailable.",
                context="comparison",
            )
            suggestions = []
        except Exception as e:
            logger.error("Unexpected coaching error", error=str(e), exc_info=True)
            st.warning("Detailed corner coaching unavailable.")
            suggestions = []

        if not suggestions:
            st.info("No significant weaknesses found in detail analysis.")
        else:
            # Wir stylen die Liste etwas schöner als Expanders
            for s in suggestions:
                with st.expander(f"{s.split(':')[0]}", expanded=False):
                    st.write(s.split(":")[1] if ":" in s else s)
