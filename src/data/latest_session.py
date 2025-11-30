import fastf1
import pandas as pd


# ---------------------------------------------------------
# LATEST EVENT + NEXT SESSION
# ---------------------------------------------------------
def get_latest_sessions(year: int | None = None) -> pd.DataFrame:
    """
    Returns a 1-row DataFrame with:
      - latest completed Grand Prix meta info
      - next upcoming session (name + datetime)
    """

    # Auto-detect current year if not provided
    if year is None:
        year = pd.Timestamp.now().year

    # Full F1 calendar for the season
    events = fastf1.get_event_schedule(year)

    # Current time (UTC)
    now = pd.Timestamp.now(tz="UTC")

    # Normalize date formats
    events["Session1DateUtc"] = pd.to_datetime(events["Session1DateUtc"], utc=True)

    # Past vs future events based on FP1 start
    past_events = events[events["Session1DateUtc"] < now]
    future_events = events[events["Session1DateUtc"] >= now]

    if past_events.empty:
        raise ValueError("No completed events yet in this season.")

    latest = past_events.iloc[-1]

    # ---------------------------
    # Find next session inside this GP
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

    # If the whole GP is finished, move to next event
    if next_name is None:
        if not future_events.empty:
            nxt = future_events.iloc[0]
            next_name = nxt["Session1"]
            next_time = pd.to_datetime(nxt["Session1DateUtc"], utc=True)
        else:
            next_name = "Season Finished"
            next_time = pd.NaT

    return pd.DataFrame({
        "OfficialEventName": [latest["OfficialEventName"]],
        "EventName": [latest["EventName"]],
        "Country": [latest["Country"]],
        "Location": [latest["Location"]],
        "EventDate": [latest["EventDate"]],
        "NextSession": [next_name],
        "NextSessionDate": [next_time],
        "Year": [year],
    })


# ---------------------------------------------------------
# SESSION RESULTS HELPERS
# ---------------------------------------------------------
def load_single_session_results(year: int, event_key: str, session_type: str) -> pd.DataFrame | None:
    """
    Loads official FIA results for a given session type of a given event.

    session_type:
        - 'Q'  = Qualifying
        - 'R'  = Race
        - 'S'  = Sprint
        - 'SQ' = Sprint Shootout

    Returns a cleaned DataFrame or None if session is unavailable.
    """
    try:
        # event_key is expected to match OfficialEventName from the calendar
        session = fastf1.get_session(year, event_key, session_type)
        session.load()
    except Exception:
        # If FastF1 cannot find / load this session, just report "no data"
        return None

    if session.results is None or session.results.empty:
        return None

    df = session.results.copy()

    # Graceful handling in case some columns are missing
    cols_available = df.columns
    keep_cols = [c for c in [
        "Position",
        "Abbreviation",
        "DriverNumber",
        "TeamName",
        "Time",
        "Status",
    ] if c in cols_available]

    df = df[keep_cols].copy()

    # Add metadata columns
    df["Session"] = session_type
    df["Event"] = event_key

    # Sort by Position if present
    if "Position" in df.columns:
        df = df.sort_values("Position")

    return df.reset_index(drop=True)


def get_season_results(year: int, event_key: str) -> dict[str, pd.DataFrame | None]:
    """
    Returns a dict of DataFrames for one event (GP):

        {
            "Q":  <Qualifying df or None>,
            "SQ": <Sprint Shootout df or None>,
            "S":  <Sprint df or None>,
            "R":  <Race df or None>,
        }
    """
    return {
        "Q":  load_single_session_results(year, event_key, "Q"),
        "SQ": load_single_session_results(year, event_key, "SQ"),
        "S":  load_single_session_results(year, event_key, "S"),
        "R":  load_single_session_results(year, event_key, "R"),
    }
