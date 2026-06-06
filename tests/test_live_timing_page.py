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
            "race_control": [],
        }
    )

    assert payload["source"] == "f1-signalr"
    assert payload["drivers"][1]["tla"] == "VER"
    assert payload["positions"] == [{"driver_number": 1, "position": 1}]
    assert payload["laps"][0]["lap_duration"] == "1:12.345"
    assert payload["service"]["connected"] is True
