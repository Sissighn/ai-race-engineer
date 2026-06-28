import base64
import copy
import json
import re
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

PENALTY_WORD_SECONDS = {
    "five": 5,
    "ten": 10,
    "twenty": 20,
    "thirty": 30,
}


def _deep_merge(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    for key, value in update.items():
        if value is None:
            continue
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        elif key == "pit_stops" and isinstance(base.get(key), int) and isinstance(value, int):
            base[key] = max(base[key], value)
        else:
            base[key] = value
    return base


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _is_lap_marker(value: Any) -> bool:
    return bool(re.fullmatch(r"\s*\+?\s*LAP\s+\d+\s*", str(value or ""), re.IGNORECASE))


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
        driver = {"driver_number": driver_number}
        field_map = {
            "tla": data.get("Tla") or data.get("TLA"),
            "broadcast_name": data.get("BroadcastName"),
            "full_name": data.get("FullName"),
            "team": data.get("TeamName") or data.get("Team"),
            "team_colour": data.get("TeamColour") or data.get("TeamColor"),
        }
        for key, value in field_map.items():
            if value not in (None, ""):
                driver[key] = value
        drivers[driver_number] = driver
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
        row: dict[str, Any] = {"driver_number": driver_number}

        position = data.get("Position")
        is_leader = str(position) == "1"
        if position:
            row["position"] = position

        if is_leader:
            row["gap_to_leader"] = ""
            row["interval"] = ""

        if not is_leader and (gap := data.get("GapToLeader")) and not _is_lap_marker(gap):
            row["gap_to_leader"] = gap

        if "IntervalToPositionAhead" in data:
            interval = data.get("IntervalToPositionAhead")
            if isinstance(interval, dict):
                if not is_leader and (value := interval.get("Value")) and not _is_lap_marker(value):
                    row["interval"] = value
            elif not is_leader and interval and not _is_lap_marker(interval):
                row["interval"] = interval

        last_lap = data.get("LastLapTime")
        if isinstance(last_lap, dict):
            if value := last_lap.get("Value"):
                row["last_lap"] = value
        elif last_lap:
            row["last_lap"] = last_lap

        best_lap = data.get("BestLapTime")
        if isinstance(best_lap, dict):
            if value := best_lap.get("Value"):
                row["best_lap"] = value
        elif best_lap:
            row["best_lap"] = best_lap

        sectors = data.get("Sectors")
        if isinstance(sectors, list):
            row["sectors"] = {str(index): sector for index, sector in enumerate(sectors)}
        elif isinstance(sectors, dict):
            row["sectors"] = sectors

        for source, target in (
            ("InPit", "in_pit"),
            ("PitOut", "pit_out"),
            ("Stopped", "stopped"),
        ):
            if source in data:
                row[target] = data[source]

        timing[driver_number] = row
    return timing


def _stint_entries(stints: Any) -> list[tuple[Any, dict[str, Any]]]:
    if isinstance(stints, dict):
        values = list(stints.items())
    elif isinstance(stints, list):
        values = list(enumerate(stints))
    else:
        return []

    return [(key, stint) for key, stint in values if isinstance(stint, dict)]


def _stint_values(stints: Any) -> list[dict[str, Any]]:
    return [stint for _, stint in _stint_entries(stints)]


def _stint_index(key: Any, stint: dict[str, Any]) -> int | None:
    for value in (
        key,
        stint.get("Stint"),
        stint.get("StintNumber"),
        stint.get("stint_number"),
        stint.get("Number"),
    ):
        if (index := _int_or_none(value)) is not None:
            return index
    return None


def _latest_stint(stints: Any) -> dict[str, Any]:
    valid = _stint_entries(stints)
    if not valid:
        return {}
    return max(
        valid,
        key=lambda entry: (
            _stint_index(entry[0], entry[1]) if _stint_index(entry[0], entry[1]) is not None else -1
        ),
    )[1]


def _pit_stop_count_from_stints(stints: Any) -> int:
    entries = _stint_entries(stints)
    if not entries:
        return 0

    counts = [max(len(entries) - 1, 0)]
    for key, stint in entries:
        if (index := _stint_index(key, stint)) is not None:
            counts.append(max(index, 0))
    return max(counts)


def _normalise_timing_app_data(payload: dict[str, Any]) -> dict[str, Any]:
    lines = payload.get("Lines", payload)
    tyres = {}
    if not isinstance(lines, dict):
        return tyres

    for number, data in lines.items():
        if not isinstance(data, dict):
            continue
        driver_number = str(data.get("RacingNumber") or number)
        stints = data.get("Stints") or data.get("stints")
        stint = _latest_stint(stints)
        compound = (
            stint.get("Compound")
            or stint.get("compound")
            or data.get("Compound")
            or data.get("TyreCompound")
        )
        total_laps = (
            stint.get("TotalLaps")
            or stint.get("LapNumber")
            or stint.get("Laps")
            or data.get("TotalLaps")
        )
        tyres[driver_number] = {
            "driver_number": driver_number,
            "compound": compound,
            "total_laps": total_laps,
            "new": stint.get("New") if isinstance(stint, dict) else None,
            "pit_stops": _pit_stop_count_from_stints(stints),
        }
    return tyres


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
        text = message.get("Message") or message.get("Title") or ""
        driver_number = message.get("RacingNumber") or _driver_number_from_text(text)
        penalty_seconds = _penalty_seconds_from_text(text)
        normalised.append(
            {
                "date": message.get("Utc") or message.get("Date"),
                "category": message.get("Category") or message.get("Flag") or "MESSAGE",
                "message": text,
                "driver_number": driver_number,
                "lap": message.get("Lap"),
                "penalty_seconds": penalty_seconds,
            }
        )
    return normalised


def _driver_number_from_text(text: Any) -> str | None:
    match = re.search(r"\bcar\s*#?\s*(\d{1,3})\b", str(text), flags=re.IGNORECASE)
    return match.group(1) if match else None


def _penalty_seconds_from_text(text: Any) -> int | None:
    text_value = str(text)
    if not re.search(r"\bpenalt", text_value, flags=re.IGNORECASE):
        return None

    numeric = re.search(
        r"\b(\d{1,2})\s*(?:second|seconds|sec|s)\b", text_value, flags=re.IGNORECASE
    )
    if numeric:
        return int(numeric.group(1))

    word = re.search(
        r"\b(five|ten|twenty|thirty)\s+(?:second|seconds|sec|s)\b",
        text_value,
        flags=re.IGNORECASE,
    )
    if word:
        return PENALTY_WORD_SECONDS[word.group(1).lower()]
    return None


def _penalty_events_from_race_control(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    events = []
    for message in messages:
        text = message.get("message") or message.get("Message") or ""
        driver_number = message.get("driver_number") or _driver_number_from_text(text)
        penalty_seconds = message.get("penalty_seconds") or _penalty_seconds_from_text(text)
        if not driver_number or not penalty_seconds:
            continue
        events.append(
            {
                "driver_number": str(driver_number),
                "seconds": penalty_seconds,
                "message": text,
                "date": message.get("date"),
                "lap": message.get("lap"),
            }
        )
    return events


def normalize_feed_message(message: Any) -> dict[str, Any]:
    normalised: dict[str, Any] = {
        "drivers": {},
        "timing": {},
        "car_data": {},
        "positions": {},
        "tyres": {},
        "race_control": [],
        "penalty_events": [],
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
        elif topic == "TimingAppData" and isinstance(payload, dict):
            normalised["tyres"].update(_normalise_timing_app_data(payload))
        elif topic == "CarData.z":
            normalised["car_data"].update(_normalise_car_data(payload))
        elif topic == "Position.z":
            normalised["positions"].update(_normalise_position_data(payload))
        elif topic == "RaceControlMessages" and isinstance(payload, dict):
            race_control = _normalise_race_control(payload)
            normalised["race_control"].extend(race_control)
            normalised["penalty_events"].extend(_penalty_events_from_race_control(race_control))
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
    source: str = "offline"
    connected: bool = False
    last_message_at: float | None = None
    message_count: int = 0
    error: str | None = None
    drivers: dict[str, Any] = field(default_factory=dict)
    timing: dict[str, Any] = field(default_factory=dict)
    car_data: dict[str, Any] = field(default_factory=dict)
    positions: dict[str, Any] = field(default_factory=dict)
    tyres: dict[str, Any] = field(default_factory=dict)
    race_control: list[dict[str, Any]] = field(default_factory=list)
    penalties: dict[str, Any] = field(default_factory=dict)
    session: dict[str, Any] = field(default_factory=dict)
    track_status: dict[str, Any] = field(default_factory=dict)
    weather: dict[str, Any] = field(default_factory=dict)
    lap_count: dict[str, Any] = field(default_factory=dict)
    raw_categories: dict[str, Any] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock, repr=False)
    _penalty_event_keys: set[str] = field(default_factory=set, repr=False)

    def mark_connected(self, connected: bool) -> None:
        with self._lock:
            self.connected = connected

    def mark_error(self, error: str | None) -> None:
        with self._lock:
            self.error = error

    def apply_message(self, message: Any) -> None:
        update = normalize_feed_message(message)
        with self._lock:
            self.source = "f1-signalr"
            self.message_count += 1
            self.last_message_at = time.time()
            _deep_merge(self.drivers, update["drivers"])
            _deep_merge(self.timing, update["timing"])
            _deep_merge(self.car_data, update["car_data"])
            _deep_merge(self.positions, update["positions"])
            _deep_merge(self.tyres, update["tyres"])
            _deep_merge(self.session, update["session"])
            _deep_merge(self.track_status, update["track_status"])
            _deep_merge(self.weather, update["weather"])
            _deep_merge(self.lap_count, update["lap_count"])
            _deep_merge(self.raw_categories, update["raw_categories"])
            self._apply_penalty_events(update["penalty_events"])
            if update["race_control"]:
                self.race_control.extend(update["race_control"])
                self.race_control = self.race_control[-50:]

    def apply_openf1_snapshot(self, snapshot: dict[str, Any]) -> None:
        with self._lock:
            self.source = "openf1"
            self.connected = True
            self.message_count += 1
            self.last_message_at = time.time()
            self.error = snapshot.get("error")
            _deep_merge(self.drivers, snapshot.get("drivers") or {})
            _deep_merge(self.timing, snapshot.get("timing") or {})
            _deep_merge(self.car_data, snapshot.get("car_data") or {})
            _deep_merge(self.positions, snapshot.get("positions") or {})
            _deep_merge(self.tyres, snapshot.get("tyres") or {})
            _deep_merge(self.session, snapshot.get("session") or {})
            _deep_merge(self.track_status, snapshot.get("track_status") or {})
            _deep_merge(self.weather, snapshot.get("weather") or {})
            _deep_merge(self.lap_count, snapshot.get("lap_count") or {})
            self.raw_categories["OpenF1"] = {"timestamp": self.last_message_at}
            race_control = snapshot.get("race_control") or []
            if race_control:
                self.race_control.extend(race_control)
                self.race_control = self.race_control[-50:]
                self._apply_penalty_events(_penalty_events_from_race_control(race_control))

    def _apply_penalty_events(self, events: list[dict[str, Any]]) -> None:
        for event in events:
            driver_number = str(event.get("driver_number") or "")
            seconds = _int_or_none(event.get("seconds"))
            if not driver_number or seconds is None:
                continue
            key = "|".join(
                str(event.get(field) or "") for field in ("driver_number", "date", "lap", "message")
            )
            if key in self._penalty_event_keys:
                continue
            self._penalty_event_keys.add(key)
            penalty = self.penalties.setdefault(
                driver_number,
                {"seconds": 0, "label": "0s", "events": []},
            )
            penalty["seconds"] += seconds
            penalty["label"] = f"{penalty['seconds']}s"
            penalty["events"].append(copy.deepcopy(event))

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            now = time.time()
            return {
                "source": self.source,
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
                "tyres": copy.deepcopy(self.tyres),
                "race_control": copy.deepcopy(self.race_control),
                "penalties": copy.deepcopy(self.penalties),
                "session": copy.deepcopy(self.session),
                "track_status": copy.deepcopy(self.track_status),
                "weather": copy.deepcopy(self.weather),
                "lap_count": copy.deepcopy(self.lap_count),
                "raw_categories": copy.deepcopy(self.raw_categories),
            }
