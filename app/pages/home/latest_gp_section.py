import html

import pandas as pd
import streamlit as st

from app.components.glow_card import GlowCard


def render_latest_gp(display_event, next_session_name: str) -> None:
    """Render the latest Grand Prix summary section.

    Args:
        display_event: Pandas Series with event metadata (EventName, Location, etc.).
        next_session_name: Human-readable name of the upcoming session.
    """
    event_long = html.escape(str(display_event["EventName"]))
    location = html.escape(str(display_event["Location"]))
    country = html.escape(str(display_event["Country"]))
    event_date = display_event["EventDate"]
    event_date_label = html.escape(pd.to_datetime(event_date).strftime("%d %B %Y"))
    next_session_label = html.escape(str(next_session_name))
    location_card = GlowCard.to_html("Location", f"{location}, {country}")
    event_date_card = GlowCard.to_html("Event Date", event_date_label)
    next_session_card = GlowCard.to_html("Type", next_session_label)

    GlowCard._inject_code()

    section_html = (
        '<section class="latest-gp-section">'
        '<h2 class="section-title">Latest Grand Prix</h2>'
        '<div class="latest-gp-grid">'
        '<div class="latest-gp-column">'
        f'<h3 class="latest-gp-heading">{event_long}</h3>'
        '<div class="latest-gp-card-stack">'
        f"{location_card}{event_date_card}"
        "</div>"
        "</div>"
        '<div class="latest-gp-column latest-gp-column--next">'
        '<h3 class="latest-gp-heading">Next session</h3>'
        '<div class="latest-gp-card-stack latest-gp-card-stack--single">'
        f"{next_session_card}"
        "</div>"
        "</div>"
        "</div>"
        "</section>"
    )

    st.markdown(section_html, unsafe_allow_html=True)
