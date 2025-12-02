import streamlit as st
import pandas as pd
import sys
import os
import re
import fastf1


@st.cache_resource
def load_event_results(year, event_key):
    """
    Load all event results (Q, SQ, S, R) only once.
    Fastest possible solution.
    """
    return get_season_results(year, event_key)

# -------------------
# Load Data Methods
# -------------------
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.components.navbar import navbar
from src.data.latest_session import get_latest_sessions, get_season_results


# ------------------------------------
# Streamlit Page Config
# ------------------------------------
st.set_page_config(
    page_title="AI Race Engineer – Home",
    layout="wide",
)

# Hide Streamlit sidebar
st.markdown("""
<style>
[data-testid="stSidebar"] { display:none; }
header {visibility:hidden;}
</style>
""", unsafe_allow_html=True)

navbar()
st.markdown("<div class='main-content'>", unsafe_allow_html=True)


# ------------------------------------
# DARK THEME GLOBAL CSS (F1 STYLE)
# ------------------------------------
st.markdown("""
<style>

@import url('https://fonts.googleapis.com/css2?family=Tektur:wght@400..900&family=Playfair:ital,opsz,wght@0,5..1200,300..900;1,5..1200,300..900&display=swap');

html, body, [class*="block-container"] {
    background-color: #191919 !important;
    color: #FFFFFF !important;
    font-optical-sizing: auto;
}


/* Section Titles */
.section-title {
    font-size: 1.6rem;
    font-weight: 700;
    font-family: 'Tektur', sans-serif !important;
    font-optical-sizing: auto;
    font-variation-settings: "wdth" 100;
    margin-top: 1.2rem;
}

.main-content h1,
.main-content h2,
.main-content h3,
.main-content h4,
.main-content h5,
.main-content h6 {
    font-family: 'Tektur', sans-serif !important;
    font-optical-sizing: auto !important;
    font-variation-settings: "wdth" 100 !important;
    font-weight: 700 !important;
}


/* Cards */
.card {
    background: #141414;
    border-radius: 14px;
    padding: 16px 20px;
    border: 1px solid #1F1F1F;
    margin-bottom: 14px;
    box-shadow: 0px 0px 10px rgba(211, 0, 0, 0.15);
    font-family: 'Playfair', serif !important;
}

.card-title {
    font-size: 0.8rem;
    color: #8e1f1f;
    font-weight: 600;
    margin-bottom: 5px;
    font-family: 'Playfair', serif !important;
}

.card-value {
    font-size: 1.3rem;
    font-weight: 700;
    font-family: 'Playfair', serif !important;
}

/* TABLE CONTAINER */
.tableBox {
    background: #141414;
    padding: 22px 26px;
    border-radius: 14px;
    width: 100%;
    max-width: 900px;  
    margin: 10px auto 30px auto;
    border: 1px solid #1F1F1F;
    box-shadow: 0px 0px 10px rgba(211, 0, 0, 0.12);
    overflow-x: auto;
}

.tableBox h3 {
    font-family: 'Tektur', sans-serif !important;
    font-weight: 700 !important;
}

.tableBox p {
    font-family: 'Playfair', serif !important;
}

/* Responsive table */
.tableBox table {
    width: 100%;
    min-width: 400px;
}

/* TABLE HEADER */
table th {
    background: #161616 !important;
    color: #FFFFFF !important;
    font-weight: 700 !important;
    border-bottom: 2px solid #7d0e0e !important;
    text-align: left !important;
    padding: 10px 8px !important;
    font-family: 'Tektur', sans-serif !important;
}

/* TABLE ROWS */
table td {
    background: #141414 !important;
    padding: 8px 8px !important;
    border-bottom: 1px solid #222 !important;
    font-family: 'Playfair', serif !important;
}

/* Hover effect */
table tr:hover td {
    background: #1E1E1E !important;
}

/* Center page */
.center {
    display: flex;
    justify-content: center;
}

/* Button styling */
.stButton > button {
    background-color: #7d0e0e !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: px !important;
    padding: 10px 24px !important;
    font-weight: 600 !important;
    transition: all 0.3s ease !important;
}

.stButton > button:hover {
    background-color: #8e1f1f !important;
    box-shadow: 0px 0px 15px rgba(211, 0, 0, 0.4) !important;
}

</style>
""", unsafe_allow_html=True)


