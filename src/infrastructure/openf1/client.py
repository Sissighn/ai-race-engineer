import json
import os
import threading
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.logging import get_logger

logger = get_logger(__name__)

OPENF1_BASE_URL = os.getenv("OPENF1_BASE_URL", "https://api.openf1.org/v1")
OPENF1_TIMEOUT = float(os.getenv("OPENF1_TIMEOUT", "10"))
OPENF1_MIN_REQUEST_INTERVAL = float(os.getenv("OPENF1_MIN_REQUEST_INTERVAL", "2.1"))
_REQUEST_LOCK = threading.Lock()
_LAST_REQUEST_AT = 0.0


class OpenF1Error(RuntimeError):
    """Raised when the OpenF1 API cannot provide a usable response."""


def _wait_for_rate_limit() -> None:
    global _LAST_REQUEST_AT
    with _REQUEST_LOCK:
        elapsed = time.monotonic() - _LAST_REQUEST_AT
        if elapsed < OPENF1_MIN_REQUEST_INTERVAL:
            time.sleep(OPENF1_MIN_REQUEST_INTERVAL - elapsed)
        _LAST_REQUEST_AT = time.monotonic()


def _fetch_json(endpoint: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    query = urlencode(params or {})
    url = f"{OPENF1_BASE_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    if query:
        url = f"{url}?{query}"

    request = Request(url, headers={"User-Agent": "ai-race-engineer/0.1"})
    try:
        _wait_for_rate_limit()
        with urlopen(request, timeout=OPENF1_TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        logger.warning("OpenF1 HTTP error", endpoint=endpoint, status=e.code, detail=detail)
        raise OpenF1Error(f"OpenF1 HTTP {e.code}: {detail}") from e
    except (URLError, TimeoutError, json.JSONDecodeError) as e:
        logger.warning("OpenF1 request failed", endpoint=endpoint, error=str(e))
        raise OpenF1Error(f"OpenF1 request failed: {e}") from e

    if isinstance(payload, dict):
        detail = payload.get("detail") or payload.get("error") or payload
        raise OpenF1Error(f"OpenF1 returned no usable data: {detail}")

    if not isinstance(payload, list):
        raise OpenF1Error("OpenF1 returned an unexpected response shape.")

    return payload


def _parse_dt(value: Any) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=UTC)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _latest_by_driver(records: list[dict[str, Any]], *, date_key: str = "date") -> list[dict[str, Any]]:
    latest: dict[int, dict[str, Any]] = {}
    for record in records:
        driver_number = record.get("driver_number")
        if driver_number is None:
            continue
        driver_number = int(driver_number)
        current = latest.get(driver_number)
        if current is None or _parse_dt(record.get(date_key)) >= _parse_dt(current.get(date_key)):
            latest[driver_number] = record
    return list(latest.values())


def get_latest_session() -> dict[str, Any] | None:
    sessions = _fetch_json("sessions", {"session_key": "latest"})
    return sessions[0] if sessions else None


def get_drivers(session_key: int | str = "latest") -> list[dict[str, Any]]:
    return _fetch_json("drivers", {"session_key": session_key})


def get_driver_lookup(session_key: int | str = "latest") -> dict[int, dict[str, Any]]:
    return {
        int(driver["driver_number"]): driver
        for driver in get_drivers(session_key)
        if driver.get("driver_number") is not None
    }


def get_latest_positions(session_key: int | str = "latest") -> list[dict[str, Any]]:
    positions = _fetch_json("position", {"session_key": session_key})
    latest = _latest_by_driver(positions)
    return sorted(latest, key=lambda row: int(row.get("position") or 99))


def get_latest_laps(session_key: int | str = "latest") -> list[dict[str, Any]]:
    laps = _fetch_json("laps", {"session_key": session_key})
    latest = _latest_by_driver(laps, date_key="date_start")
    return sorted(latest, key=lambda row: int(row.get("driver_number") or 999))


def get_latest_intervals(session_key: int | str = "latest") -> list[dict[str, Any]]:
    intervals = _fetch_json("intervals", {"session_key": session_key})
    latest = _latest_by_driver(intervals)
    return sorted(latest, key=lambda row: int(row.get("driver_number") or 999))


def get_latest_stints(session_key: int | str = "latest") -> list[dict[str, Any]]:
    stints = _fetch_json("stints", {"session_key": session_key})
    latest: dict[int, dict[str, Any]] = {}
    for stint in stints:
        driver_number = stint.get("driver_number")
        if driver_number is None:
            continue
        driver_number = int(driver_number)
        current = latest.get(driver_number)
        current_stint = int((current or {}).get("stint_number") or 0)
        next_stint = int(stint.get("stint_number") or 0)
        if current is None or next_stint >= current_stint:
            latest[driver_number] = stint
    return list(latest.values())


def _recent_window_start(session: dict[str, Any] | None) -> str:
    now = datetime.now(UTC)
    session_end = _parse_dt((session or {}).get("date_end"))
    anchor = min(now, session_end) if session_end > datetime.min.replace(tzinfo=UTC) else now
    return (anchor - timedelta(minutes=5)).isoformat()


def _window_start(seconds: int, session: dict[str, Any] | None = None) -> str:
    now = datetime.now(UTC)
    session_end = _parse_dt((session or {}).get("date_end"))
    anchor = min(now, session_end) if session_end > datetime.min.replace(tzinfo=UTC) else now
    return (anchor - timedelta(seconds=seconds)).isoformat()


def get_latest_car_snapshot(
    session_key: int | str,
    driver_number: int,
    *,
    session: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    params: dict[str, Any] = {
        "session_key": session_key,
        "driver_number": int(driver_number),
        "date>=": _recent_window_start(session),
    }
    try:
        records = _fetch_json("car_data", params)
    except OpenF1Error:
        records = _fetch_json(
            "car_data",
            {"session_key": session_key, "driver_number": int(driver_number)},
        )

    if not records:
        return None
    return max(records, key=lambda row: _parse_dt(row.get("date")))


def get_latest_car_data(
    session_key: int | str,
    *,
    session: dict[str, Any] | None = None,
    window_seconds: int = 30,
) -> list[dict[str, Any]]:
    records = _fetch_json(
        "car_data",
        {
            "session_key": session_key,
            "date>=": _window_start(window_seconds, session),
        },
    )
    return sorted(_latest_by_driver(records), key=lambda row: int(row.get("driver_number") or 999))


def get_latest_location(
    session_key: int | str,
    *,
    session: dict[str, Any] | None = None,
    window_seconds: int = 30,
) -> list[dict[str, Any]]:
    records = _fetch_json(
        "location",
        {
            "session_key": session_key,
            "date>=": _window_start(window_seconds, session),
        },
    )
    return sorted(_latest_by_driver(records), key=lambda row: int(row.get("driver_number") or 999))


def get_latest_race_control(session_key: int | str = "latest", limit: int = 8) -> list[dict[str, Any]]:
    messages = _fetch_json("race_control", {"session_key": session_key})
    messages = sorted(messages, key=lambda row: _parse_dt(row.get("date")), reverse=True)
    return messages[:limit]
