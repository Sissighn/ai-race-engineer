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
    plot_gear_usage,
    plot_speed_deltas,
    plot_speed_profile,
    plot_time_loss_bar,
)
from app.components.report_view import render_race_engineer_report
from app.components.track_map import plot_track_map
from app.utils.error_ui import DOMAIN_EXCEPTIONS, show_domain_error
from src.data.compare import sync_telemetry
from src.domain.analysis.driver_dna import get_driver_dna_comparison_df
from src.logging import get_logger
from src.models import ComparisonSessionState

logger = get_logger(__name__)


def render_comparison_results(session_type: str, track: str) -> None:
    if not st.session_state.get("compare_result"):
        return

    data = st.session_state["compare_result"]
    if isinstance(data, ComparisonSessionState):
        tl = data.tl
        tel_a = data.tel_a
        tel_b = data.tel_b
        driver_a = data.driver_a
        driver_b = data.driver_b
        session = data.session
    else:
        # Backward compatibility for pre-refactor session state payloads
        tl = data["tl"]
        tel_a = data["telA"]
        tel_b = data["telB"]
        driver_a = data["driverA"]
        driver_b = data["driverB"]
        session = data["session"]

    corner_analysis = build_corner_analysis(tl, driver_a=driver_a, driver_b=driver_b)
    tl_classified = corner_analysis.tl_classified
    agg_types = corner_analysis.agg_types
    advice_list = corner_analysis.advice_list

    tab_overview, tab_inputs, tab_corners, tab_coaching = st.tabs(
        ["Overview", "Driver Inputs", "Corners", "Coaching"]
    )

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

    with tab_inputs:
        _render_inputs_tab(
            tel_a=tel_a,
            tel_b=tel_b,
            driver_a=driver_a,
            driver_b=driver_b,
            session=session,
            track=track,
        )

    with tab_corners:
        _render_corners_tab(tl)

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
    st.markdown("<h2 class='section-title'>Summary</h2>", unsafe_allow_html=True)
    total_delta = tl["TimeLoss"].sum()

    c1, c2, c3 = st.columns(3)
    with c1:
        GlowCard.render("Total Time Delta", f"{total_delta:.3f}s")
    with c2:
        GlowCard.render("Track Status", "Dry")
    with c3:
        GlowCard.render("Session", session_type)

    st.markdown("<h3>Driver Style Analysis (DNA)</h3>", unsafe_allow_html=True)
    try:
        dna_df = get_driver_dna_comparison_df(tel_a, tel_b, driver_a, driver_b)

        if dna_df is None or dna_df.empty:
            st.warning("Driver DNA is unavailable for the selected drivers/session.")
        else:
            col_dna, col_loss = st.columns([1, 1])
            with col_dna:
                plot_driver_dna(dna_df, driver_a, driver_b, key="radar_chart_overview")
                st.caption(
                    "Analysis based on telemetry patterns (Aggressiveness, Smoothness, Input Workload)."
                )
            with col_loss:
                st.markdown("<b>Time Loss Distribution</b>", unsafe_allow_html=True)
                plot_time_loss_bar(tl, key="time_loss_bar_overview")

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
        col_type_chart, col_type_text = st.columns([2, 1])

        with col_type_chart:
            plot_corner_type_performance(agg_types, key="corner_type_chart")

        with col_type_text:
            st.markdown("#### Engineering Insights")

            if not advice_list:
                st.info("No major corner type dominance found.")
            else:
                for advice in advice_list:
                    st.markdown(f"- {advice}")

            st.markdown("###### Breakdown")
            st.dataframe(
                agg_types.style.format({"TimeLoss": "{:.3f}s"}),
                hide_index=True,
                width="stretch",
            )
    else:
        st.warning("Could not classify corners (Missing Speed Data).")

    st.markdown("<h3>Speed Delta (Apex & Exit)</h3>", unsafe_allow_html=True)
    plot_speed_deltas(tl, driver_a, driver_b, key="speed_deltas_overview")

    st.markdown("<h3>Apex Speed Share</h3>", unsafe_allow_html=True)
    plot_apex_speed_share(tl, key="apex_share_overview")


def _render_inputs_tab(
    tel_a, tel_b, driver_a: str, driver_b: str, session, track: str
) -> None:
    st.markdown("<h2 class='section-title'>Driver Inputs</h2>", unsafe_allow_html=True)

    ctm1, ctm2 = st.columns(2)
    with ctm1:
        plot_track_map(session, driver_a, track)
    with ctm2:
        plot_track_map(session, driver_b, track)

    plot_speed_profile(tel_a, tel_b, driver_a, driver_b, key="speed_prof_inputs")

    st.markdown("<h3>Delta Lap Overlay</h3>", unsafe_allow_html=True)
    try:
        tel_sync = sync_telemetry(tel_a, tel_b)
        df_a = tel_sync.rename(columns={"Speed_1": "Speed_A", "Time_1": "Time_A"})[
            ["Distance", "Speed_A", "Time_A"]
        ]
        df_b = tel_sync.rename(columns={"Speed_2": "Speed_B", "Time_2": "Time_B"})[
            ["Distance", "Speed_B", "Time_B"]
        ]
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

    plot_brake_throttle(tel_a, tel_b, driver_a, driver_b, key="brake_thr_inputs")

    col_gear1, col_gear2 = st.columns(2)
    with col_gear1:
        plot_gear_usage(tel_a, driver_a, key="gear_A")
    with col_gear2:
        plot_gear_usage(tel_b, driver_b, key="gear_B")


def _render_corners_tab(tl) -> None:
    st.markdown(
        "<h2 class='section-title'>Corner-by-Corner Data</h2>",
        unsafe_allow_html=True,
    )
    st.dataframe(tl, width="stretch")


def _render_coaching_tab(
    tl,
    tl_classified,
    agg_types,
    driver_a: str,
    driver_b: str,
    track: str,
) -> None:
    st.markdown(
        "<h2 class='section-title'>AI Race Engineer</h2>", unsafe_allow_html=True
    )

    try:
        report_data = build_race_engineer_report(
            tl_classified,
            agg_types,
            driver_a,
            driver_b,
            track,
        )

        if report_data is not None:
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
        for suggestion in suggestions:
            with st.expander(f"{suggestion.split(':')[0]}", expanded=False):
                st.write(suggestion.split(":")[1] if ":" in suggestion else suggestion)
