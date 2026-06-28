import pandas as pd

from src.data.latest_session import get_latest_sessions, get_season_results
from src.infrastructure.fastf1 import get_event_schedule
from src.models import HomeContextPayload, SeasonResultsPayload

_SESSION_COLS = [
    "Session1DateUtc",
    "Session2DateUtc",
    "Session3DateUtc",
    "Session4DateUtc",
    "Session5DateUtc",
]

_SESSION_FIELDS = [
    ("Session1", "Session1DateUtc"),
    ("Session2", "Session2DateUtc"),
    ("Session3", "Session3DateUtc"),
    ("Session4", "Session4DateUtc"),
    ("Session5", "Session5DateUtc"),
]

_RACE_SESSION_DURATION = pd.Timedelta(hours=4)
_STANDARD_SESSION_DURATION = pd.Timedelta(hours=2)


def load_event_results(year: int, event_key: str) -> SeasonResultsPayload:
    return get_season_results(year, event_key)


def get_home_context(year: int | None = None) -> HomeContextPayload:
    session_data = get_latest_sessions(year)

    events_df = session_data.events
    latest_completed_idx = session_data.latest_completed_index
    next_session_name = session_data.next_session_name
    next_session_time = session_data.next_session_time
    now = pd.Timestamp.now(tz="UTC")

    display_event = determine_display_event(
        events_df=events_df,
        latest_completed_idx=latest_completed_idx,
        next_session_time=next_session_time,
        now=now,
    )

    active_session = find_session_in_progress(display_event, now)
    if active_session is not None:
        next_session_name, next_session_time = active_session

    event_date = display_event["EventDate"]
    season_year = int(pd.Timestamp(event_date).year)

    return HomeContextPayload(
        events_df=events_df,
        latest_completed_idx=latest_completed_idx,
        next_session_name=next_session_name,
        next_session_time=next_session_time,
        display_event=display_event,
        season_year=season_year,
        event_key=display_event["OfficialEventName"],
    )


def get_season_started_events(season_year: int) -> list:
    all_events = get_event_schedule(season_year, include_testing=False).copy()

    now = pd.Timestamp.now(tz="UTC")

    for col in _SESSION_COLS:
        if col in all_events.columns:
            all_events[col] = pd.to_datetime(all_events[col], utc=True)

    started_events = []
    for _, event in all_events.iterrows():
        if pd.notna(event.get("Session1DateUtc")) and event["Session1DateUtc"] < now:
            started_events.append(event)

    return started_events


def determine_display_event(
    events_df,
    latest_completed_idx: int,
    next_session_time,
    now: pd.Timestamp | None = None,
):
    now = now or pd.Timestamp.now(tz="UTC")

    active_event = find_event_in_progress(events_df, now)
    if active_event is not None:
        return active_event

    if pd.notna(next_session_time) and next_session_time > now:
        display_event = None
        for _, event in events_df.iterrows():
            for col in _SESSION_COLS:
                if pd.notna(event.get(col)) and event[col] == next_session_time:
                    display_event = event
                    break
            if display_event is not None:
                break

        if display_event is None:
            display_event = events_df.iloc[latest_completed_idx]
        return display_event

    return events_df.iloc[latest_completed_idx]


def find_event_in_progress(events_df, now: pd.Timestamp):
    current_event = None

    for _, event in events_df.iterrows():
        windows = list(_iter_session_windows(event))
        if not windows:
            continue

        event_start = min(start for _name, start, _end in windows)
        event_end = max(end for _name, _start, end in windows)
        if event_start <= now <= event_end:
            current_event = event

    return current_event


def find_session_in_progress(event, now: pd.Timestamp) -> tuple[str, pd.Timestamp] | None:
    for session_name, start, end in _iter_session_windows(event):
        if start <= now <= end:
            return session_name, start

    return None


def _iter_session_windows(event):
    for name_col, date_col in _SESSION_FIELDS:
        session_name = event.get(name_col)
        session_start = event.get(date_col)
        if pd.isna(session_name) or pd.isna(session_start):
            continue

        start = pd.to_datetime(session_start, utc=True)
        yield str(session_name), start, start + _estimated_session_duration(session_name)


def _estimated_session_duration(session_name: str) -> pd.Timedelta:
    if "race" in str(session_name).lower():
        return _RACE_SESSION_DURATION
    return _STANDARD_SESSION_DURATION
