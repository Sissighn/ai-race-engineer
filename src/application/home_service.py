from typing import Optional

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


def load_event_results(year: int, event_key: str) -> SeasonResultsPayload:
    return get_season_results(year, event_key)


def get_home_context(year: Optional[int] = None) -> HomeContextPayload:
    session_data = get_latest_sessions(year)

    events_df = session_data.events
    latest_completed_idx = session_data.latest_completed_index
    next_session_name = session_data.next_session_name
    next_session_time = session_data.next_session_time

    display_event = determine_display_event(
        events_df=events_df,
        latest_completed_idx=latest_completed_idx,
        next_session_time=next_session_time,
    )

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


def determine_display_event(events_df, latest_completed_idx: int, next_session_time):
    now = pd.Timestamp.now(tz="UTC")

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
