import base64
import copy
import json
import time
import zlib
from dataclasses import dataclass, field
from threading import RLock
from typing import Any

from signalrcore.messages.completion_message import CompletionMessage

CAR_CHANNELS = {
    "0": "rpm",
    "2": "speed",
    "3": "n_gear",
    "4": "throttle",
    "5": "brake",
    "45": "drs",
}


def _deep_merge(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _decode_z_payload(payload: Any) -> dict[str, Any] | None:
    if isinstance(payload, dict):
        return payload
    if not isinstance(payload, str) or not payload:
        return None

    text = payload.strip('"')
    try:
        decoded = zlib.decompress(base64.b64decode(text), -zlib.MAX_WBITS)
        return json.loads(decoded.decode("utf-8-sig"))
    except Exception:
        return None


def _message_items(message: Any) -> list[tuple[str, Any, Any]]:
    if isinstance(message, CompletionMessage):
        result = message.result or {}
        return [(str(key), value, None) for key, value in result.items()]

    if isinstance(message, list):
        if len(message) >= 2 and isinstance(message[0], str):
            return [(message[0], message[1], message[2] if len(message) > 2 else None)]

        items = []
        for item in message:
            if isinstance(item, list) and len(item) >= 2:
                items.append((str(item[0]), item[1], item[2] if len(item) > 2 else None))
        return items

    return []


def _normalise_driver_list(payload: dict[str, Any]) -> dict[str, Any]:
    drivers = {}
    for number, data in payload.items():
        if not isinstance(data, dict):
            continue
        driver_number = str(data.get("RacingNumber") or number)
        drivers[driver_number] = {
            "driver_number": driver_number,
            "tla": data.get("Tla") or data.get("TLA") or driver_number,
            "broadcast_name": data.get("BroadcastName") or data.get("FullName") or driver_number,
            "full_name": data.get("FullName") or data.get("BroadcastName") or driver_number,
            "team": data.get("TeamName") or data.get("Team") or "-",
            "team_colour": data.get("TeamColour") or data.get("TeamColor") or "",
        }
    return drivers


def _normalise_timing_data(payload: dict[str, Any]) -> dict[str, Any]:
    lines = payload.get("Lines", payload)
    timing = {}
    if not isinstance(lines, dict):
        return timing

    for number, data in lines.items():
        if not isinstance(data, dict):
            continue
        driver_number = str(data.get("RacingNumber") or number)
        sectors = data.get("Sectors") or []
        timing[driver_number] = {
            "driver_number": driver_number,
            "position": data.get("Position"),
            "gap_to_leader": data.get("GapToLeader"),
            "interval": data.get("IntervalToPositionAhead", {}).get("Value")
            if isinstance(data.get("IntervalToPositionAhead"), dict)
            else data.get("IntervalToPositionAhead"),
            "last_lap": data.get("LastLapTime", {}).get("Value")
            if isinstance(data.get("LastLapTime"), dict)
            else data.get("LastLapTime"),
            "best_lap": data.get("BestLapTime", {}).get("Value")
            if isinstance(data.get("BestLapTime"), dict)
            else data.get("BestLapTime"),
            "sectors": sectors,
            "in_pit": data.get("InPit"),
            "pit_out": data.get("PitOut"),
            "stopped": data.get("Stopped"),
        }
    return timing


def _normalise_car_data(payload: Any) -> dict[str, Any]:
    decoded = _decode_z_payload(payload)
    if not decoded:
        return {}

    latest = {}
    for entry in decoded.get("Entries", []):
        utc = entry.get("Utc")
        cars = entry.get("Cars") or {}
        for number, car in cars.items():
            channels = car.get("Channels") or {}
            row = {"driver_number": str(number), "date": utc}
            for source, target in CAR_CHANNELS.items():
                if source in channels:
                    row[target] = channels[source]
            latest[str(number)] = row
    return latest


def _normalise_position_data(payload: Any) -> dict[str, Any]:
    decoded = _decode_z_payload(payload)
    if not decoded:
        return {}

    latest = {}
    for entry in decoded.get("Position", decoded.get("Entries", [])):
        utc = entry.get("Timestamp") or entry.get("Utc")
        cars = entry.get("Entries") or entry.get("Cars") or {}
        for number, data in cars.items():
            if not isinstance(data, dict):
                continue
            latest[str(number)] = {
                "driver_number": str(number),
                "date": utc,
                "x": data.get("X"),
                "y": data.get("Y"),
                "z": data.get("Z"),
                "status": data.get("Status"),
            }
    return latest


def _normalise_race_control(payload: dict[str, Any]) -> list[dict[str, Any]]:
    messages = payload.get("Messages", payload)
    if isinstance(messages, dict):
        messages = list(messages.values())
    if not isinstance(messages, list):
        return []

    normalised = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        normalised.append(
            {
                "date": message.get("Utc") or message.get("Date"),
                "category": message.get("Category") or message.get("Flag") or "MESSAGE",
                "message": message.get("Message") or message.get("Title") or "",
                "driver_number": message.get("RacingNumber"),
                "lap": message.get("Lap"),
            }
        )
    return normalised


def normalize_feed_message(message: Any) -> dict[str, Any]:
    normalised: dict[str, Any] = {
        "drivers": {},
        "timing": {},
        "car_data": {},
        "positions": {},
        "race_control": [],
        "session": {},
        "track_status": {},
        "weather": {},
        "lap_count": {},
        "raw_categories": {},
    }

    for topic, payload, timestamp in _message_items(message):
        normalised["raw_categories"][topic] = {"timestamp": timestamp}

        if topic == "DriverList" and isinstance(payload, dict):
            normalised["drivers"].update(_normalise_driver_list(payload))
        elif topic == "TimingData" and isinstance(payload, dict):
            normalised["timing"].update(_normalise_timing_data(payload))
        elif topic == "CarData.z":
            normalised["car_data"].update(_normalise_car_data(payload))
        elif topic == "Position.z":
            normalised["positions"].update(_normalise_position_data(payload))
        elif topic == "RaceControlMessages" and isinstance(payload, dict):
            normalised["race_control"].extend(_normalise_race_control(payload))
        elif topic == "SessionInfo" and isinstance(payload, dict):
            normalised["session"].update(payload)
        elif topic == "SessionStatus" and isinstance(payload, dict):
            normalised["session"].update({"status": payload})
        elif topic == "TrackStatus" and isinstance(payload, dict):
            normalised["track_status"].update(payload)
        elif topic == "WeatherData" and isinstance(payload, dict):
            normalised["weather"].update(payload)
        elif topic == "LapCount" and isinstance(payload, dict):
            normalised["lap_count"].update(payload)

    return normalised


@dataclass
class LiveTimingState:
    started_at: float = field(default_factory=time.time)
    connected: bool = False
    last_message_at: float | None = None
    message_count: int = 0
    error: str | None = None
    drivers: dict[str, Any] = field(default_factory=dict)
    timing: dict[str, Any] = field(default_factory=dict)
    car_data: dict[str, Any] = field(default_factory=dict)
    positions: dict[str, Any] = field(default_factory=dict)
    race_control: list[dict[str, Any]] = field(default_factory=list)
    session: dict[str, Any] = field(default_factory=dict)
    track_status: dict[str, Any] = field(default_factory=dict)
    weather: dict[str, Any] = field(default_factory=dict)
    lap_count: dict[str, Any] = field(default_factory=dict)
    raw_categories: dict[str, Any] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock, repr=False)

    def mark_connected(self, connected: bool) -> None:
        with self._lock:
            self.connected = connected

    def mark_error(self, error: str | None) -> None:
        with self._lock:
            self.error = error

    def apply_message(self, message: Any) -> None:
        update = normalize_feed_message(message)
        with self._lock:
            self.message_count += 1
            self.last_message_at = time.time()
            _deep_merge(self.drivers, update["drivers"])
            _deep_merge(self.timing, update["timing"])
            _deep_merge(self.car_data, update["car_data"])
            _deep_merge(self.positions, update["positions"])
            _deep_merge(self.session, update["session"])
            _deep_merge(self.track_status, update["track_status"])
            _deep_merge(self.weather, update["weather"])
            _deep_merge(self.lap_count, update["lap_count"])
            _deep_merge(self.raw_categories, update["raw_categories"])
            if update["race_control"]:
                self.race_control.extend(update["race_control"])
                self.race_control = self.race_control[-50:]

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            now = time.time()
            return {
                "source": "f1-signalr",
                "connected": self.connected,
                "healthy": self.connected and self.last_message_at is not None,
                "started_at": self.started_at,
                "uptime_seconds": round(now - self.started_at, 3),
                "last_message_at": self.last_message_at,
                "seconds_since_last_message": (
                    round(now - self.last_message_at, 3)
                    if self.last_message_at is not None
                    else None
                ),
                "message_count": self.message_count,
                "error": self.error,
                "drivers": copy.deepcopy(self.drivers),
                "timing": copy.deepcopy(self.timing),
                "car_data": copy.deepcopy(self.car_data),
                "positions": copy.deepcopy(self.positions),
                "race_control": copy.deepcopy(self.race_control),
                "session": copy.deepcopy(self.session),
                "track_status": copy.deepcopy(self.track_status),
                "weather": copy.deepcopy(self.weather),
                "lap_count": copy.deepcopy(self.lap_count),
                "raw_categories": copy.deepcopy(self.raw_categories),
            }
