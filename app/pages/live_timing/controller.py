from datetime import UTC, datetime

import pandas as pd
import streamlit as st

from app.components.navbar import navbar
from app.utils.ui import apply_dark_page_shell, load_css
from src.infrastructure.live_timing_service import (
    LiveTimingServiceError,
    get_signalr_snapshot,
)
from src.infrastructure.openf1 import (
    OpenF1Error,
    get_driver_lookup,
    get_latest_car_snapshot,
    get_latest_laps,
    get_latest_positions,
    get_latest_race_control,
    get_latest_session,
)
from src.logging import get_logger

logger = get_logger(__name__)


@st.cache_data(ttl=4, show_spinner=False)
def _load_live_timing_payload() -> dict:
    try:
        signalr_payload = get_signalr_snapshot()
        if signalr_payload.get("message_count", 0) > 0:
            return _payload_from_signalr(signalr_payload)
    except LiveTimingServiceError:
        pass

    session = get_latest_session()
    if not session:
        raise OpenF1Error("No latest OpenF1 session available.")

    session_key = session["session_key"]
    drivers = get_driver_lookup(session_key)
    positions = get_latest_positions(session_key)
    laps = get_latest_laps(session_key)

    race_control = []
    try:
        race_control = get_latest_race_control(session_key)
    except OpenF1Error as e:
        logger.warning("Race control feed unavailable", error=str(e))

    return {
        "session": session,
        "drivers": drivers,
        "positions": positions,
        "laps": laps,
        "race_control": race_control,
        "loaded_at": datetime.now(UTC).isoformat(),
    }


def _payload_from_signalr(snapshot: dict) -> dict:
    return {
        "source": "f1-signalr",
        "session": snapshot.get("session") or {},
        "drivers": {
            int(number): driver
            for number, driver in (snapshot.get("drivers") or {}).items()
            if str(number).isdigit()
        },
        "positions": _positions_from_signalr(snapshot),
        "laps": _laps_from_signalr(snapshot),
        "race_control": snapshot.get("race_control") or [],
        "car_data": snapshot.get("car_data") or {},
        "track_status": snapshot.get("track_status") or {},
        "weather": snapshot.get("weather") or {},
        "service": {
            "connected": snapshot.get("connected"),
            "message_count": snapshot.get("message_count"),
            "seconds_since_last_message": snapshot.get("seconds_since_last_message"),
            "error": snapshot.get("error"),
        },
        "loaded_at": datetime.now(UTC).isoformat(),
    }


def _positions_from_signalr(snapshot: dict) -> list[dict]:
    timing = snapshot.get("timing") or {}
    rows = []
    for number, data in timing.items():
        position = data.get("position")
        if position in (None, ""):
            continue
        try:
            position = int(position)
        except (TypeError, ValueError):
            continue
        rows.append({"driver_number": int(number), "position": position})
    return sorted(rows, key=lambda row: row["position"])


def _laps_from_signalr(snapshot: dict) -> list[dict]:
    timing = snapshot.get("timing") or {}
    rows = []
    for number, data in timing.items():
        rows.append(
            {
                "driver_number": int(number),
                "lap_number": None,
                "lap_duration": data.get("last_lap"),
                "duration_sector_1": None,
                "duration_sector_2": None,
                "duration_sector_3": None,
                "i1_speed": None,
                "i2_speed": None,
                "st_speed": None,
                "best_lap": data.get("best_lap"),
                "gap_to_leader": data.get("gap_to_leader"),
                "interval": data.get("interval"),
            }
        )
    return rows


@st.cache_data(ttl=4, show_spinner=False)
def _load_car_snapshot(session_key: int, driver_number: int, session: dict) -> dict | None:
    return get_latest_car_snapshot(session_key, driver_number, session=session)


