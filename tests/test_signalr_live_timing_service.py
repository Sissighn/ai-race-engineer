import base64
import json
import zlib

from src.services.live_timing_signalr.normalizer import (
    LiveTimingState,
    normalize_feed_message,
)


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
