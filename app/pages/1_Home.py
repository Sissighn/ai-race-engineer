import streamlit as st
import pandas as pd
import sys
import os
import re

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
sessions = get_latest_sessions()

event_long = sessions["EventName"].iloc[0]
location = sessions["Location"].iloc[0]
country = sessions["Country"].iloc[0]
event_date = sessions["EventDate"].iloc[0]
season_year = int(str(event_date)[:4])
event_key = sessions["OfficialEventName"].iloc[0]

next_session_name = sessions["NextSession"].iloc[0]
next_session_time = sessions["NextSessionDate"].iloc[0]


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
# RESULTS SECTION
# ------------------------------------
st.markdown("<h2 class='section-title'>Current Event Results</h2>", unsafe_allow_html=True)

results = load_event_results(season_year, event_key)

# Pair tables: Sprint + Sprint Quali, then Quali + Race
pairs = [
    ("S", "Sprint", "SQ", "Sprint Qualifying"),
    ("Q", "Qualifying", "R", "Race")
]

for left_key, left_title, right_key, right_title in pairs:
    colA, colB = st.columns([1, 1], gap="medium")

    with colA:
        st.markdown(render_f1_table(results.get(left_key), left_title), unsafe_allow_html=True)
    with colB:
        st.markdown(render_f1_table(results.get(right_key), right_title), unsafe_allow_html=True)

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