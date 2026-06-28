import base64
import json
import zlib

from src.services.live_timing_signalr.normalizer import (
    LiveTimingState,
    normalize_feed_message,
)
from src.services.live_timing_signalr.openf1_worker import OpenF1LiveTimingWorker


def _z_payload(payload: dict) -> str:
    raw = json.dumps(payload).encode("utf-8")
    return base64.b64encode(zlib.compress(raw)[2:-4]).decode("ascii")


def test_normalize_feed_message_maps_driver_and_timing_data():
    update = normalize_feed_message(
        [
            [
                "DriverList",
                {
                    "1": {
                        "RacingNumber": "1",
                        "Tla": "VER",
                        "FullName": "Max Verstappen",
                        "TeamName": "Red Bull Racing",
                    }
                },
                "2026-06-07T12:00:00Z",
            ],
            [
                "TimingData",
                {
                    "Lines": {
                        "1": {
                            "RacingNumber": "1",
                            "Position": "1",
                            "GapToLeader": "",
                            "IntervalToPositionAhead": {"Value": ""},
                            "LastLapTime": {"Value": "1:12.345"},
                            "BestLapTime": {"Value": "1:11.111"},
                            "InPit": True,
                            "PitOut": False,
                            "Stopped": False,
                        }
                    }
                },
                "2026-06-07T12:00:01Z",
            ],
        ]
    )

    assert update["drivers"]["1"]["tla"] == "VER"
    assert update["timing"]["1"]["position"] == "1"
    assert update["timing"]["1"]["last_lap"] == "1:12.345"
    assert update["timing"]["1"]["in_pit"] is True
    assert update["timing"]["1"]["pit_out"] is False
    assert update["timing"]["1"]["stopped"] is False


def test_normalize_feed_message_decodes_car_data_z():
    payload = _z_payload(
        {
            "Entries": [
                {
                    "Utc": "2026-06-07T12:00:00Z",
                    "Cars": {
                        "1": {
                            "Channels": {
                                "0": 11000,
                                "2": 286,
                                "3": 7,
                                "4": 96,
                                "5": 0,
                            }
                        }
                    },
                }
            ]
        }
    )

    update = normalize_feed_message(["CarData.z", payload, ""])

    assert update["car_data"]["1"]["rpm"] == 11000
    assert update["car_data"]["1"]["speed"] == 286
    assert update["car_data"]["1"]["throttle"] == 96


def test_normalize_feed_message_maps_timing_app_tyres():
    update = normalize_feed_message(
        [
            "TimingAppData",
            {
                "Lines": {
                    "1": {
                        "RacingNumber": "1",
                        "Stints": {
                            "0": {
                                "Compound": "MEDIUM",
                                "TotalLaps": 12,
                                "New": "true",
                            },
                            "1": {
                                "Compound": "SOFT",
                                "TotalLaps": 8,
                                "New": "true",
                            },
                        },
                    }
                }
            },
            "",
        ]
    )

    assert update["tyres"]["1"]["compound"] == "SOFT"
    assert update["tyres"]["1"]["total_laps"] == 8
    assert update["tyres"]["1"]["pit_stops"] == 1


def test_normalize_feed_message_uses_sparse_stint_index_for_pit_stops():
    update = normalize_feed_message(
        [
            "TimingAppData",
            {
                "Lines": {
                    "44": {
                        "RacingNumber": "44",
                        "Stints": {
                            "2": {
                                "Compound": "HARD",
                                "TotalLaps": 4,
                                "New": "true",
                            }
                        },
                    }
                }
            },
            "",
        ]
    )

    assert update["tyres"]["44"]["compound"] == "HARD"
    assert update["tyres"]["44"]["pit_stops"] == 2


def test_live_timing_state_does_not_reduce_pit_stop_count_from_delta():
    state = LiveTimingState()
    state.apply_message(
        [
            "TimingAppData",
            {
                "Lines": {
                    "44": {
                        "RacingNumber": "44",
                        "Stints": {
                            "2": {
                                "Compound": "HARD",
                                "TotalLaps": 4,
                            }
                        },
                    }
                }
            },
            "",
        ]
    )
    state.apply_message(
        [
            "TimingAppData",
            {
                "Lines": {
                    "44": {
                        "RacingNumber": "44",
                        "Stints": {
                            "0": {
                                "Compound": "MEDIUM",
                                "TotalLaps": 1,
                            }
                        },
                    }
                }
            },
            "",
        ]
    )

    assert state.snapshot()["tyres"]["44"]["pit_stops"] == 2


def test_live_timing_state_applies_messages_and_builds_snapshot():
    state = LiveTimingState()
    state.mark_connected(True)
    state.apply_message(
        [
            "RaceControlMessages",
            {
                "Messages": {
                    "1": {
                        "Utc": "2026-06-07T12:00:00Z",
                        "Category": "Flag",
                        "Message": "GREEN LIGHT - PIT EXIT OPEN",
                    }
                }
            },
            "",
        ]
    )

    snapshot = state.snapshot()

    assert snapshot["connected"] is True
    assert snapshot["message_count"] == 1
    assert snapshot["race_control"][0]["message"] == "GREEN LIGHT - PIT EXIT OPEN"


