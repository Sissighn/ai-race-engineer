import pandas as pd
import streamlit as st

from app.components.results_view import render_f1_table
from src.logging import get_logger

from .data_logic import load_event_results

logger = get_logger(__name__)


def render_results_tables(season_year: int, started_events: list) -> None:
    if not started_events:
        st.warning("No events have started yet this season.")
        return

    _initialize_event_index(started_events)

    current_display_event = started_events[st.session_state.event_index]
    display_event_name = current_display_event["EventName"]
    display_event_key = current_display_event["OfficialEventName"]

    st.markdown(
        "<h2 class='section-title' style='text-align: center;'>Current Event Results</h2>",
        unsafe_allow_html=True,
    )

    col_nav1, col_nav2, col_nav3 = st.columns([4, 12, 4])

    with col_nav1:
        if st.button(
            "←", key="prev_event", disabled=(st.session_state.event_index <= 0)
        ):
            st.session_state.event_index -= 1
            st.rerun()

    with col_nav2:
        st.markdown(
            f"<h3 style='text-align: center;'>‹ {display_event_name} Results ›</h3>",
            unsafe_allow_html=True,
        )

    with col_nav3:
        if st.button(
            "→",
            key="next_event",
            disabled=(st.session_state.event_index >= len(started_events) - 1),
        ):
            st.session_state.event_index += 1
            st.rerun()

    display_results = load_event_results(season_year, display_event_key)
    logger.debug(
        "Rendering event results",
        season_year=season_year,
        display_event_name=display_event_name,
    )

    pairs = [
        ("S", "Sprint", "SQ", "Sprint Qualifying"),
        ("Q", "Qualifying", "R", "Race"),
    ]

    for left_key, left_title, right_key, right_title in pairs:
        col_a, col_b = st.columns([1, 1], gap="medium")

        with col_a:
            st.markdown(
                render_f1_table(display_results.get(left_key), left_title),
                unsafe_allow_html=True,
            )
        with col_b:
            st.markdown(
                render_f1_table(display_results.get(right_key), right_title),
                unsafe_allow_html=True,
            )


def _initialize_event_index(started_events: list) -> None:
    if "event_index" not in st.session_state:
        st.session_state.event_index = 0

    now = pd.Timestamp.now(tz="UTC")
    latest_completed_idx_calc = 0

    for i, event in enumerate(started_events):
        last_session_date = None
        for col in [
            "Session5DateUtc",
            "Session4DateUtc",
            "Session3DateUtc",
            "Session2DateUtc",
            "Session1DateUtc",
        ]:
            if pd.notna(event.get(col)):
                last_session_date = event[col]
                break

        if last_session_date and last_session_date < now:
            latest_completed_idx_calc = i

    if "event_index_initialized" not in st.session_state:
        st.session_state.event_index = latest_completed_idx_calc
        st.session_state.event_index_initialized = True

    st.session_state.event_index = max(
        0, min(st.session_state.event_index, len(started_events) - 1)
    )
