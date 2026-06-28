from pathlib import Path

import pandas as pd

from app.pages.live_timing import controller


def test_format_seconds_handles_none_and_float_values():
    assert controller._format_seconds(None) == "-"
    assert controller._format_seconds(76.732) == "1:16.732"
    assert controller._format_seconds(25.1) == "25.100"


def test_build_timing_tower_merges_positions_laps_and_drivers():
    payload = {
        "drivers": {
            1: {"name_acronym": "VER", "team_name": "Red Bull Racing"},
            44: {"name_acronym": "HAM", "team_name": "Ferrari"},
        },
        "positions": [
            {"driver_number": 44, "position": 2},
            {"driver_number": 1, "position": 1},
        ],
        "laps": [
            {
                "driver_number": 1,
                "lap_number": 12,
                "lap_duration": 76.7,
                "duration_sector_1": 25.1,
                "duration_sector_2": 31.2,
                "duration_sector_3": 20.4,
                "i1_speed": 292,
                "i2_speed": 303,
                "st_speed": 321,
            }
        ],
    }

    tower = controller._build_timing_tower(payload)

    assert isinstance(tower, pd.DataFrame)
    assert tower.iloc[0]["DRV"] == "VER"
    assert tower.iloc[0]["LAST"] == "1:16.700"
    assert tower.iloc[1]["DRV"] == "HAM"
    assert tower.iloc[1]["LAST"] == "-"


def test_payload_from_signalr_converts_snapshot_to_page_payload():
    payload = controller._payload_from_signalr(
        {
            "connected": True,
            "message_count": 4,
            "seconds_since_last_message": 0.5,
            "session": {"Name": "Monaco Grand Prix"},
            "drivers": {"1": {"driver_number": "1", "tla": "VER", "team": "Red Bull Racing"}},
            "timing": {
                "1": {
                    "position": "1",
                    "last_lap": "1:12.345",
                    "best_lap": "1:11.111",
                    "gap_to_leader": "",
                    "interval": "",
                }
            },
            "car_data": {"1": {"speed": 286}},
            "positions": {"1": {"x": 10, "y": 20}},
            "tyres": {"1": {"compound": "SOFT", "total_laps": 8}},
            "race_control": [],
        }
    )

    assert payload["source"] == "f1-signalr"
    assert payload["drivers"][1]["tla"] == "VER"
    assert payload["positions"] == [{"driver_number": 1, "position": 1}]
    assert payload["positions_xyz"]["1"]["x"] == 10
    assert payload["tyres"]["1"]["compound"] == "SOFT"
    assert payload["laps"][0]["lap_duration"] == "1:12.345"
    assert payload["service"]["connected"] is True


def test_signalr_session_helpers_use_meeting_name_for_event():
    session = {
        "Name": "Race",
        "Type": "Race",
        "Meeting": {
            "Name": "Austrian Grand Prix",
            "Location": "Spielberg",
            "Circuit": {"ShortName": "Spielberg"},
        },
    }

    assert controller._session_event_name(session) == "Austrian Grand Prix"
    assert controller._session_label(session) == "Race"
    assert controller._session_circuit_name(session) == "Spielberg"


def test_display_current_lap_uses_signalr_lap_count_without_projection():
    assert controller._display_current_lap({"CurrentLap": 29, "TotalLaps": 71}) == 29
    assert controller._display_current_lap({"CurrentLap": 71, "TotalLaps": 71}) == 71
    assert controller._display_current_lap({}) == "--"


def test_load_live_timing_payload_prefers_connected_signalr(monkeypatch):
    controller._load_live_timing_payload.clear()
    monkeypatch.setattr(
        controller,
        "get_signalr_snapshot",
        lambda: {
            "connected": True,
            "message_count": 0,
            "session": {},
            "drivers": {},
            "timing": {},
        },
    )
    monkeypatch.setattr(
        controller,
        "get_latest_session",
        lambda: (_ for _ in ()).throw(AssertionError("OpenF1 should not be called")),
    )

    payload = controller._load_live_timing_payload()

    assert payload["source"] == "f1-signalr"
    assert payload["service"]["connected"] is True
    controller._load_live_timing_payload.clear()