def test_live_timing_state_keeps_race_control_penalty_driver_number():
    state = LiveTimingState()
    state.apply_message(
        [
            "RaceControlMessages",
            {
                "Messages": {
                    "1": {
                        "Utc": "2026-06-07T12:00:00Z",
                        "Category": "Other",
                        "Message": "FIVE SECOND TIME PENALTY FOR CAR 44",
                        "RacingNumber": "44",
                        "Lap": 12,
                    }
                }
            },
            "",
        ]
    )

    snapshot = state.snapshot()

    assert snapshot["race_control"][0]["message"] == "FIVE SECOND TIME PENALTY FOR CAR 44"
    assert snapshot["race_control"][0]["driver_number"] == "44"
    assert snapshot["race_control"][0]["lap"] == 12
    assert snapshot["penalties"]["44"]["label"] == "5s"


def test_live_timing_state_keeps_penalties_after_race_control_rollover():
    state = LiveTimingState()
    state.apply_message(
        [
            "RaceControlMessages",
            {
                "Messages": {
                    "1": {
                        "Utc": "2026-06-07T12:00:00Z",
                        "Category": "Other",
                        "Message": "10 SECOND TIME PENALTY FOR CAR 55",
                    }
                }
            },
            "",
        ]
    )
    for index in range(60):
        state.apply_message(
            [
                "RaceControlMessages",
                {
                    "Messages": {
                        str(index): {
                            "Utc": f"2026-06-07T12:{index:02d}:00Z",
                            "Category": "Flag",
                            "Message": f"WAVED BLUE FLAG FOR CAR 14 TIMED AT {index}",
                        }
                    }
                },
                "",
            ]
        )

    snapshot = state.snapshot()

    assert len(snapshot["race_control"]) == 50
    assert snapshot["race_control"][0]["message"] != "10 SECOND TIME PENALTY FOR CAR 55"
    assert snapshot["penalties"]["55"]["label"] == "10s"


def test_driver_list_delta_does_not_replace_name_with_racing_number():
    state = LiveTimingState()
    state.apply_message(
        [
            "DriverList",
            {
                "12": {
                    "RacingNumber": "12",
                    "Tla": "ANT",
                    "BroadcastName": "K ANTONELLI",
                    "FullName": "Kimi ANTONELLI",
                    "TeamName": "Mercedes",
                }
            },
            "",
        ]
    )
    state.apply_message(["DriverList", {"12": {"RacingNumber": "12"}}, ""])

    driver = state.snapshot()["drivers"]["12"]

    assert driver["tla"] == "ANT"
    assert driver["broadcast_name"] == "K ANTONELLI"
    assert driver["full_name"] == "Kimi ANTONELLI"
    assert driver["team"] == "Mercedes"


def test_driver_list_without_name_does_not_use_number_as_tla():
    update = normalize_feed_message(["DriverList", {"12": {"RacingNumber": "12"}}, ""])

    assert update["drivers"]["12"] == {"driver_number": "12"}


def test_timing_data_delta_updates_do_not_clear_previous_classification():
    state = LiveTimingState()
    state.apply_message(
        [
            "TimingData",
            {
                "Lines": {
                    "1": {
                        "RacingNumber": "1",
                        "Position": "2",
                        "GapToLeader": "+3.557",
                        "IntervalToPositionAhead": {"Value": "+1.203"},
                        "LastLapTime": {"Value": "1:17.028"},
                        "BestLapTime": {"Value": "1:16.587"},
                    }
                }
            },
            "",
        ]
    )
    state.apply_message(
        [
            "TimingData",
            {
                "Lines": {
                    "1": {
                        "RacingNumber": "1",
                        "Sectors": {"0": {"Value": "20.123"}},
                    }
                }
            },
            "",
        ]
    )

    row = state.snapshot()["timing"]["1"]

    assert row["position"] == "2"
    assert row["gap_to_leader"] == "+3.557"
    assert row["interval"] == "+1.203"
    assert row["last_lap"] == "1:17.028"
    assert row["best_lap"] == "1:16.587"
    assert row["sectors"]["0"]["Value"] == "20.123"


def test_timing_data_leader_update_clears_gap_and_interval():
    state = LiveTimingState()
    state.apply_message(
        [
            "TimingData",
            {
                "Lines": {
                    "1": {
                        "RacingNumber": "1",
                        "Position": "2",
                        "GapToLeader": "+3.557",
                        "IntervalToPositionAhead": {"Value": "+1.203"},
                    }
                }
            },
            "",
        ]
    )
    state.apply_message(
        [
            "TimingData",
            {
                "Lines": {
                    "1": {
                        "RacingNumber": "1",
                        "Position": "1",
                    }
                }
            },
            "",
        ]
    )

    row = state.snapshot()["timing"]["1"]

    assert row["position"] == "1"
    assert row["gap_to_leader"] == ""
    assert row["interval"] == ""


