import fastf1
import pandas as pd
from typing import Optional

from src.logging import get_logger
from src.models import LatestSessionsPayload, SeasonResultsPayload

logger = get_logger(__name__)


def get_latest_sessions(year: Optional[int] = None) -> LatestSessionsPayload:
    """
    Returns complete event data for navigation and next session info.

    Args:
        year: F1 season year. If None, uses current year.

    Returns:
        {
            "events": DataFrame with all events (indexed),
            "latest_completed_index": int (index of last completed event),
            "next_session_name": str,
            "next_session_time": datetime or NaT,
            "next_event_index": int or None (index of event with next session),
        }

    Raises:
        ValueError: If no events found in schedule
    """

    # Auto-detect current year if not provided
    if year is None:
        year = pd.Timestamp.now().year

    logger.info("Loading F1 schedule", year=year)

    try:
        # Full F1 calendar for the season (exclude pre-season testing)
        events = fastf1.get_event_schedule(year, include_testing=False)
    except Exception as e:
        logger.error("Failed to load event schedule", year=year, error=str(e))
        raise ValueError(f"Could not load F1 schedule for {year}: {e}")

    if events is None or events.empty:
        raise ValueError(f"No events found in F1 schedule for {year}")

    # Current time (UTC)
    now = pd.Timestamp.now(tz="UTC")

    # Normalize all session date columns
    session_cols = [
        "Session1DateUtc",
        "Session2DateUtc",
        "Session3DateUtc",
        "Session4DateUtc",
        "Session5DateUtc",
    ]

    for col in session_cols:
        if col in events.columns:
            events[col] = pd.to_datetime(events[col], utc=True, errors="coerce")
        else:
            logger.warning("Column not found in events DataFrame", column=col)

    # Calculate LastSessionDateUtc (max of all sessions)
    available_session_cols = [col for col in session_cols if col in events.columns]
    if available_session_cols:
        events["LastSessionDateUtc"] = events[available_session_cols].max(axis=1)
    else:
        logger.error("No session date columns found")
        events["LastSessionDateUtc"] = pd.NaT

    # Add EventIndex
    events = events.reset_index(drop=True)
    events["EventIndex"] = events.index

    # Keep only relevant columns
    keep_cols = [
        "EventIndex",
        "OfficialEventName",
        "EventName",
        "Country",
        "Location",
        "EventDate",
        "Session1",
        "Session2",
        "Session3",
        "Session4",
        "Session5",
        "Session1DateUtc",
        "Session2DateUtc",
        "Session3DateUtc",
        "Session4DateUtc",
        "Session5DateUtc",
        "LastSessionDateUtc",
    ]

    keep_cols = [c for c in keep_cols if c in events.columns]
    events = events[keep_cols].copy()

    # ---------------------------
    # Find latest completed event
    # ---------------------------
    latest_completed_index = 0

    for idx, event in events.iterrows():
        last_session = event.get("LastSessionDateUtc")
        if pd.notna(last_session) and last_session < now:
            latest_completed_index = int(idx)

    logger.info("Latest completed event index", index=latest_completed_index)

    # ---------------------------
    # Find next session (across all events)
    # ---------------------------
    next_session_name = "Season Finished"
    next_session_time = pd.NaT
    next_event_index = None

    session_fields = [
        ("Session1", "Session1DateUtc"),
        ("Session2", "Session2DateUtc"),
        ("Session3", "Session3DateUtc"),
        ("Session4", "Session4DateUtc"),
        ("Session5", "Session5DateUtc"),
    ]

    # Find earliest future session across all events
    all_future_sessions = []

    for idx, event in events.iterrows():
        for label_col, date_col in session_fields:
            if date_col not in events.columns or label_col not in events.columns:
                continue

            session_date = event.get(date_col)
            session_name = event.get(label_col)

            if pd.notna(session_date) and pd.notna(session_name):
                if session_date > now:
                    all_future_sessions.append(
                        {
                            "name": session_name,
                            "time": session_date,
                            "event_index": int(idx),
                        }
                    )

    # Get the earliest future session
    if all_future_sessions:
        earliest = min(all_future_sessions, key=lambda x: x["time"])
        next_session_name = earliest["name"]
        next_session_time = earliest["time"]
        next_event_index = earliest["event_index"]
        logger.info(
            "Next session found", name=next_session_name, time=str(next_session_time)
        )
    else:
        logger.info("No future sessions found - season finished")

    return LatestSessionsPayload(
        events=events,
        latest_completed_index=latest_completed_index,
        next_session_name=str(next_session_name),
        next_session_time=next_session_time,
        next_event_index=next_event_index,
    )


