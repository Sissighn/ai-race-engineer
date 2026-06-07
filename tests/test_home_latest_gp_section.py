import pandas as pd

from app.pages.home.latest_gp_section import _format_weekend_range, build_weekend_sessions


def test_build_weekend_sessions_formats_all_sessions_in_local_time():
    event = pd.Series(
        {
            "EventName": "Monaco Grand Prix",
            "Country": "Monaco",
            "Location": "Monte Carlo",
            "EventDate": "2026-06-07",
            "Session1": "Practice 1",
            "Session2": "Practice 2",
            "Session3": "Practice 3",
            "Session4": "Qualifying",
            "Session5": "Race",
            "Session1DateUtc": "2026-06-05T11:30:00Z",
            "Session2DateUtc": "2026-06-05T15:00:00Z",
            "Session3DateUtc": "2026-06-06T10:30:00Z",
            "Session4DateUtc": "2026-06-06T14:00:00Z",
            "Session5DateUtc": "2026-06-07T13:00:00Z",
        }
    )

    sessions = build_weekend_sessions(
        event,
        next_session_time=pd.Timestamp("2026-06-06T14:00:00Z"),
    )

    assert [session["name"] for session in sessions] == [
        "Practice 1",
        "Practice 2",
        "Practice 3",
        "Qualifying",
        "Race",
    ]
    assert sessions[0]["day"] == "Friday"
    assert sessions[0]["time"] == "13:30"
    assert sessions[3]["status"] == "next"
    assert sessions[4]["date"] == "07 Jun"
    assert _format_weekend_range(event) == "05-07 June 2026"
