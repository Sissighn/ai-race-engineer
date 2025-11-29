import streamlit as st
import pandas as pd
import time
import sys
import os

# ---- Fix path ----
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.data.latest_session import get_latest_sessions
from app.components.navbar import navbar

# -------------------------------
# PAGE CONFIG
# -------------------------------
st.set_page_config(
    page_title="AI Race Engineer – Home",
    layout="wide",
)
st.markdown("""
<style>
[data-testid="stSidebar"] { display: none; }
[data-testid="stSidebarNav"] { display: none; }
[data-testid="stSidebarUserContent"] { display: none; }
[data-testid="collapsedControl"] { display: none; }
</style>
""", unsafe_allow_html=True)

navbar()
# -------------------------------
# LOAD FONTS + GLOBAL STYLE
# -------------------------------
st.markdown("""
<style>

/* IMPORT ALL FONTS */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Poppins:wght@600;700;800&family=Science+Gothic:wght@100..900&display=swap');

/* BODY FONT */
html, body, [class*="block-container"] {
    font-family: 'Inter', sans-serif;
}

/* SECTION TITLES */
h2, h3, h4 {
    font-family: 'Poppins', sans-serif !important;
    font-weight: 700 !important;
}

/* PAGE TITLE FONT (Science Gothic) */
.science-gothic {
    font-family: "Science Gothic", sans-serif !important;
    font-weight: 700 !important;
    font-style: normal;
    font-optical-sizing: auto;
    font-variation-settings:
        "slnt" 0,
        "wdth" 100,
        "CTRS" 0;
    letter-spacing: -0.5px;
}

/* SECTION HEADER */
.section-title {
    font-size: 1.6rem;
    font-weight: 700;
    margin-top: 1.4rem;
    color: #403075;
}

/* CARD STYLE */
.card {
    background: #FFFFFF;
    border-radius: 18px;
    padding: 22px 26px;
    border: 1px solid #EDE7FF;
    margin-bottom: 18px;
}

/* TITLE INSIDE A CARD */
.card-title {
    font-size: 0.9rem;
    font-weight: 600;
    color: #6A5ACD;
    margin-bottom: 6px;
}

/* MAIN VALUE */
.card-value {
    font-size: 1.7rem;
    font-weight: 700;
    color: #4636C5;
    margin-bottom: 4px;
}

</style>
""", unsafe_allow_html=True)


# -------------------------------
# HEADER
# -------------------------------
st.write("")

st.markdown(
    "<h1 class='science-gothic'>AI Race Engineer – Live F1 Insights</h1>",
    unsafe_allow_html=True
)

# -------------------------------
# LOAD LATEST EVENT
# -------------------------------
try:
    sessions = get_latest_sessions()

    event_long = sessions["EventName"].iloc[0]
    location = sessions["Location"].iloc[0]
    country = sessions["Country"].iloc[0]
    event_date = sessions["EventDate"].iloc[0]
    season_year = int(str(event_date)[:4])

    next_session_name = sessions["NextSession"].iloc[0]
    next_session_time = sessions["NextSessionDate"].iloc[0]

    # Clean event title (keep short and clean)
    short_name = event_long.split("GRAND PRIX")[0].replace("FORMULA 1", "").replace("AIRWAYS", "").strip()
    title_final = f"{short_name} Grand Prix {season_year}"

except Exception as e:
    st.error(f"Error loading latest sessions: {e}")
    st.stop()


# -------------------------------
# EVENT SECTION
# -------------------------------
st.markdown(f"<h2 class='section-title'>Latest Grand Prix</h2>", unsafe_allow_html=True)

col1, col2 = st.columns([2, 1])

with col1:
    st.markdown(f"<h3>{title_final}</h3>", unsafe_allow_html=True)

    st.markdown(
        f"""
        <div class="card">
            <div class="card-title">Location</div>
            <div class="card-value">{location}, {country}</div>
        </div>

        <div class="card">
            <div class="card-title">Event date</div>
            <div class="card-value">{pd.to_datetime(event_date).strftime('%d %B %Y')}</div>
        </div>

        <div class="card">
            <div class="card-title">Season</div>
            <div class="card-value">{season_year}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with col2:
    st.markdown("<h3>Next session details</h3>", unsafe_allow_html=True)

    if next_session_name == "Season Ended":
        st.markdown(
            """
            <div class="card">
                <div class="card-title">Next session</div>
                <div class="card-value">Season ended</div>
            </div>
            """,
            unsafe_allow_html=True
        )
        next_session_time = None
    else:
        st.markdown(
            f"""
            <div class="card">
                <div class="card-title">Session type</div>
                <div class="card-value">{next_session_name}</div>
            </div>

            <div class="card">
                <div class="card-title">Session date</div>
                <div class="card-value">
                    {pd.to_datetime(next_session_time).strftime('%d %B %Y – %H:%M UTC')}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )


# -------------------------------
# COUNTDOWN SECTION
# -------------------------------
st.markdown("<h2 class='section-title'>Next session countdown</h2>", unsafe_allow_html=True)

countdown_box = st.empty()

if next_session_time is None:
    countdown_box.markdown(
        """
        <div class="card">
            <div class="card-title">Time until next session</div>
            <div class="card-value">n/a</div>
        </div>
        """,
        unsafe_allow_html=True
    )
else:
    now = pd.Timestamp.now(tz="UTC")
    delta = next_session_time - now

    if delta.total_seconds() <= 0:
        countdown_text = "Session in progress"
    else:
        total = int(delta.total_seconds())
        hrs = total // 3600
        mins = (total % 3600) // 60
        secs = total % 60
        countdown_text = f"{hrs}h {mins}m {secs}s"

    countdown_box.markdown(
        f"""
        <div class="card">
            <div class="card-title">Time until next session</div>
            <div class="card-value">{countdown_text}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    time.sleep(1)
    st.rerun()
