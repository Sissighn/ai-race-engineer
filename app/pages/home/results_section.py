import streamlit as st

from app.components.results_view import render_f1_table
from src.logging import get_logger

from .data_logic import load_event_results

logger = get_logger(__name__)


def render_results_tables(
    season_year: int,
    started_events: list,
    current_event_key: str | None = None,
) -> None:
    """Render navigable results tables for all started events in a season.

    Args:
        season_year: F1 season year.
        started_events: List of event Series objects that have started.
        current_event_key: Official event name for the active race weekend.
    """
    if not started_events:
        st.warning("No events have started yet this season.")
        return

    _initialize_event_index(started_events, current_event_key)

    current_display_event = started_events[st.session_state.event_index]
    display_event_name = current_display_event["EventName"]
    display_event_key = current_display_event["OfficialEventName"]

    st.markdown(
        "<h2 class='section-title event-results-title'>Current Event Results</h2>",
        unsafe_allow_html=True,
    )

    col_spacer_left, col_nav_prev, col_nav_title, col_nav_next, col_spacer_right = st.columns(
        [1.5, 1, 6, 1, 1.5], gap="small"
    )

    with col_spacer_left:
        st.empty()

    with col_nav_prev:
        if st.button("←", key="prev_event", disabled=(st.session_state.event_index <= 0)):
            st.session_state.event_index -= 1
            st.session_state.event_index_user_selected = True
            st.rerun()

    with col_nav_title:
        st.markdown(
            f"<h3 class='event-results-current'>‹ {display_event_name} Results ›</h3>",
            unsafe_allow_html=True,
        )

    with col_nav_next:
        if st.button(
            "→",
            key="next_event",
            disabled=(st.session_state.event_index >= len(started_events) - 1),
        ):
            st.session_state.event_index += 1
            st.session_state.event_index_user_selected = True
            st.rerun()

    with col_spacer_right:
        st.empty()

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


def _initialize_event_index(started_events: list, current_event_key: str | None) -> None:
    target_index = _resolve_current_event_index(started_events, current_event_key)
    previous_target_key = st.session_state.get("event_index_target_key")
    target_key = started_events[target_index].get("OfficialEventName")

    should_reset_to_current = (
        "event_index" not in st.session_state
        or previous_target_key != target_key
        or not st.session_state.get("event_index_user_selected", False)
    )

    if should_reset_to_current:
        st.session_state.event_index = target_index
        st.session_state.event_index_target_key = target_key
        st.session_state.event_index_user_selected = False

    st.session_state.event_index = max(
        0, min(st.session_state.event_index, len(started_events) - 1)
    )


def _resolve_current_event_index(started_events: list, current_event_key: str | None) -> int:
    if current_event_key:
        for i, event in enumerate(started_events):
            if event.get("OfficialEventName") == current_event_key:
                return i

    return len(started_events) - 1
