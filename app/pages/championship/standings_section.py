import pandas as pd
import streamlit as st

from app.components.results_view import render_f1_table
from src.models import ChampionshipStandingsPayload


def _format_standings_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    formatted = df.copy()
    if "Points" in formatted.columns:
        formatted["Points"] = formatted["Points"].apply(
            lambda value: (
                int(value) if pd.notna(value) and float(value).is_integer() else value
            )
        )
    return formatted


def render_championship_standings(payload: ChampionshipStandingsPayload) -> None:
    st.markdown(
        "<h2 class='section-title event-results-title'>Current Championship Standings</h2>",
        unsafe_allow_html=True,
    )

    if payload.drivers_df.empty and payload.constructors_df.empty:
        st.warning(
            "Championship standings are not available yet. Please check back after the first sprint or race result has been published."
        )
        return

    summary_col1, summary_col2, summary_col3 = st.columns([1, 1, 2], gap="medium")
    with summary_col1:
        st.markdown(f"**Season:** {payload.season_year}")
    with summary_col2:
        st.markdown(f"**Events Counted:** {payload.events_count}")
    with summary_col3:
        st.markdown(
            f"**Sessions Loaded:** {payload.sessions_loaded} (Sprint + Race points automatically updated)"
        )

    driver_table = _format_standings_dataframe(payload.drivers_df)
    constructor_table = _format_standings_dataframe(payload.constructors_df)

    left_col, right_col = st.columns([1, 1], gap="large")
    with left_col:
        st.markdown(
            render_f1_table(
                driver_table,
                f"Driver Championship Standings ({payload.season_year})",
            ),
            unsafe_allow_html=True,
        )
    with right_col:
        st.markdown(
            render_f1_table(
                constructor_table,
                f"Team Championship Standings ({payload.season_year})",
            ),
            unsafe_allow_html=True,
        )