def test_timing_data_leader_ignores_lap_marker_as_gap():
    state = LiveTimingState()
    state.apply_message(
        [
            "TimingData",
            {
                "Lines": {
                    "12": {
                        "RacingNumber": "12",
                        "Position": "1",
                        "GapToLeader": "LAP 23",
                        "IntervalToPositionAhead": {"Value": "LAP 23"},
                    }
                }
            },
            "",
        ]
    )

    row = state.snapshot()["timing"]["12"]

    assert row["position"] == "1"
    assert row["gap_to_leader"] == ""
    assert row["interval"] == ""


def test_timing_data_ignores_lap_marker_gap_without_position_delta():
    state = LiveTimingState()
    state.apply_message(
        [
            "TimingData",
            {
                "Lines": {
                    "63": {
                        "RacingNumber": "63",
                        "Position": "1",
                    }
                }
            },
            "",
        ]
    )
    state.apply_message(
        [
            "TimingData",
            {
                "Lines": {
                    "63": {
                        "RacingNumber": "63",
                        "GapToLeader": "LAP 29",
                        "IntervalToPositionAhead": {"Value": "LAP 29"},
                    }
                }
            },
            "",
        ]
    )

    row = state.snapshot()["timing"]["63"]

    assert row["position"] == "1"
    assert row["gap_to_leader"] == ""
    assert row["interval"] == ""


def test_live_timing_state_applies_openf1_snapshot():
    state = LiveTimingState()

    state.apply_openf1_snapshot(
        {
            "drivers": {"1": {"name_acronym": "VER"}},
            "timing": {"1": {"position": 1, "last_lap": 72.1}},
            "positions": {"1": {"x": 10, "y": 20}},
            "car_data": {"1": {"speed": 286}},
            "tyres": {"1": {"compound": "MEDIUM"}},
            "race_control": [{"message": "GREEN FLAG"}],
            "session": {"session_name": "Race"},
        }
    )

    snapshot = state.snapshot()

    assert snapshot["source"] == "openf1"
    assert snapshot["connected"] is True
    assert snapshot["drivers"]["1"]["name_acronym"] == "VER"
    assert snapshot["timing"]["1"]["position"] == 1
    assert snapshot["positions"]["1"]["x"] == 10
    assert snapshot["race_control"][0]["message"] == "GREEN FLAG"


def test_openf1_worker_builds_snapshot_shape(monkeypatch):
    worker = OpenF1LiveTimingWorker(LiveTimingState(), poll_interval=1)

    monkeypatch.setattr(
        "src.services.live_timing_signalr.openf1_worker.get_latest_session",
        lambda: {"session_key": 99, "session_name": "Race"},
    )
    monkeypatch.setattr(
        "src.services.live_timing_signalr.openf1_worker.get_driver_lookup",
        lambda _session_key: {
            1: {"driver_number": 1, "name_acronym": "VER", "team_colour": "3671C6"}
        },
    )
    monkeypatch.setattr(
        "src.services.live_timing_signalr.openf1_worker.get_latest_positions",
        lambda _session_key: [{"driver_number": 1, "position": 1}],
    )
    monkeypatch.setattr(
        "src.services.live_timing_signalr.openf1_worker.get_latest_laps",
        lambda _session_key: [
            {
                "driver_number": 1,
                "lap_number": 12,
                "lap_duration": 72.123,
                "duration_sector_1": 23.1,
            }
        ],
    )
    monkeypatch.setattr(
        "src.services.live_timing_signalr.openf1_worker.get_latest_intervals",
        lambda _session_key: [{"driver_number": 1, "gap_to_leader": None, "interval": None}],
    )
    monkeypatch.setattr(
        "src.services.live_timing_signalr.openf1_worker.get_latest_stints",
        lambda _session_key: [
            {"driver_number": 1, "compound": "HARD", "lap_start": 10, "stint_number": 2}
        ],
    )
    monkeypatch.setattr(
        "src.services.live_timing_signalr.openf1_worker.get_latest_car_data",
        lambda *_args, **_kwargs: [
            {"driver_number": 1, "speed": 286, "rpm": 11000, "date": "2026-06-07T12:00:00Z"}
        ],
    )
    monkeypatch.setattr(
        "src.services.live_timing_signalr.openf1_worker.get_latest_location",
        lambda *_args, **_kwargs: [
            {"driver_number": 1, "x": 100, "y": 200, "z": 0, "date": "2026-06-07T12:00:00Z"}
        ],
    )
    monkeypatch.setattr(
        "src.services.live_timing_signalr.openf1_worker.get_latest_race_control",
        lambda _session_key: [{"message": "GREEN FLAG"}],
    )

    snapshot = worker._build_snapshot()

    assert snapshot["drivers"]["1"]["name_acronym"] == "VER"
    assert snapshot["timing"]["1"]["position"] == 1
    assert snapshot["timing"]["1"]["last_lap"] == 72.123
    assert snapshot["tyres"]["1"]["compound"] == "HARD"
    assert snapshot["tyres"]["1"]["total_laps"] == 3
    assert snapshot["tyres"]["1"]["pit_stops"] == 1
    assert snapshot["car_data"]["1"]["speed"] == 286
    assert snapshot["positions"]["1"]["x"] == 100
    assert snapshot["lap_count"]["CurrentLap"] == 12
