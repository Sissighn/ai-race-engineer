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
            "drivers": {
                "1": {"driver_number": "1", "tla": "VER", "team": "Red Bull Racing"}
            },
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
    assert "OpenF1" not in html
