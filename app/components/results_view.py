import pandas as pd
import re

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
    """
    Renders a dataframe as an HTML table wrapped in the 
    GlowCard structure. Uses 'glow-large' for better visibility on big elements.
    """
    # 1. Handle Empty State
    if df is None or df.empty:
        # ADDED CLASS: glow-large
        return f"""
        <div class="glow-card-wrapper glow-large" style="max-width: 900px; margin: 10px auto;">
            <div class="glow-card-content">
                <h3 style="margin-top:0;">{title}</h3>
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
    html_table = df.to_html(
        index=False,
        classes="compact",
        border=0
    )

    # 4. Wrap with GLOW-LARGE
    # ADDED CLASS: glow-large
    return f"""
    <div class="glow-card-wrapper glow-large" style="width: 100%; max-width: 900px; margin: 10px auto;">
        <div class="glow-card-content" style="padding: 20px;">
            <h3 style="margin-top:0; margin-bottom: 15px;">{title}</h3>
            <div class="table-responsive">
                {html_table}
            </div>
        </div>
    </div>
    """
