import pandas as pd

from src.application.home_service import (
    determine_display_event,
    find_session_in_progress,
)


def _event(name: str, session1: str, session5: str) -> dict:
    return {
        "OfficialEventName": name,
        "EventName": name,
        "Country": "Test",
        "Location": "Test",
        "EventDate": session5,
        "Session1": "Practice 1",
        "Session2": "Practice 2",
        "Session3": "Practice 3",
        "Session4": "Qualifying",
        "Session5": "Race",
        "Session1DateUtc": pd.Timestamp(session1, tz="UTC"),
        "Session2DateUtc": pd.Timestamp(session1, tz="UTC") + pd.Timedelta(hours=4),
        "Session3DateUtc": pd.Timestamp(session5, tz="UTC") - pd.Timedelta(days=1),
        "Session4DateUtc": pd.Timestamp(session5, tz="UTC") - pd.Timedelta(hours=23),
        "Session5DateUtc": pd.Timestamp(session5, tz="UTC"),
    }


def test_determine_display_event_keeps_race_weekend_current_during_race():
    events = pd.DataFrame(
        [
            _event("Canadian Grand Prix", "2026-05-22 11:30", "2026-05-24 13:00"),
            _event("Monaco Grand Prix", "2026-06-05 11:30", "2026-06-07 13:00"),
            _event("Spanish Grand Prix", "2026-06-12 11:30", "2026-06-14 13:00"),
        ]
    )

    display_event = determine_display_event(
        events_df=events,
        latest_completed_idx=0,
        next_session_time=pd.Timestamp("2026-06-12 11:30", tz="UTC"),
        now=pd.Timestamp("2026-06-07 13:30", tz="UTC"),
    )

    assert display_event["OfficialEventName"] == "Monaco Grand Prix"


def test_determine_display_event_switches_after_race_window_ends():
    events = pd.DataFrame(
        [
            _event("Canadian Grand Prix", "2026-05-22 11:30", "2026-05-24 13:00"),
            _event("Monaco Grand Prix", "2026-06-05 11:30", "2026-06-07 13:00"),
            _event("Spanish Grand Prix", "2026-06-12 11:30", "2026-06-14 13:00"),
        ]
    )

    display_event = determine_display_event(
        events_df=events,
        latest_completed_idx=1,
        next_session_time=pd.Timestamp("2026-06-12 11:30", tz="UTC"),
        now=pd.Timestamp("2026-06-07 17:30", tz="UTC"),
    )

    assert display_event["OfficialEventName"] == "Spanish Grand Prix"


def test_find_session_in_progress_reports_race_until_estimated_end():
    event = pd.Series(_event("Monaco Grand Prix", "2026-06-05 11:30", "2026-06-07 13:00"))

    active_session = find_session_in_progress(
        event,
        pd.Timestamp("2026-06-07 13:30", tz="UTC"),
    )

    assert active_session == ("Race", pd.Timestamp("2026-06-07 13:00", tz="UTC"))