# ------------------------------------
# Helpers
# ------------------------------------

def clean_position(num):
    try:
        return int(float(num))
    except:
        return num

# Convert F1 time format
def format_f1_time(raw):
    """
    Convert '0 days 00:25:09.054000' → '25:09.054'
    """
    text = str(raw)

    match = re.search(r'(\d+ days )?(\d+):(\d+):(\d+\.\d+)', text)
    if not match:
        return text

    hours = int(match.group(2))
    mins = int(match.group(3))
    secs = float(match.group(4))

    total_mins = hours * 60 + mins
    return f"{total_mins}:{secs:06.3f}"


def render_f1_table(df, title):
    if df is None or df.empty:
        return f"""
        <div class="tableBox">
            <h3>{title}</h3>
            <p style="color:#AAA;">No data yet.</p>
        </div>
        """

    df = df.copy()

    drop_cols = ["Status", "Session", "EventName", "Event", "Season", "Milliseconds"]
    for c in drop_cols:
        if c in df.columns:
            df = df.drop(columns=c)

    if "Position" in df.columns:
        df["Position"] = df["Position"].apply(clean_position)

    if "Time" in df.columns:
        df["Time"] = df["Time"].apply(format_f1_time)

    html_table = df.to_html(
        index=False,
        classes="compact",
        border=0
    )

    return f"""
    <div class="tableBox">
        <h3>{title}</h3>
        {html_table}
    </div>
    """


# ------------------------------------
# Load Latest Event
# ------------------------------------
session_data = get_latest_sessions()

# Get events DataFrame
events_df = session_data["events"]
latest_completed_idx = session_data["latest_completed_index"]

# Get next session info
next_session_name = session_data["next_session_name"]
next_session_time = session_data["next_session_time"]

# Determine which event to display for Location/Date
# If next session exists and is in the future, show that event's location
# Otherwise show latest completed event
now = pd.Timestamp.now(tz="UTC")

if pd.notna(next_session_time) and next_session_time > now:
    # Find which event the next session belongs to
    display_event = None
    for idx, event in events_df.iterrows():
        session_cols = ["Session1DateUtc", "Session2DateUtc", "Session3DateUtc", 
                       "Session4DateUtc", "Session5DateUtc"]
        for col in session_cols:
            if pd.notna(event.get(col)) and event[col] == next_session_time:
                display_event = event
                break
        if display_event is not None:
            break
    
    # Fallback to latest completed if not found
    if display_event is None:
        display_event = events_df.iloc[latest_completed_idx]
else:
    # No upcoming session, show latest completed
    display_event = events_df.iloc[latest_completed_idx]

event_long = display_event["EventName"]
location = display_event["Location"]
country = display_event["Country"]
event_date = display_event["EventDate"]
season_year = int(str(event_date)[:4])
event_key = display_event["OfficialEventName"]

# ------------------------------------
# TOP SECTION
# ------------------------------------
st.markdown("<h2 class='section-title'>Latest Grand Prix</h2>", unsafe_allow_html=True)

col1, col2 = st.columns([2, 1])

with col1:
    st.markdown(f"<h3>{event_long}</h3>", unsafe_allow_html=True)
    st.markdown(f"""
        <div class="card">
            <div class="card-title">Location</div>
            <div class="card-value">{location}, {country}</div>
        </div>
        <div class="card">
            <div class="card-title">Event Date</div>
            <div class="card-value">{pd.to_datetime(event_date).strftime('%d %B %Y')}</div>
        </div>
    """ , unsafe_allow_html=True)

with col2:
    st.markdown("<h3>Next session</h3>", unsafe_allow_html=True)
    st.markdown(f"""
        <div class="card">
            <div class="card-title">Type</div>
            <div class="card-value">{next_session_name}</div>
        </div>
    """, unsafe_allow_html=True)