def load_single_session_results(
    year: int, event_key: str, session_type: str
) -> Optional[pd.DataFrame]:
    """
    Loads official FIA results for a given session type of a given event.

    Args:
        year: F1 season year
        event_key: OfficialEventName from the calendar
        session_type: 'Q', 'R', 'S', or 'SQ'

    Returns:
        DataFrame with session results or None if session is unavailable.
    """

    # Validate session type
    valid_sessions = ["Q", "R", "S", "SQ", "FP1", "FP2", "FP3"]
    if session_type not in valid_sessions:
        logger.warning("Invalid session type", session_type=session_type)
        return None

    try:
        logger.info(
            "Loading session results",
            session_type=session_type,
            event_key=event_key,
            year=year,
        )
        session = fastf1.get_session(year, event_key, session_type)
        session.load()
    except Exception as e:
        logger.warning(
            "Failed to load session",
            session_type=session_type,
            event_key=event_key,
            error=str(e),
        )
        return None

    if session.results is None or session.results.empty:
        logger.info(
            "No results available", session_type=session_type, event_key=event_key
        )
        return None

    try:
        df = session.results.copy()

        cols_available = df.columns.tolist()
        keep_cols = [
            c
            for c in [
                "Position",
                "Abbreviation",
                "DriverNumber",
                "TeamName",
                "Time",
                "Status",
            ]
            if c in cols_available
        ]

        if not keep_cols:
            logger.warning(
                "No expected columns found in results",
                event_key=event_key,
                session_type=session_type,
            )
            return None

        df = df[keep_cols].copy()

        # Add metadata columns
        df["Session"] = session_type
        df["Event"] = event_key

        # Sort by Position if present
        if "Position" in df.columns:
            # Convert Position to numeric, handling DNF, DSQ, etc.
            df["Position"] = pd.to_numeric(df["Position"], errors="coerce")
            df = df.sort_values("Position")

        logger.info(
            "Successfully loaded results",
            count=len(df),
            session_type=session_type,
            event_key=event_key,
        )
        return df.reset_index(drop=True)

    except Exception as e:
        logger.error(
            "Error processing results",
            event_key=event_key,
            session_type=session_type,
            error=str(e),
        )
        return None


def get_season_results(year: int, event_key: str) -> SeasonResultsPayload:
    """
    Returns a dict of DataFrames for one event (GP).

    Args:
        year: F1 season year
        event_key: OfficialEventName from the calendar

    Returns:
        {
            "Q":  Qualifying DataFrame or None,
            "SQ": Sprint Shootout DataFrame or None,
            "S":  Sprint DataFrame or None,
            "R":  Race DataFrame or None,
        }
    """

    if not isinstance(year, int) or year < 1950 or year > 2100:
        logger.error("Invalid year", year=year)
        return SeasonResultsPayload()

    if not event_key or not isinstance(event_key, str):
        logger.error("Invalid event_key", event_key=event_key)
        return SeasonResultsPayload()

    logger.info("Loading all session results", event_key=event_key, year=year)

    results = {
        "Q": load_single_session_results(year, event_key, "Q"),
        "SQ": load_single_session_results(year, event_key, "SQ"),
        "S": load_single_session_results(year, event_key, "S"),
        "R": load_single_session_results(year, event_key, "R"),
    }

    loaded_sessions = [k for k, v in results.items() if v is not None]
    logger.info("Loaded sessions", event_key=event_key, sessions=loaded_sessions)

    return SeasonResultsPayload(
        Q=results["Q"],
        SQ=results["SQ"],
        S=results["S"],
        R=results["R"],
    )
