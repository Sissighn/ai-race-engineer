import os
from contextlib import suppress
from threading import Event, Thread
from typing import Any

from src.infrastructure.openf1 import (
    OpenF1Error,
    get_driver_lookup,
    get_latest_car_data,
    get_latest_intervals,
    get_latest_laps,
    get_latest_location,
    get_latest_positions,
    get_latest_race_control,
    get_latest_session,
    get_latest_stints,
)
from src.logging import get_logger

from .normalizer import LiveTimingState

logger = get_logger(__name__)


def _driver_key(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return str(value)


def _format_gap(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, str):
        return value
    try:
        value = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"+{value:.3f}" if value > 0 else ""


def _latest_session_key(session: dict[str, Any] | None) -> int | str:
    if not session:
        return "latest"
    return session.get("session_key") or "latest"


class OpenF1LiveTimingWorker:
    """Polls OpenF1 and normalises it into the live timing snapshot shape."""

    def __init__(
        self,
        state: LiveTimingState,
        *,
        poll_interval: float | None = None,
        recent_window_seconds: int | None = None,
    ):
        self.state = state
        self.poll_interval = poll_interval or float(
            os.getenv("OPENF1_LIVE_POLL_INTERVAL", "18")
        )
        self.recent_window_seconds = recent_window_seconds or int(
            os.getenv("OPENF1_LIVE_WINDOW_SECONDS", "45")
        )
        self._stop = Event()
        self._thread: Thread | None = None
        self._drivers_session_key: int | str | None = None
        self._drivers: dict[int, dict[str, Any]] = {}

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = Thread(target=self._run_forever, name="openf1-live-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _get_drivers(self, session_key: int | str) -> dict[int, dict[str, Any]]:
        if self._drivers_session_key == session_key and self._drivers:
            return self._drivers
        self._drivers = get_driver_lookup(session_key)
        self._drivers_session_key = session_key
        return self._drivers

    def _fetch_optional(self, fetcher, *args, default, **kwargs):
        try:
            return fetcher(*args, **kwargs)
        except OpenF1Error as e:
            logger.debug("OpenF1 live endpoint unavailable", endpoint=fetcher.__name__, error=str(e))
            return default

    def _build_snapshot(self) -> dict[str, Any]:
        session = get_latest_session()
        session_key = _latest_session_key(session)
        drivers = self._get_drivers(session_key)

        positions = self._fetch_optional(get_latest_positions, session_key, default=[])
        laps = self._fetch_optional(get_latest_laps, session_key, default=[])
        intervals = self._fetch_optional(get_latest_intervals, session_key, default=[])
        stints = self._fetch_optional(get_latest_stints, session_key, default=[])
        car_data = self._fetch_optional(
            get_latest_car_data,
            session_key,
            default=[],
            session=session,
            window_seconds=self.recent_window_seconds,
        )
        locations = self._fetch_optional(
            get_latest_location,
            session_key,
            default=[],
            session=session,
            window_seconds=self.recent_window_seconds,
        )
        race_control = self._fetch_optional(get_latest_race_control, session_key, default=[])

        timing = self._build_timing(positions, laps, intervals)
        tyres = self._build_tyres(stints, timing)
        lap_count = self._build_lap_count(laps)

        return {
            "session": session or {},
            "drivers": {str(number): driver for number, driver in drivers.items()},
            "timing": timing,
            "tyres": tyres,
            "car_data": self._build_car_data(car_data),
            "positions": self._build_locations(locations),
            "race_control": race_control,
            "lap_count": lap_count,
            "track_status": {},
            "weather": {},
            "error": None,
        }

    def _build_timing(
        self,
        positions: list[dict[str, Any]],
        laps: list[dict[str, Any]],
        intervals: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        timing: dict[str, dict[str, Any]] = {}
        for position in positions:
            key = _driver_key(position.get("driver_number"))
            if key is None:
                continue
            timing.setdefault(key, {"driver_number": key})["position"] = position.get("position")

        for lap in laps:
            key = _driver_key(lap.get("driver_number"))
            if key is None:
                continue
            row = timing.setdefault(key, {"driver_number": key})
            row.update(
                {
                    "lap_number": lap.get("lap_number"),
                    "last_lap": lap.get("lap_duration"),
                    "best_lap": row.get("best_lap") or lap.get("lap_duration"),
                    "duration_sector_1": lap.get("duration_sector_1"),
                    "duration_sector_2": lap.get("duration_sector_2"),
                    "duration_sector_3": lap.get("duration_sector_3"),
                    "i1_speed": lap.get("i1_speed"),
                    "i2_speed": lap.get("i2_speed"),
                    "st_speed": lap.get("st_speed"),
                    "in_pit": lap.get("is_pit_out_lap"),
                }
            )

        for interval in intervals:
            key = _driver_key(interval.get("driver_number"))
            if key is None:
                continue
            row = timing.setdefault(key, {"driver_number": key})
            row["gap_to_leader"] = _format_gap(interval.get("gap_to_leader"))
            row["interval"] = _format_gap(interval.get("interval"))

        return timing

    def _build_tyres(
        self,
        stints: list[dict[str, Any]],
        timing: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        tyres = {}
        pit_stops = {}
        for stint in stints:
            key = _driver_key(stint.get("driver_number"))
            if key is None:
                continue
            with suppress(TypeError, ValueError):
                pit_stops[key] = max(pit_stops.get(key, 0), int(stint.get("stint_number") or 1) - 1)

        for stint in stints:
            key = _driver_key(stint.get("driver_number"))
            if key is None:
                continue
            current_lap = timing.get(key, {}).get("lap_number")
            lap_start = stint.get("lap_start")
            total_laps = None
            with suppress(TypeError, ValueError):
                total_laps = max(0, int(current_lap) - int(lap_start) + 1)
            tyres[key] = {
                "driver_number": key,
                "compound": stint.get("compound"),
                "total_laps": total_laps or stint.get("tyre_age_at_start") or "-",
                "new": None,
                "pit_stops": pit_stops.get(key, 0),
            }
        return tyres

    def _build_car_data(self, records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        data = {}
        for record in records:
            key = _driver_key(record.get("driver_number"))
            if key is None:
                continue
            data[key] = {
                "driver_number": key,
                "date": record.get("date"),
                "speed": record.get("speed"),
                "rpm": record.get("rpm"),
                "n_gear": record.get("n_gear"),
                "throttle": record.get("throttle"),
                "brake": record.get("brake"),
                "drs": record.get("drs"),
            }
        return data

    def _build_locations(self, records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        locations = {}
        for record in records:
            key = _driver_key(record.get("driver_number"))
            if key is None:
                continue
            locations[key] = {
                "driver_number": key,
                "date": record.get("date"),
                "x": record.get("x"),
                "y": record.get("y"),
                "z": record.get("z"),
                "status": "TRACK",
            }
        return locations

    def _build_lap_count(self, laps: list[dict[str, Any]]) -> dict[str, Any]:
        lap_numbers = [
            int(lap["lap_number"])
            for lap in laps
            if str(lap.get("lap_number") or "").isdigit()
        ]
        return {"CurrentLap": max(lap_numbers)} if lap_numbers else {}

    def _run_forever(self) -> None:
        while not self._stop.is_set():
            try:
                snapshot = self._build_snapshot()
                self.state.apply_openf1_snapshot(snapshot)
                self.state.mark_error(None)
            except Exception as e:
                logger.warning("OpenF1 live worker error", error=str(e), exc_info=True)
                self.state.mark_error(str(e))

            self._stop.wait(self.poll_interval)
