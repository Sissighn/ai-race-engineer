import html as html_module
import re

import pandas as pd

from src.logging import get_logger

logger = get_logger(__name__)


def clean_position(num):
    try:
        return int(float(num))
    except Exception:
        return num


# Convert F1 time format
def format_f1_time(raw):
    """
    Convert '0 days 00:25:09.054000' → '25:09.054'
    """
    text = str(raw)

    match = re.search(r"(\d+ days )?(\d+):(\d+):(\d+\.\d+)", text)
    if not match:
        return text

    hours = int(match.group(2))
    mins = int(match.group(3))
    secs = float(match.group(4))

    total_mins = hours * 60 + mins
    return f"{total_mins}:{secs:06.3f}"


def render_f1_table(df, title: str) -> str:
    """
    Render a DataFrame as an HTML table wrapped in the GlowCard structure.

    Uses 'glow-large' class for better visibility on big elements.
    Title is HTML-escaped to prevent injection.

    Args:
        df: DataFrame to render, or None for empty state.
        title: Human-readable title for the table card.

    Returns:
        HTML string ready for st.markdown(unsafe_allow_html=True).
    """
    safe_title = html_module.escape(str(title))
    # 1. Handle Empty State
    if df is None or df.empty:
        logger.info("No data for F1 table", title=title)
        return f"""
        <div class="glow-card-wrapper glow-large" style="max-width: 900px; margin: 10px auto;">
            <div class="glow-card-content">
                <h3 style="margin-top:0;">{safe_title}</h3>
                <p style="color:#AAA;">No data yet.</p>
            </div>
        </div>
        """

    df = df.copy()

    # 2. Clean Data (Same as before)
    drop_cols = ["Status", "Session", "EventName", "Event", "Season", "Milliseconds"]
    for c in drop_cols:
        if c in df.columns:
            df = df.drop(columns=c)

    if "Position" in df.columns:
        df["Position"] = df["Position"].apply(clean_position)

    if "Time" in df.columns:
        df["Time"] = df["Time"].apply(format_f1_time)

    # 3. Create HTML Table
    try:
        html_table = df.to_html(index=False, classes="compact", border=0)
    except Exception as e:
        logger.error(
            "Failed to convert results dataframe to HTML", title=title, error=str(e)
        )
        return f"""
        <div class="glow-card-wrapper glow-large" style="max-width: 900px; margin: 10px auto;">
            <div class="glow-card-content">
                <h3 style="margin-top:0;">{safe_title}</h3>
                <p style="color:#AAA;">Could not render table.</p>
            </div>
        </div>
        """

    # 4. Wrap with GLOW-LARGE
    return f"""
    <div class="glow-card-wrapper glow-large" style="width: 100%; max-width: 900px; margin: 10px auto;">
        <div class="glow-card-content" style="padding: 20px;">
            <h3 style="margin-top:0; margin-bottom: 15px;">{safe_title}</h3>
            <div class="table-responsive">
                {html_table}
            </div>
        </div>
    </div>
    """
