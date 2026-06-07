import pandas as pd
import streamlit as st

from app.components.navbar import navbar
from app.utils.ui import load_css
from .data_logic import fetch_championship_standings, get_season_year_options
from .standings_section import render_championship_standings


def run_page() -> None:
    st.set_page_config(
        page_title="Championship Standings – AI Race Engineer",
        layout="wide",
    )

    load_css()
    navbar()

    st.markdown("<div class='main-content'>", unsafe_allow_html=True)

    year_options = get_season_year_options()
    season_year = st.selectbox(
        "Season", year_options, index=0, key="championship_season"
    )

    championship_payload = fetch_championship_standings(season_year)
    render_championship_standings(championship_payload)