def test_build_classification_rows_adds_tyre_and_team_data():
    payload = {
        "drivers": {
            1: {
                "tla": "VER",
                "team": "Red Bull Racing",
                "team_colour": "4781D7",
            }
        },
        "positions": [{"driver_number": 1, "position": 1}],
        "laps": [
            {
                "driver_number": 1,
                "lap_number": 12,
                "lap_duration": "1:12.345",
                "best_lap": "1:11.111",
                "gap_to_leader": "",
                "interval": "",
            }
        ],
        "tyres": {"1": {"compound": "SOFT", "total_laps": 8}},
        "car_data": {"1": {"speed": 286}},
    }

    rows = controller._build_classification_rows(payload)

    assert rows[0]["code"] == "VER"
    assert rows[0]["team_colour"] == "#4781D7"
    assert rows[0]["tyre"] == "S"
    assert rows[0]["tyre_laps"] == 8


def test_build_classification_rows_does_not_use_global_lap_as_driver_lap():
    payload = {
        "drivers": {63: {"tla": "RUS", "team": "Mercedes"}},
        "positions": [{"driver_number": 63, "position": 1}],
        "laps": [{"driver_number": 63, "gap_to_leader": "", "interval": ""}],
        "lap_count": {"CurrentLap": 29, "TotalLaps": 71},
    }

    rows = controller._build_classification_rows(payload)

    assert rows[0]["lap"] == "-"


def test_live_timing_page_uses_client_side_polling_without_streamlit_refresh():
    source = Path(controller.__file__).read_text(encoding="utf-8")

    assert "http-equiv='refresh'" not in source
    assert 'http-equiv="refresh"' not in source
    assert "@st.fragment" not in source
    assert "st.iframe" in source
    assert "components.html" not in source
    assert "streamlit.components.v1" not in source
    assert "window.setInterval" in source
    assert "serviceUrlCandidates" in source
    assert "fetchSnapshot(url)" in source
    assert "fetch(`${{url}}/snapshot`" in source
    assert "SignalR service unavailable: ${{error.message}}" not in source


def test_build_live_timing_component_html_uses_signalr_snapshot_url():
    html = controller._build_live_timing_component_html("http://localhost:8765")

    assert "http://localhost:8765" in html
    assert "/snapshot" in html
    assert "F1 Pit Wall" in html
    assert "Race Classification" in html
    assert "Race Control" in html
    assert "State" in html
    assert "Stops" in html
    assert "runState(row, snapshot)" in html
    assert "isRedFlag(snapshot)" in html
    assert 'if (row.stopped === true) return {label: "Out", cls: "out"}' in html
    assert html.index('if (row.stopped === true) return {label: "Out", cls: "out"}') < html.index(
        'if (isRedFlag(snapshot)) return {label: "", cls: ""}'
    )
    assert "mergeDrivers(snapshot)" in html
    assert "driver?.broadcast_name" in html
    assert "tyre.pit_stops" in html
    assert "String(value) === String(number)" in html
    assert "InPit" in html
    assert "PitOut" in html
    assert "PitStop" in html
    assert "Out" in html
    assert "STOP" not in html
    assert "penaltyMap(snapshot)" in html
    assert "penaltySeconds(text)" in html
    assert "penaltyLabel(value)" in html
    assert "snapshot.penalties" in html
    assert "penalty-mark" in html
    assert "+${esc(row.penalty)}" in html
    assert "sessionEventName(session)" in html
    assert "session?.Meeting?.Name" in html
    assert "sessionLabel(session)" in html
    assert "displayRaceLap(lap)" in html
    assert 'lap: row.lap_number || "-"' in html
    assert "row.lap_number || (snapshot.lap_count || {}).CurrentLap" not in html
    assert "Last Lap" in html
    assert "Best Lap" in html
    assert "Standings" not in html
    assert "Analytics" not in html
    assert "Replay" not in html
    assert "Live Track Position" not in html
    assert "OpenF1" not in html