# ------------------------------------
# RESULTS SECTION WITH NAVIGATION
# ------------------------------------

# Initialize session state for event navigation
if "event_index" not in st.session_state:
    st.session_state.event_index = 0

# Get all events for the season
all_events = fastf1.get_event_schedule(season_year)
now = pd.Timestamp.now(tz="UTC")

# Normalize dates
for col in ["Session1DateUtc", "Session2DateUtc", "Session3DateUtc", 
            "Session4DateUtc", "Session5DateUtc"]:
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
    # Find the latest completed event (default)
    latest_completed_idx = 0
    for i, event in enumerate(started_events):
        # Check if last session is in the past
        last_session_date = None
        for col in ["Session5DateUtc", "Session4DateUtc", "Session3DateUtc", 
                    "Session2DateUtc", "Session1DateUtc"]:
            if pd.notna(event.get(col)):
                last_session_date = event[col]
                break
        
        if last_session_date and last_session_date < now:
            latest_completed_idx = i

    # Set default to latest completed event (only on first load)
    if "event_index_initialized" not in st.session_state:
        st.session_state.event_index = latest_completed_idx
        st.session_state.event_index_initialized = True

    # Clamp index to valid range
    st.session_state.event_index = max(0, min(st.session_state.event_index, len(started_events) - 1))

    # Get current event to display
    current_display_event = started_events[st.session_state.event_index]
    display_event_name = current_display_event["EventName"]
    display_event_key = current_display_event["OfficialEventName"]

    # Navigation buttons
    st.markdown("<h2 class='section-title' style='text-align: center;'>Current Event Results</h2>", unsafe_allow_html=True)
    
    col_nav1, col_nav2, col_nav3 = st.columns([1, 3, 1])
    
    with col_nav1:
        if st.button("←", key="prev_event", disabled=(st.session_state.event_index <= 0)):
            st.session_state.event_index -= 1
            st.rerun()
    
    with col_nav2:
        st.markdown(f"<h3 style='text-align: center;'>‹ {display_event_name} Results ›</h3>", unsafe_allow_html=True)
    
    with col_nav3:
        if st.button("→", key="next_event", disabled=(st.session_state.event_index >= len(started_events) - 1)):
            st.session_state.event_index += 1
            st.rerun()

    # Load results for selected event
    display_results = load_event_results(season_year, display_event_key)

    # Pair tables: Sprint + Sprint Quali, then Quali + Race
    pairs = [
        ("S", "Sprint", "SQ", "Sprint Qualifying"),
        ("Q", "Qualifying", "R", "Race")
    ]

    for left_key, left_title, right_key, right_title in pairs:
        colA, colB = st.columns([1, 1], gap="medium")

        with colA:
            st.markdown(render_f1_table(display_results.get(left_key), left_title), unsafe_allow_html=True)
        with colB:
            st.markdown(render_f1_table(display_results.get(right_key), right_title), unsafe_allow_html=True)

# ------------------------------------
# COUNTDOWN SECTION
# ------------------------------------
import time

st.markdown("<h2 class='section-title'>Next Session Countdown</h2>", unsafe_allow_html=True)

countdown_box = st.empty()

def render_countdown():
    if next_session_time is None or pd.isna(next_session_time):
        countdown_box.markdown("""
            <div class="card">
                <div class="card-title">Time until next session</div>
                <div class="card-value">n/a</div>
            </div>
        """, unsafe_allow_html=True)
        return

    now = pd.Timestamp.now(tz="UTC")
    delta = next_session_time - now

    if delta.total_seconds() <= 0:
        countdown_text = "Session in progress"
    else:
        total = int(delta.total_seconds())
        hrs = total // 3600
        mins = (total % 3600) // 60
        secs = total % 60
        countdown_text = f"{hrs:02d}h {mins:02d}m {secs:02d}s"

    countdown_box.markdown(
        f"""
        <div class="card">
            <div class="card-title">Time until next session</div>
            <div class="card-value">{countdown_text}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


# Live ticking countdown
while True:
    render_countdown()
    time.sleep(1)