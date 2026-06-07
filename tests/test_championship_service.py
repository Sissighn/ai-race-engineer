import pandas as pd
from types import SimpleNamespace

from src.application.championship_service import calculate_championship_standings


def test_calculate_championship_standings_returns_empty_when_no_schedule(monkeypatch):
    monkeypatch.setattr(
        "src.application.championship_service.get_event_schedule",
        lambda year, include_testing=False: pd.DataFrame(),
    )

    payload = calculate_championship_standings(2025)

    assert payload.drivers_df.empty
    assert payload.constructors_df.empty
    assert payload.events_count == 0
    assert payload.sessions_loaded == 0


def test_calculate_championship_standings_aggregates_sprint_and_race_points(
    monkeypatch,
):
    schedule = pd.DataFrame(
        [
            {
                "OfficialEventName": "TEST GRAND PRIX 2025",
                "EventName": "Test Grand Prix",
                "Session3": "Sprint",
                "Session3DateUtc": "2025-06-01T12:00:00Z",
                "Session5": "Race",
                "Session5DateUtc": "2025-06-02T12:00:00Z",
            }
        ]
    )

    def fake_get_event_schedule(year, include_testing=False):
        return schedule

    def fake_session_factory(year, event_key, session_type):
        if session_type == "R":
            results = pd.DataFrame(
                {
                    "Position": [1, 2],
                    "Abbreviation": ["VER", "HAM"],
                    "DriverNumber": [1, 44],
                    "TeamName": ["Red Bull", "Mercedes"],
                    "Time": ["1:30.000", "1:31.000"],
                    "Status": ["Finished", "Finished"],
                    "Points": [25.0, 18.0],
                    "FullName": ["Max Verstappen", "Lewis Hamilton"],
                }
            )
        else:
            results = pd.DataFrame(
                {
                    "Position": [1],
                    "Abbreviation": ["HAM"],
                    "DriverNumber": [44],
                    "TeamName": ["Mercedes"],
                    "Time": ["1:25.000"],
                    "Status": ["Finished"],
                    "Points": [8.0],
                    "FullName": ["Lewis Hamilton"],
                }
            )

        return SimpleNamespace(load=lambda **kwargs: None, results=results)

    monkeypatch.setattr(
        "src.application.championship_service.get_event_schedule",
        fake_get_event_schedule,
    )
    monkeypatch.setattr(
        "src.application.championship_service.get_session",
        fake_session_factory,
    )

    payload = calculate_championship_standings(2025)

    assert payload.drivers_df.iloc[0]["DriverName"] == "Lewis Hamilton"
    assert payload.drivers_df.iloc[0]["Points"] == 26.0
    assert payload.drivers_df.iloc[1]["DriverName"] == "Max Verstappen"
    assert payload.drivers_df.iloc[1]["Points"] == 25.0
    assert payload.constructors_df.iloc[0]["Team"] == "Mercedes"
    assert payload.constructors_df.iloc[0]["Points"] == 26.0
    assert payload.events_count == 1
    assert payload.sessions_loaded == 2
