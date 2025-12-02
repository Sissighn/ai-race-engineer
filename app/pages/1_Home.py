import streamlit as st
import pandas as pd
import sys
import os
import re
import fastf1
import time

# -------------------
# Load Data Methods
# -------------------
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import components
from app.utils.ui import load_css
from app.components.navbar import navbar
from app.components.glow_card import GlowCard
from src.data.latest_session import get_latest_sessions, get_season_results
from app.components.results_view import render_f1_table


@st.cache_resource
def load_event_results(year, event_key):
    """
    Load all event results (Q, SQ, S, R) only once.
    Fastest possible solution.
    """
    return get_season_results(year, event_key)


# ------------------------------------
# Streamlit Page Config
# ------------------------------------
st.set_page_config(page_title="AI Race Engineer – Home", layout="wide")

# Hide Streamlit sidebar
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

# ------------------------------------
# Logic: Load Data & Sessions
# ------------------------------------
session_data = get_latest_sessions()

# Get events DataFrame
events_df = session_data["events"]
latest_completed_idx = session_data["latest_completed_index"]

# Get next session info
next_session_name = session_data["next_session_name"]
next_session_time = session_data["next_session_time"]

now = pd.Timestamp.now(tz="UTC")

if pd.notna(next_session_time) and next_session_time > now:
    # Find which event the next session belongs to
    display_event = None
    for idx, event in events_df.iterrows():
        session_cols = [
            "Session1DateUtc",
            "Session2DateUtc",
            "Session3DateUtc",
            "Session4DateUtc",
            "Session5DateUtc",
        ]
        for col in session_cols:
            if pd.notna(event.get(col)) and event[col] == next_session_time:
                display_event = event
                break
        if display_event is not None:
            break

    if display_event is None:
        display_event = events_df.iloc[latest_completed_idx]
else:
    display_event = events_df.iloc[latest_completed_idx]

event_long = display_event["EventName"]
location = display_event["Location"]
country = display_event["Country"]
event_date = display_event["EventDate"]
season_year = int(str(event_date)[:4])
event_key = display_event["OfficialEventName"]

# ------------------------------------
# UI: Top Section
# ------------------------------------
st.markdown("<h2 class='section-title'>Latest Grand Prix</h2>", unsafe_allow_html=True)

col1, col2 = st.columns([2, 1])

with col1:
    st.markdown(f"<h3>{event_long}</h3>", unsafe_allow_html=True)

    # Use GlowCard for static info
    GlowCard.render("Location", f"{location}, {country}")
    GlowCard.render("Event Date", pd.to_datetime(event_date).strftime("%d %B %Y"))

with col2:
    st.markdown("<h3>Next session</h3>", unsafe_allow_html=True)
    GlowCard.render("Type", next_session_name)

# ------------------------------------
# Results Tables
# ------------------------------------

# Initialize session state for event navigation
if "event_index" not in st.session_state:
    st.session_state.event_index = 0

# Get all events for the season
all_events = fastf1.get_event_schedule(season_year)
now = pd.Timestamp.now(tz="UTC")

# Normalize dates
for col in [
    "Session1DateUtc",
    "Session2DateUtc",
    "Session3DateUtc",
    "Session4DateUtc",
    "Session5DateUtc",
]:
    if col in all_events.columns:
        all_events[col] = pd.to_datetime(all_events[col], utc=True)

# Filter to events that have started (at least FP1 happened)
started_events = []
for idx, event in all_events.iterrows():
    if pd.notna(event.get("Session1DateUtc")) and event["Session1DateUtc"] < now:
        started_events.append(event)

if not started_events:
    st.warning("No events have started yet this season.")
else:
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

    current_display_event = started_events[st.session_state.event_index]
    display_event_name = current_display_event["EventName"]
    display_event_key = current_display_event["OfficialEventName"]

    # Navigation buttons
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

    pairs = [
        ("S", "Sprint", "SQ", "Sprint Qualifying"),
        ("Q", "Qualifying", "R", "Race"),
    ]

    for left_key, left_title, right_key, right_title in pairs:
        colA, colB = st.columns([1, 1], gap="medium")

        with colA:
            st.markdown(
                render_f1_table(display_results.get(left_key), left_title),
                unsafe_allow_html=True,
            )
        with colB:
            st.markdown(
                render_f1_table(display_results.get(right_key), right_title),
                unsafe_allow_html=True,
            )

# ------------------------------------
# COUNTDOWN SECTION
# ------------------------------------

st.markdown(
    "<h2 class='section-title'>Next Session Countdown</h2>", unsafe_allow_html=True
)

countdown_box = st.empty()


def render_countdown():
    """
    Renders the countdown using the GlowCard HTML structure.
    """
    if next_session_time is None or pd.isna(next_session_time):
        # Fallback using Glow Card classes manually
        countdown_box.markdown(
            """
            <div class="glow-card-wrapper">
                <div class="glow-card-content">
                    <div class="gc-title">Time until next session</div>
                    <div class="gc-value">n/a</div>
                </div>
            </div>
        """,
            unsafe_allow_html=True,
        )
        return

    now = pd.Timestamp.now(tz="UTC")
    delta = next_session_time - now

    if delta.total_seconds() <= 0:
        countdown_text = "Session in progress"
    else:
        total = int(delta.total_seconds())

        days = total // 86400
        hrs = (total % 86400) // 3600
        mins = (total % 3600) // 60
        secs = total % 60
        if days > 0:
            countdown_text = f"{days}d {hrs}h {mins:02d}m {secs:02d}s"
        else:
            countdown_text = f"{hrs:02d}h {mins:02d}m {secs:02d}s"

    # Render with the same HTML class structure as GlowCard
    countdown_box.markdown(
        f"""
        <div class="glow-card-wrapper">
            <div class="glow-card-content">
                <div class="gc-title">Time until next session</div>
                <div class="gc-value">{countdown_text}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# Live ticking countdown
while True:
    render_countdown()
    time.sleep(1)
