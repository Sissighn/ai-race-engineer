"""
Results view module for driver comparison analysis.

This module handles the rendering and display of comparison results
between two drivers across multiple analytical tabs including overview,
driver inputs, corner-by-corner analysis, and AI-powered coaching.
"""

import streamlit as st

from src.application.comparison_service import (
    build_coaching_suggestions,
    build_corner_analysis,
    build_race_engineer_report,
)
from app.components.advanced_plots.plot_delta_lap import (
    compute_delta_lap,
    plot_delta_lap,
)
from app.components.glow_card import GlowCard
from app.components.plots import (
    plot_apex_speed_share,
    plot_brake_throttle,
    plot_corner_type_performance,
    plot_driver_dna,
    plot_exit_speed_delta,
    plot_gear_usage,
    plot_speed_profile,
    plot_time_loss_bar,
)
from app.components.report_view import render_race_engineer_report
from app.components.track_map import plot_track_map_comparison
from app.utils.error_ui import DOMAIN_EXCEPTIONS, show_domain_error
from src.data.compare import sync_telemetry
from src.domain.analysis.driver_dna import get_driver_dna_comparison_df
from src.logging import get_logger
from src.models import ComparisonSessionState

logger = get_logger(__name__)


def render_comparison_results(session_type: str, track: str) -> None:
    """
    Main entry point for rendering driver comparison analysis results.

    Retrieves comparison data from session state and orchestrates the rendering
    of four analysis tabs: Overview, Driver Inputs, Corners, and Coaching.
    Handles backward compatibility with legacy session state payloads.

    Args:
        session_type (str): Type of session (e.g., 'Race', 'Qualifying', 'Practice')
        track (str): Track name for context-specific analysis
    """
    # Exit early if no comparison data is available
    if not st.session_state.get("compare_result"):
        return

    # Extract comparison data from session state
    data: ComparisonSessionState = st.session_state["compare_result"]
    tl = data.tl
    tel_a = data.tel_a
    tel_b = data.tel_b
    driver_a = data.driver_a
    driver_b = data.driver_b
    session = data.session

    # Perform corner analysis to extract time loss classification and insights
    corner_analysis = build_corner_analysis(tl, driver_a=driver_a, driver_b=driver_b)
    tl_classified = corner_analysis.tl_classified
    agg_types = corner_analysis.agg_types
    advice_list = corner_analysis.advice_list

    # Organize results into four main analysis tabs
    tab_overview, tab_inputs, tab_corners, tab_coaching = st.tabs(
        ["Overview", "Driver Inputs", "Corners", "Coaching"]
    )

    # Tab 1: High-level summary with key metrics and driver DNA analysis
    with tab_overview:
        _render_overview_tab(
            tl=tl,
            tel_a=tel_a,
            tel_b=tel_b,
            driver_a=driver_a,
            driver_b=driver_b,
            session_type=session_type,
            agg_types=agg_types,
            advice_list=advice_list,
        )

    # Tab 2: Detailed driver input analysis (steering, throttle, braking, gear)
    with tab_inputs:
        _render_inputs_tab(
            tel_a=tel_a,
            tel_b=tel_b,
            driver_a=driver_a,
            driver_b=driver_b,
            session=session,
            track=track,
        )

    # Tab 3: Raw corner-by-corner telemetry data
    with tab_corners:
        _render_corners_tab(tl)

    # Tab 4: AI-powered coaching insights and recommendations
    with tab_coaching:
        _render_coaching_tab(
            tl=tl,
            tl_classified=tl_classified,
            agg_types=agg_types,
            driver_a=driver_a,
            driver_b=driver_b,
            track=track,
        )


def _render_overview_tab(
    tl,
    tel_a,
    tel_b,
    driver_a: str,
    driver_b: str,
    session_type: str,
    agg_types,
    advice_list: list[str],
) -> None:
    """
    Render the Overview tab with summary metrics and high-level analysis.

    Displays:
    - Total time delta between drivers
    - Key performance metrics (track status, session type)
    - Driver DNA radar chart comparing driving styles
    - Performance breakdown by corner type
    - Apex speed share and exit speed deltas
    """
    st.markdown("<h2 class='section-title'>Summary</h2>", unsafe_allow_html=True)
    # Calculate cumulative time loss across all corners
    total_delta = tl["TimeLoss"].sum()

    # Display key metrics in a three-column layout
    c1, c2, c3 = st.columns(3)
    with c1:
        GlowCard.render("Total Time Delta", f"{total_delta:.3f}s")
    with c2:
        GlowCard.render("Track Status", "Dry")
    with c3:
        GlowCard.render("Session", session_type)

    # Driver Style Analysis section
    st.markdown("<h3>Driver Style Analysis (DNA)</h3>", unsafe_allow_html=True)
    try:
        # Generate driver DNA comparison dataframe
        dna_df = get_driver_dna_comparison_df(tel_a, tel_b, driver_a, driver_b)

        if dna_df is None or dna_df.empty:
            st.warning("Driver DNA is unavailable for the selected drivers/session.")
        else:
            # Display DNA radar chart and time loss breakdown side-by-side
            col_dna, col_loss = st.columns([1, 1])
            with col_dna:
                plot_driver_dna(dna_df, driver_a, driver_b, key="radar_chart_overview")
            with col_loss:
                plot_time_loss_bar(
                    tl,
                    driver_a=driver_a,
                    driver_b=driver_b,
                    key="time_loss_bar_overview",
                )

    except Exception as e:
        logger.error(
            "Driver DNA calculation failed",
            driver_a=driver_a,
            driver_b=driver_b,
            error=str(e),
        )
        st.error(f"Could not calculate Driver DNA: {e}")

    st.markdown("---")
    st.markdown("<h3>Performance by Corner Type</h3>", unsafe_allow_html=True)

    if agg_types is not None and not agg_types.empty:
        # Display corner type performance chart with engineering insights
        col_type_chart, col_type_text = st.columns([2, 1])

        with col_type_chart:
            plot_corner_type_performance(agg_types, key="corner_type_chart")

        with col_type_text:
            st.markdown("#### Engineering Insights")

            if not advice_list:
                st.info("No major corner type dominance found.")
            else:
                # Display AI-generated insights for each corner type dominance
                for advice in advice_list:
                    st.markdown(f"- {advice}")

            st.markdown("###### Breakdown")
            # Display aggregated time loss statistics by corner type
            st.dataframe(
                agg_types.style.format({"TimeLoss": "{:.3f}s"}),
                hide_index=True,
                width="stretch",
            )
    else:
        st.warning("Could not classify corners (Missing Speed Data).")

    # Display speed and exit speed analysis across the lap
    plot_apex_speed_share(
        tl,
        driver_a=driver_a,
        driver_b=driver_b,
        key="apex_share_overview",
    )

    plot_exit_speed_delta(
        tl,
        driver_a=driver_a,
        driver_b=driver_b,
        key="exit_speed_delta_overview",
    )


