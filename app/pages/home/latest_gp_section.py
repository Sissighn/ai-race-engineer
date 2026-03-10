import pandas as pd
import streamlit as st

from app.components.glow_card import GlowCard


def render_latest_gp(display_event, next_session_name: str) -> None:
    event_long = display_event["EventName"]
    location = display_event["Location"]
    country = display_event["Country"]
    event_date = display_event["EventDate"]

    st.markdown(
        "<h2 class='section-title'>Latest Grand Prix</h2>", unsafe_allow_html=True
    )

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown(f"<h3>{event_long}</h3>", unsafe_allow_html=True)
        GlowCard.render("Location", f"{location}, {country}")
        GlowCard.render("Event Date", pd.to_datetime(event_date).strftime("%d %B %Y"))

    with col2:
        st.markdown("<h3>Next session</h3>", unsafe_allow_html=True)
        GlowCard.render("Type", next_session_name)
