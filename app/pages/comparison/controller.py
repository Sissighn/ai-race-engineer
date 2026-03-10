import streamlit as st

from app.components.navbar import navbar
from app.utils.ui import load_css

from .results_tabs import render_comparison_results
from .selection_section import (
    handle_driver_comparison,
    handle_session_load,
    render_driver_selection,
    render_session_selection,
)
from .state import ensure_selection_state


def run_page() -> None:
    st.set_page_config(
        page_title="Driver Comparison – AI Race Engineer",
        layout="wide",
    )

    load_css()
    navbar()

    year, track, session_type = render_session_selection()

    if ensure_selection_state(year, track, session_type):
        return

    handle_session_load(year, track, session_type)

    selected_drivers = render_driver_selection()
    if selected_drivers:
        handle_driver_comparison(*selected_drivers)

    render_comparison_results(session_type=session_type, track=track)