def _format_seconds(value) -> str:
    if value is None or value == "":
        return "-"
    try:
        value = float(value)
    except (TypeError, ValueError):
        return str(value)

    minutes = int(value // 60)
    seconds = value - minutes * 60
    return f"{minutes}:{seconds:06.3f}" if minutes else f"{seconds:.3f}"


def _session_status(session: dict) -> str:
    if not session.get("date_start") or not session.get("date_end"):
        return "LIVE SERVICE"
    now = datetime.now(UTC)
    start = datetime.fromisoformat(session["date_start"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(session["date_end"].replace("Z", "+00:00"))
    if now < start:
        return "UPCOMING"
    if start <= now <= end:
        return "LIVE"
    return "LATEST SESSION"


def _build_timing_tower(payload: dict) -> pd.DataFrame:
    drivers = payload["drivers"]
    laps_by_driver = {
        int(lap["driver_number"]): lap
        for lap in payload["laps"]
        if lap.get("driver_number") is not None
    }

    rows = []
    for position in payload["positions"]:
        driver_number = int(position["driver_number"])
        driver = drivers.get(driver_number, {})
        lap = laps_by_driver.get(driver_number, {})

        rows.append(
            {
                "POS": int(position.get("position") or 0),
                "DRV": driver.get("name_acronym") or str(driver_number),
                "TEAM": driver.get("team_name") or "-",
                "LAP": lap.get("lap_number") or "-",
                "LAST": _format_seconds(lap.get("lap_duration")),
                "BEST": _format_seconds(lap.get("best_lap")),
                "GAP": lap.get("gap_to_leader") or "-",
                "INT": lap.get("interval") or "-",
                "S1": _format_seconds(lap.get("duration_sector_1")),
                "S2": _format_seconds(lap.get("duration_sector_2")),
                "S3": _format_seconds(lap.get("duration_sector_3")),
                "I1": lap.get("i1_speed") or "-",
                "I2": lap.get("i2_speed") or "-",
                "ST": lap.get("st_speed") or "-",
            }
        )

    return pd.DataFrame(rows).sort_values("POS")


def _render_header(payload: dict) -> None:
    session = payload["session"]
    status = _session_status(session)
    status_class = "live" if status in ("LIVE", "LIVE SERVICE") else "standby"
    source_label = payload.get("source", "openf1").upper()
    event_name = session.get("Name") or session.get("country_name") or "F1"
    session_name = session.get("session_name") or session.get("Meeting", {}).get("Name") or "Live Session"
    circuit_name = session.get("circuit_short_name") or session.get("Location") or "-"

    st.markdown(
        f"""
        <section class="live-timing-hero">
          <div>
            <span class="live-kicker">F1 Live Timing Data Layer</span>
            <h1>Official Live Timing</h1>
            <p>
              Timing tower, latest car telemetry snapshot and race-control feed.
              Direct F1 SignalR service is used when available; OpenF1 is used
              as a fallback data layer.
            </p>
          </div>
          <div class="live-session-card">
            <div class="live-status {status_class}"><span></span>{status}</div>
            <strong>{event_name}</strong>
            <small>{session_name} · {circuit_name} · {source_label}</small>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_timing_tower(payload: dict) -> None:
    st.markdown("<h2 class='section-title'>Timing Tower</h2>", unsafe_allow_html=True)
    tower = _build_timing_tower(payload)
    if tower.empty:
        st.info("No position data available yet.")
        return

    st.dataframe(
        tower,
        width="stretch",
        hide_index=True,
        key="live-timing-tower",
    )


def _render_car_snapshot(payload: dict) -> None:
    session = payload["session"]
    drivers = payload["drivers"]

    driver_options = {
        (
            f"{driver.get('name_acronym') or driver.get('tla') or number} · "
            f"{driver.get('team_name') or driver.get('team') or '-'}"
        ): int(number)
        for number, driver in sorted(drivers.items())
    }

    st.markdown("<h2 class='section-title'>Car Telemetry Snapshot</h2>", unsafe_allow_html=True)
    if not driver_options:
        st.info("No drivers available for telemetry snapshot.")
        return

    selected_label = st.selectbox(
        "Driver",
        list(driver_options.keys()),
        key="live_timing_driver",
    )
    driver_number = driver_options[selected_label]

    if payload.get("source") == "f1-signalr":
        snapshot = (payload.get("car_data") or {}).get(str(driver_number))
    else:
        session_key = int(session["session_key"])
        try:
            snapshot = _load_car_snapshot(session_key, driver_number, session)
        except OpenF1Error as e:
            st.warning(f"Car telemetry snapshot unavailable: {e}")
            return

    if not snapshot:
        st.info("No recent car telemetry snapshot available.")
        return

    cols = st.columns(5)
    metrics = [
        ("Speed", f"{snapshot.get('speed', '-')}", "km/h"),
        ("RPM", f"{snapshot.get('rpm', '-')}", ""),
        ("Throttle", f"{snapshot.get('throttle', '-')}", "%"),
        ("Brake", "ON" if snapshot.get("brake") else "OFF", ""),
        ("Gear", f"{snapshot.get('n_gear', '-')}", ""),
    ]
    for col, (label, value, unit) in zip(cols, metrics, strict=True):
        with col:
            st.markdown(
                f"""
                <div class="live-metric-card">
                  <span>{label}</span>
                  <strong>{value}</strong>
                  <small>{unit}</small>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_race_control(payload: dict) -> None:
    st.markdown("<h2 class='section-title'>Race Control</h2>", unsafe_allow_html=True)
    messages = payload.get("race_control") or []
    if not messages:
        st.info("No race-control messages available.")
        return

    for message in messages:
        st.markdown(
            f"""
            <div class="race-control-row">
              <span>{message.get('date', '-')}</span>
              <strong>{message.get('category', message.get('flag', 'MESSAGE'))}</strong>
              <p>{message.get('message', '-')}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def run_page() -> None:
    st.set_page_config(page_title="Official Live Timing – AI Race Engineer", layout="wide")

    apply_dark_page_shell()
    load_css()
    navbar()

    st.caption(
        "Live source priority: local F1 SignalR backend service first, OpenF1 fallback second."
    )

    col_refresh, col_loaded = st.columns([1, 3])
    with col_refresh:
        if st.button("Refresh feed", key="live_timing_refresh"):
            st.cache_data.clear()
            st.rerun()

    try:
        payload = _load_live_timing_payload()
    except OpenF1Error as e:
        st.error(f"Live timing feed unavailable: {e}")
        return

    with col_loaded:
        service = payload.get("service")
        extra = ""
        if service:
            extra = (
                f" · SignalR connected={service.get('connected')} "
                f"messages={service.get('message_count')} "
                f"last={service.get('seconds_since_last_message')}s"
            )
        st.caption(f"Loaded at UTC: {payload['loaded_at']}{extra}")

    _render_header(payload)
    _render_timing_tower(payload)
    _render_car_snapshot(payload)
    _render_race_control(payload)
