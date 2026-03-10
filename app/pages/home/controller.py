import streamlit as st

from app.components.navbar import navbar
from app.utils.ui import load_css

from .countdown_section import render_countdown_section
from .data_logic import get_started_events_for_season, load_home_context
from .latest_gp_section import render_latest_gp
from .results_section import render_results_tables


def run_page() -> None:
    st.set_page_config(page_title="AI Race Engineer – Home", layout="wide")

    st.markdown(
        """
    <style>
    [data-testid="stSidebar"] { display:none; }
    header {visibility:hidden;}
    </style>
    """,
        unsafe_allow_html=True,
    )

    load_css()
    navbar()
    st.markdown("<div class='main-content'>", unsafe_allow_html=True)

    context = load_home_context()
    render_latest_gp(
        display_event=context["display_event"],
        next_session_name=context["next_session_name"],
    )

    started_events = get_started_events_for_season(context["season_year"])
    render_results_tables(context["season_year"], started_events)

    render_countdown_section(context["next_session_time"])
