import fastf1
import pandas as pd


def get_latest_sessions(year=None):
    """
    Returns info about:
      - the latest completed Grand Prix
      - the next upcoming session
    """

    # Auto detect current year if not provided
    if year is None:
        year = pd.Timestamp.now().year

    # Load calendar
    events = fastf1.get_event_schedule(year)

    # Today in UTC
    now = pd.Timestamp.now(tz="UTC")

    # Normalize date formats
    events["Session1DateUtc"] = pd.to_datetime(events["Session1DateUtc"], utc=True)

    # Past vs future events
    past_events = events[events["Session1DateUtc"] < now]
    future_events = events[events["Session1DateUtc"] >= now]

    if past_events.empty:
        raise ValueError("No completed events yet.")

    latest = past_events.iloc[-1]

    # ---------------------------
    # Find next session inside GP
    # ---------------------------
    session_fields = [
        ("Session1", "Session1DateUtc"),
        ("Session2", "Session2DateUtc"),
        ("Session3", "Session3DateUtc"),
        ("Session4", "Session4DateUtc"),
        ("Session5", "Session5DateUtc"),
    ]

    next_name = None
    next_time = None

    for label, date_col in session_fields:
        if date_col not in events.columns:
            continue

        dt = latest.get(date_col, None)
        if pd.notna(dt):
            dt = pd.to_datetime(dt, utc=True)
            if dt > now:
                next_name = latest[label]
                next_time = dt
                break

    # If GP is finished → go to next GP
    if next_name is None:
        if not future_events.empty:
            nxt = future_events.iloc[0]
            next_name = nxt["Session1"]
            next_time = pd.to_datetime(nxt["Session1DateUtc"], utc=True)
        else:
            next_name = "Season Finished"
            next_time = pd.NaT

    # Build result frame
    return pd.DataFrame({
        "OfficialEventName": [latest["OfficialEventName"]],
        "EventName": [latest["EventName"]],
        "Country": [latest["Country"]],
        "Location": [latest["Location"]],
        "EventDate": [latest["EventDate"]],
        "NextSession": [next_name],
        "NextSessionDate": [next_time],
        "Year": [year]
    })