def _render_inputs_tab(
    tel_a, tel_b, driver_a: str, driver_b: str, session, track: str
) -> None:
    """
    Render the Driver Inputs tab with detailed telemetry analysis.

    Displays:
    - Track speed maps showing fastest-lap speed profiles
    - Speed profile comparison
    - Delta lap overlay (cumulative time gain/loss visualization)
    - Brake and throttle input comparison
    - Gear usage patterns
    """
    st.markdown("<h2 class='section-title'>Driver Inputs</h2>", unsafe_allow_html=True)
    # Track speed visualization section
    st.markdown("<h3>Track Speed Maps</h3>", unsafe_allow_html=True)
    st.caption(
        "Fastest-lap track position colored by speed [km/h]. Both drivers use the same color scale for direct comparison."
    )
    # Render comparative track maps for both drivers
    plot_track_map_comparison(session, driver_a, driver_b, track, metric="speed")

    # Display speed profile across the entire lap
    plot_speed_profile(tel_a, tel_b, driver_a, driver_b, key="speed_prof_inputs")

    # Delta lap overlay section - shows cumulative time gain/loss throughout lap
    st.markdown("<h3>Delta Lap Overlay</h3>", unsafe_allow_html=True)
    try:
        # Synchronize telemetry data between drivers for accurate delta calculation
        tel_sync = sync_telemetry(tel_a, tel_b)
        df_a = tel_sync.rename(columns={"Speed_1": "Speed_A", "Time_1": "Time_A"})[
            ["Distance", "Speed_A", "Time_A"]
        ]
        df_b = tel_sync.rename(columns={"Speed_2": "Speed_B", "Time_2": "Time_B"})[
            ["Distance", "Speed_B", "Time_B"]
        ]
        # Compute delta values showing time gain/loss at each track position
        delta_df = compute_delta_lap(df_a, df_b)
        plot_delta_lap(delta_df, driver_a, driver_b)
    except Exception as e:
        logger.warning(
            "Delta lap computation failed",
            driver_a=driver_a,
            driver_b=driver_b,
            error=str(e),
        )
        st.warning(f"Could not compute Delta Lap: {e}")

    # Brake and throttle input comparison
    plot_brake_throttle(tel_a, tel_b, driver_a, driver_b, key="brake_thr_inputs")

    # Display gear usage patterns for both drivers side-by-side
    col_gear1, col_gear2 = st.columns(2)
    with col_gear1:
        plot_gear_usage(tel_a, driver_a, key="gear_A")
    with col_gear2:
        plot_gear_usage(tel_b, driver_b, key="gear_B")


def _render_corners_tab(tl) -> None:
    """
    Render the Corners tab with raw corner-by-corner telemetry data.

    Displays:
    - Complete time loss breakdown by individual corners
    - Distance, speed, and other telemetry metrics per corner
    """
    st.markdown(
        "<h2 class='section-title'>Corner-by-Corner Data</h2>",
        unsafe_allow_html=True,
    )
    # Display raw telemetry data with time loss for each corner
    st.dataframe(tl, width="stretch")


def _render_coaching_tab(
    tl,
    tl_classified,
    agg_types,
    driver_a: str,
    driver_b: str,
    track: str,
) -> None:
    """
    Render the Coaching tab with AI-powered race engineering insights.

    Displays:
    - Executive race engineer report with strategic recommendations
    - Detailed corner-by-corner coaching suggestions
    - Specific telemetry deviations and improvement opportunities
    """
    st.markdown(
        "<h2 class='section-title'>AI Race Engineer</h2>", unsafe_allow_html=True
    )

    try:
        # Generate comprehensive race engineering report with strategic insights
        report_data = build_race_engineer_report(
            tl_classified,
            agg_types,
            driver_a,
            driver_b,
            track,
        )

        if report_data is not None:
            # Render the executive report with recommendations
            render_race_engineer_report(report_data)
        else:
            st.warning("Insufficient data to generate Executive Report.")
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

    st.markdown("---")
    st.markdown("### Detailed Corner Analysis")
    st.caption("Specific telemetry deviations per corner.")

    try:
        # Generate AI-powered coaching suggestions for each corner
        suggestions = build_coaching_suggestions(tl, driver_a, driver_b)
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
        # Display coaching suggestions in collapsible sections, one per corner
        for suggestion in suggestions:
            with st.expander(f"{suggestion.split(':')[0]}", expanded=False):
                st.write(suggestion.split(":")[1] if ":" in suggestion else suggestion)
