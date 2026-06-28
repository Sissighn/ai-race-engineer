import os
from datetime import UTC, datetime

import pandas as pd
import plotly.graph_objects as go
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

TYRE_LABELS = {
    "SOFT": "S",
    "MEDIUM": "M",
    "HARD": "H",
    "INTERMEDIATE": "I",
    "WET": "W",
    "UNKNOWN": "-",
}

LIVE_TIMING_BROWSER_SIGNALR_URL = os.getenv(
    "LIVE_TIMING_BROWSER_SIGNALR_URL",
    "http://localhost:8765",
)


@st.cache_data(ttl=2, show_spinner=False)
def _load_live_timing_payload() -> dict:
    try:
        signalr_payload = get_signalr_snapshot()
        if signalr_payload.get("connected") or signalr_payload.get("message_count", 0) > 0:
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
        "tyres": {},
        "car_data": {},
        "positions_xyz": {},
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
        "penalties": snapshot.get("penalties") or {},
        "car_data": snapshot.get("car_data") or {},
        "positions_xyz": snapshot.get("positions") or {},
        "tyres": snapshot.get("tyres") or {},
        "lap_count": snapshot.get("lap_count") or {},
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


def _driver_code(driver: dict, fallback: int | str) -> str:
    return driver.get("name_acronym") or driver.get("tla") or driver.get("Tla") or str(fallback)


def _driver_team(driver: dict) -> str:
    return driver.get("team_name") or driver.get("team") or "-"


def _team_colour(driver: dict) -> str:
    colour = driver.get("team_colour") or driver.get("team_color") or "888888"
    colour = str(colour).lstrip("#")
    return f"#{colour}" if len(colour) in (3, 6) else "#888888"


def _session_kind(payload: dict) -> str:
    session = payload.get("session") or {}
    text = " ".join(
        str(session.get(key, "")) for key in ("session_type", "session_name", "Name", "Meeting")
    ).lower()
    if "qualifying" in text or text in {"q", "sq"}:
        return "qualifying"
    if "race" in text or text == "r":
        return "race"
    return "race"


def _tyre_short(tyre: dict | None) -> str:
    if not tyre:
        return "-"
    compound = str(tyre.get("compound") or tyre.get("Compound") or "").upper()
    return TYRE_LABELS.get(compound, compound[:1] or "-")


def _tyre_class(tyre: dict | None) -> str:
    if not tyre:
        return "unknown"
    compound = str(tyre.get("compound") or tyre.get("Compound") or "unknown").lower()
    return compound.replace(" ", "-")


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


def _session_event_name(session: dict) -> str:
    meeting = session.get("Meeting") if isinstance(session.get("Meeting"), dict) else {}
    return (
        meeting.get("Name")
        or session.get("meeting_name")
        or session.get("event_name")
        or session.get("country_name")
        or session.get("Name")
        or "F1 Grand Prix"
    )


def _session_label(session: dict) -> str:
    return (
        session.get("session_name")
        or session.get("Type")
        or session.get("Name")
        or session.get("NameShort")
        or "Live Session"
    )


def _session_circuit_name(session: dict) -> str:
    meeting = session.get("Meeting") if isinstance(session.get("Meeting"), dict) else {}
    circuit = meeting.get("Circuit") if isinstance(meeting.get("Circuit"), dict) else {}
    return (
        session.get("circuit_short_name")
        or circuit.get("ShortName")
        or session.get("Location")
        or meeting.get("Location")
        or "-"
    )


def _display_current_lap(lap_count: dict) -> int | str:
    current = lap_count.get("CurrentLap")
    try:
        return int(current)
    except (TypeError, ValueError):
        return current or "--"


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


def _build_classification_rows(payload: dict) -> list[dict]:
    drivers = payload.get("drivers") or {}
    tyres = payload.get("tyres") or {}
    car_data = payload.get("car_data") or {}
    laps_by_driver = {
        int(lap["driver_number"]): lap
        for lap in payload.get("laps", [])
        if lap.get("driver_number") is not None
    }

    rows = []
    for position in payload.get("positions", []):
        driver_number = int(position["driver_number"])
        driver = drivers.get(driver_number, {})
        lap = laps_by_driver.get(driver_number, {})
        timing_status = lap.get("status") or lap.get("in_pit") or ""
        tyre = tyres.get(str(driver_number)) or tyres.get(driver_number) or {}
        car = car_data.get(str(driver_number)) or car_data.get(driver_number) or {}

        rows.append(
            {
                "position": int(position.get("position") or 0),
                "driver_number": driver_number,
                "code": _driver_code(driver, driver_number),
                "team": _driver_team(driver),
                "team_colour": _team_colour(driver),
                "tyre": _tyre_short(tyre),
                "tyre_class": _tyre_class(tyre),
                "tyre_laps": tyre.get("total_laps") or "-",
                "lap": lap.get("lap_number") or "-",
                "last": _format_seconds(lap.get("lap_duration")),
                "best": _format_seconds(lap.get("best_lap")),
                "gap": lap.get("gap_to_leader") or "-",
                "interval": lap.get("interval") or "-",
                "q1": _format_seconds(lap.get("q1")),
                "q2": _format_seconds(lap.get("q2")),
                "q3": _format_seconds(lap.get("q3")),
                "status": "PIT" if timing_status is True else timing_status or "-",
                "speed": car.get("speed") or "-",
            }
        )

    return sorted(rows, key=lambda row: row["position"])


def _render_header(payload: dict) -> None:
    session = payload["session"]
    status = _session_status(session)
    status_class = "live" if status in ("LIVE", "LIVE SERVICE") else "standby"
    event_name = _session_event_name(session)
    session_name = _session_label(session)
    circuit_name = _session_circuit_name(session)

    st.markdown(
        f"""
        <section class="live-timing-hero">
          <div>
            <span class="live-kicker">F1 Pit Wall</span>
            <h1>Official Live Timing</h1>
            <p>
              Live classification, car telemetry and race-control messages in one
              race operations view.
            </p>
          </div>
          <div class="live-session-card">
            <div class="live-status {status_class}"><span></span>{status}</div>
            <strong>{event_name}</strong>
            <small>{session_name} · {circuit_name}</small>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_timing_tower(payload: dict) -> None:
    rows = _build_classification_rows(payload)
    if not rows:
        st.info("No classification data available yet.")
        return

    kind = _session_kind(payload)
    title = "Race Classification" if kind == "race" else "Qualifying Classification"
    header_cells = (
        "<span>POS</span><span>DRV</span><span>TYRE</span><span>LAP</span>"
        "<span>GAP</span><span>INT</span><span>LAST</span>"
        if kind == "race"
        else "<span>POS</span><span>DRV</span><span>TYRE</span><span>BEST</span>"
        "<span>Q1</span><span>Q2</span><span>Q3</span><span>STATUS</span>"
    )
    row_class = "race" if kind == "race" else "quali"

    html_rows = []
    for row in rows[:22]:
        if kind == "race":
            cells = (
                f"<span>{row['position']}</span>"
                f"<span class='driver-code' style='border-left-color:{row['team_colour']}'>{row['code']}</span>"
                f"<span><b class='tyre {row['tyre_class']}'>{row['tyre']}</b><small>{row['tyre_laps']}</small></span>"
                f"<span>{row['lap']}</span>"
                f"<span>{row['gap']}</span>"
                f"<span>{row['interval']}</span>"
                f"<span>{row['last']}</span>"
            )
        else:
            cells = (
                f"<span>{row['position']}</span>"
                f"<span class='driver-code' style='border-left-color:{row['team_colour']}'>{row['code']}</span>"
                f"<span><b class='tyre {row['tyre_class']}'>{row['tyre']}</b><small>{row['tyre_laps']}</small></span>"
                f"<span>{row['best']}</span>"
                f"<span>{row['q1']}</span>"
                f"<span>{row['q2']}</span>"
                f"<span>{row['q3']}</span>"
                f"<span>{row['status']}</span>"
            )
        html_rows.append(f"<div class='classification-row {row_class}'>{cells}</div>")

    st.markdown(
        f"""
        <section class="classification-tower">
          <div class="tower-title">{title}</div>
          <div class="classification-header {row_class}">{header_cells}</div>
          {"".join(html_rows)}
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_live_track(payload: dict) -> None:
    positions = payload.get("positions_xyz") or {}
    drivers = payload.get("drivers") or {}
    if not positions:
        st.markdown(
            """
            <section class="live-track-empty">
              <strong>Live track position feed waiting</strong>
              <span>Position.z data will populate here during an active session.</span>
            </section>
            """,
            unsafe_allow_html=True,
        )
        return

    xs, ys, labels, colours, hover = [], [], [], [], []
    for number, pos in positions.items():
        x = pos.get("x")
        y = pos.get("y")
        if x is None or y is None:
            continue
        try:
            x = float(x)
            y = float(y)
        except (TypeError, ValueError):
            continue
        driver = drivers.get(int(number), {})
        xs.append(x)
        ys.append(y)
        labels.append(_driver_code(driver, number))
        colours.append(_team_colour(driver))
        hover.append(
            f"{_driver_code(driver, number)}<br>{_driver_team(driver)}<br>Status: {pos.get('status', '-')}"
        )

    if not xs:
        st.info("Position feed is connected but has no plottable car coordinates yet.")
        return

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=xs,
            y=ys,
            mode="markers+text",
            marker=dict(size=18, color=colours, line=dict(color="#ffffff", width=1.4)),
            text=labels,
            textposition="top center",
            hovertext=hover,
            hovertemplate="<b>%{hovertext}</b><extra></extra>",
        )
    )
    fig.update_layout(
        paper_bgcolor="#0f1117",
        plot_bgcolor="#0f1117",
        height=640,
        margin=dict(l=8, r=8, t=42, b=8),
        title=dict(text="Live Track Position", x=0.5, font=dict(color="#ffffff")),
        font=dict(color="#ffffff"),
        showlegend=False,
    )
    fig.update_xaxes(visible=False, showgrid=False, zeroline=False)
    fig.update_yaxes(visible=False, showgrid=False, zeroline=False, scaleanchor="x")
    st.plotly_chart(
        fig,
        width="stretch",
        key="signalr-live-position-map",
        config={"displayModeBar": False, "responsive": True, "scrollZoom": False},
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
              <span>{message.get("date", "-")}</span>
              <strong>{message.get("category", message.get("flag", "MESSAGE"))}</strong>
              <p>{message.get("message", "-")}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _build_legacy_live_timing_component_html(service_url: str, poll_ms: int = 2000) -> str:
    safe_url = service_url.rstrip("/")
    return f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0f1117;
      --panel: #080a0f;
      --panel-2: #111319;
      --line: rgba(216, 221, 231, 0.12);
      --red: #7d0e0e;
      --text: #ffffff;
      --muted: #aeb4be;
      --green: #30ff8a;
      --amber: #ffb000;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: #191919;
      color: var(--text);
      font-family: Inter, Arial, sans-serif;
      overflow: hidden;
    }}
    .shell {{ display: grid; gap: 18px; }}
    .hero {{
      display: flex;
      justify-content: space-between;
      gap: 24px;
      align-items: stretch;
      padding: 28px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background:
        linear-gradient(135deg, rgba(125, 14, 14, 0.26), transparent 42%),
        linear-gradient(90deg, rgba(255, 255, 255, 0.04), transparent),
        var(--bg);
    }}
    .kicker {{
      display: block;
      margin-bottom: 8px;
      color: #ff4b4b;
      font-family: Tektur, Inter, sans-serif;
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.16em;
      text-transform: uppercase;
    }}
    h1 {{
      margin: 0 0 8px 0;
      font-family: Tektur, Inter, sans-serif;
      font-size: clamp(34px, 5vw, 68px);
      line-height: 0.95;
    }}
    .hero p {{
      max-width: 820px;
      margin: 0;
      color: #c8cdd6;
    }}
    .session-card {{
      min-width: 280px;
      display: flex;
      flex-direction: column;
      justify-content: center;
      gap: 8px;
      padding: 18px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #12161f;
    }}
    .status {{
      display: flex;
      align-items: center;
      gap: 8px;
      font-family: Tektur, Inter, sans-serif;
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }}
    .status-dot {{
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: var(--amber);
      box-shadow: 0 0 14px rgba(255, 176, 0, 0.65);
    }}
    .status.live .status-dot {{
      background: var(--green);
      box-shadow: 0 0 14px rgba(48, 255, 138, 0.85);
    }}
    .session-card strong {{
      font-family: Tektur, Inter, sans-serif;
      font-size: 22px;
    }}
    .session-card small {{ color: var(--muted); }}
    .meta {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      color: var(--muted);
      font-size: 13px;
      min-height: 20px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: minmax(380px, 0.92fr) minmax(0, 2.08fr);
      gap: 22px;
      align-items: start;
    }}
    .tower {{
      overflow: hidden;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      box-shadow: 0 0 28px rgba(0, 0, 0, 0.32);
    }}
    .tower-title {{
      padding: 12px 14px;
      background: var(--red);
      font-family: Tektur, Inter, sans-serif;
      font-size: 14px;
      font-weight: 800;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .tower-header,
    .tower-row {{
      display: grid;
      align-items: center;
      gap: 6px;
    }}
    .tower-header.race,
    .tower-row.race {{
      grid-template-columns: 34px minmax(48px, 0.8fr) 48px 42px 62px 58px 72px;
    }}
    .tower-header.quali,
    .tower-row.quali {{
      grid-template-columns: 34px minmax(48px, 0.8fr) 48px 74px 64px 64px 64px 56px;
    }}
    .tower-header {{
      padding: 8px 10px;
      background: #151923;
      color: #8f98a8;
      font-family: Tektur, Inter, sans-serif;
      font-size: 10px;
      font-weight: 800;
      letter-spacing: 0.06em;
    }}
    .tower-row {{
      min-height: 38px;
      padding: 7px 10px;
      border-top: 1px solid rgba(255, 255, 255, 0.06);
      font-family: Tektur, Inter, sans-serif;
      font-size: 12px;
      background: #0d1017;
      transition: background 120ms linear;
    }}
    .tower-row:nth-child(odd) {{ background: #10141d; }}
    .driver-code {{
      padding-left: 8px;
      border-left: 4px solid #888888;
      font-weight: 900;
    }}
    .tyre {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 22px;
      height: 22px;
      border-radius: 50%;
      background: #3d4350;
      color: #fff;
      font-size: 11px;
      font-weight: 900;
    }}
    .tyre.soft {{ background: #e10600; }}
    .tyre.medium {{ background: #ffd12e; color: #101010; }}
    .tyre.hard {{ background: #f5f5f5; color: #101010; }}
    .tyre.intermediate {{ background: #39b54a; }}
    .tyre.wet {{ background: #1f7cff; }}
    .tyre-wrap small {{
      display: inline-block;
      margin-left: 4px;
      color: #8f98a8;
    }}
    .track-panel {{
      min-height: 640px;
      position: relative;
      overflow: hidden;
      border: 1px solid var(--line);
      border-radius: 8px;
      background:
        repeating-linear-gradient(90deg, rgba(255,255,255,0.035) 0, rgba(255,255,255,0.035) 1px, transparent 1px, transparent 64px),
        #0f1117;
    }}
    .track-title {{
      position: absolute;
      top: 14px;
      left: 0;
      right: 0;
      text-align: center;
      font-family: Tektur, Inter, sans-serif;
      font-weight: 800;
      z-index: 2;
    }}
    .track-empty {{
      height: 640px;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 8px;
      color: #d8dde7;
      text-align: center;
    }}
    .track-empty span {{ color: #8f98a8; }}
    svg {{
      width: 100%;
      height: 640px;
      display: block;
    }}
    .car-label {{
      font-family: Tektur, Inter, sans-serif;
      font-size: 12px;
      font-weight: 900;
      fill: #ffffff;
      paint-order: stroke;
      stroke: #080a0f;
      stroke-width: 4px;
      stroke-linejoin: round;
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 12px;
    }}
    .metric-card {{
      min-height: 104px;
      padding: 16px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel-2);
    }}
    .metric-card span,
    .metric-card small {{
      display: block;
      color: var(--muted);
      font-family: Tektur, Inter, sans-serif;
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .metric-card strong {{
      display: block;
      margin-top: 8px;
      font-family: Tektur, Inter, sans-serif;
      font-size: 34px;
      line-height: 1;
    }}
    .race-control {{
      display: grid;
      gap: 10px;
    }}
    .race-row {{
      padding: 14px 16px;
      border-left: 3px solid var(--red);
      border-radius: 6px;
      background: var(--panel-2);
    }}
    .race-row span {{
      color: var(--muted);
      font-size: 12px;
    }}
    .race-row strong {{
      display: block;
      margin: 4px 0;
      font-family: Tektur, Inter, sans-serif;
    }}
    .race-row p {{
      margin: 0;
      color: #d8dde7;
    }}
    .section-title {{
      margin: 26px 0 12px;
      font-family: Tektur, Inter, sans-serif;
      font-size: 24px;
      font-weight: 800;
    }}
    .service-hint {{
      max-width: 720px;
      padding: 18px 20px;
      border: 1px solid rgba(255, 176, 0, 0.38);
      border-radius: 8px;
      background: rgba(255, 176, 0, 0.08);
      color: #f1d28a;
      line-height: 1.5;
    }}
    .service-hint code {{
      display: inline-block;
      margin-top: 8px;
      padding: 4px 7px;
      border-radius: 4px;
      background: rgba(0, 0, 0, 0.35);
      color: #ffffff;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 12px;
    }}
    @media (max-width: 980px) {{
      .hero {{ flex-direction: column; }}
      .grid {{ grid-template-columns: 1fr; }}
      .cards {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      body {{ overflow: auto; }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <div class="meta">
      <span>Race control, timing and telemetry</span>
      <span id="loadedAt">Waiting for first snapshot</span>
    </div>
    <section class="hero">
      <div>
        <span class="kicker">F1 Pit Wall</span>
        <h1>Official Live Timing</h1>
        <p>Live classification, track position, car telemetry and race-control messages in one race operations view.</p>
      </div>
      <div class="session-card">
        <div id="status" class="status"><span class="status-dot"></span><span id="statusText">CONNECTING</span></div>
        <strong id="eventName">F1</strong>
        <small id="sessionName">Waiting for session data</small>
      </div>
    </section>

    <section class="grid">
      <div class="tower">
        <div id="towerTitle" class="tower-title">Race Classification</div>
        <div id="towerHeader" class="tower-header race"></div>
        <div id="towerRows"></div>
      </div>
      <div id="trackPanel" class="track-panel">
        <div class="track-title">Live Track Position</div>
        <div class="track-empty"><strong>Waiting for Position.z</strong><span>Cars will appear during an active session.</span></div>
      </div>
    </section>

    <div class="section-title">Car Telemetry Snapshot</div>
    <section id="metricCards" class="cards"></section>

    <div class="section-title">Race Control</div>
    <section id="raceControl" class="race-control"></section>
  </main>

  <script>
    const CONFIGURED_SERVICE_URL = {safe_url!r};
    const POLL_MS = {int(poll_ms)};
    const TYRES = {{SOFT: "S", MEDIUM: "M", HARD: "H", INTERMEDIATE: "I", WET: "W"}};
    const state = {{ lastSnapshot: null, lastDriver: null, serviceUrl: null, failures: 0, offlineRendered: false }};

    function unique(values) {{
      return [...new Set(values.filter(Boolean).map(value => value.replace(new RegExp("/$"), "")))];
    }}

    function serviceUrlCandidates() {{
      const urls = [CONFIGURED_SERVICE_URL];
      try {{
        const configured = new URL(CONFIGURED_SERVICE_URL);
        const port = configured.port || "8765";
        if (["localhost", "127.0.0.1", "0.0.0.0"].includes(configured.hostname)) {{
          urls.push(`${{configured.protocol}}//127.0.0.1:${{port}}`);
          urls.push(`${{configured.protocol}}//localhost:${{port}}`);
          if (window.location.hostname && !["localhost", "127.0.0.1"].includes(window.location.hostname)) {{
            urls.push(`${{configured.protocol}}//${{window.location.hostname}}:${{port}}`);
          }}
        }}
      }} catch (_error) {{
        // Keep the configured URL as the only candidate.
      }}
      return unique(urls);
    }}

    const SERVICE_URLS = serviceUrlCandidates();

    function esc(value) {{
      return String(value ?? "-").replace(/[&<>"']/g, ch => ({{
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
      }}[ch]));
    }}

    function teamColor(driver) {{
      const raw = String(driver?.team_colour || driver?.team_color || "888888").replace("#", "");
      return raw.length === 3 || raw.length === 6 ? "#" + raw : "#888888";
    }}

    function code(driver, fallback) {{
      return driver?.name_acronym || driver?.tla || driver?.Tla || String(fallback);
    }}

    function team(driver) {{
      return driver?.team_name || driver?.team || "-";
    }}

    function formatTime(value) {{
      if (value === undefined || value === null || value === "") return "-";
      const num = Number(value);
      if (!Number.isFinite(num)) return String(value);
      const minutes = Math.floor(num / 60);
      const seconds = num - minutes * 60;
      return minutes ? `${{minutes}}:${{seconds.toFixed(3).padStart(6, "0")}}` : seconds.toFixed(3);
    }}

    function sessionKind(snapshot) {{
      const session = snapshot.session || {{}};
      const text = `${{session.session_type || ""}} ${{session.session_name || ""}} ${{session.Name || ""}}`.toLowerCase();
      return text.includes("qualifying") || text === "q" || text.includes("sprint shootout") ? "quali" : "race";
    }}

    function tyreInfo(snapshot, driverNumber) {{
      const tyre = (snapshot.tyres || {{}})[String(driverNumber)] || {{}};
      const compound = String(tyre.compound || tyre.Compound || "").toUpperCase();
      return {{
        short: TYRES[compound] || compound.slice(0, 1) || "-",
        cls: compound.toLowerCase().replace(/\\s+/g, "-") || "unknown",
        laps: tyre.total_laps || tyre.TotalLaps || "-"
      }};
    }}
    function displayRaceLap(lap) {{
      const current = Number(lap?.CurrentLap);
      if (!Number.isFinite(current)) return "--";
      return current;
    }}

    function rowsFromSnapshot(snapshot) {{
      const timing = snapshot.timing || {{}};
      const drivers = snapshot.drivers || {{}};
      return Object.entries(timing)
        .map(([number, row]) => {{
          const position = Number(row.position || 99);
          const driver = drivers[String(number)] || {{}};
          const tyre = tyreInfo(snapshot, number);
          return {{
            number,
            position,
            code: code(driver, number),
            team: team(driver),
            color: teamColor(driver),
            tyre,
            lap: row.lap_number || "-",
            last: formatTime(row.last_lap),
            best: formatTime(row.best_lap),
            gap: row.gap_to_leader || "-",
            interval: row.interval || "-",
            q1: formatTime(row.q1),
            q2: formatTime(row.q2),
            q3: formatTime(row.q3),
            status: row.in_pit === true ? "PIT" : (row.status || "-"),
          }};
        }})
        .filter(row => Number.isFinite(row.position))
        .sort((a, b) => a.position - b.position)
        .slice(0, 22);
    }}

    function renderTower(snapshot) {{
      const kind = sessionKind(snapshot);
      const rows = rowsFromSnapshot(snapshot);
      const header = document.getElementById("towerHeader");
      const body = document.getElementById("towerRows");
      document.getElementById("towerTitle").textContent = kind === "race" ? "Race Classification" : "Qualifying Classification";
      header.className = `tower-header ${{kind}}`;
      header.innerHTML = kind === "race"
        ? "<span>POS</span><span>DRV</span><span>TYRE</span><span>LAP</span><span>GAP</span><span>INT</span><span>LAST</span>"
        : "<span>POS</span><span>DRV</span><span>TYRE</span><span>BEST</span><span>Q1</span><span>Q2</span><span>Q3</span><span>STATUS</span>";

      if (!rows.length) {{
        body.innerHTML = `<div class="tower-row race"><span>-</span><span>Waiting for TimingData</span></div>`;
        return;
      }}

      body.innerHTML = rows.map(row => {{
        const tyre = `<span class="tyre-wrap"><b class="tyre ${{esc(row.tyre.cls)}}">${{esc(row.tyre.short)}}</b><small>${{esc(row.tyre.laps)}}</small></span>`;
        const driver = `<span class="driver-code" style="border-left-color:${{esc(row.color)}}">${{esc(row.code)}}</span>`;
        if (kind === "race") {{
          return `<div class="tower-row race"><span>${{row.position}}</span>${{driver}}<span>${{tyre}}</span><span>${{esc(row.lap)}}</span><span>${{esc(row.gap)}}</span><span>${{esc(row.interval)}}</span><span>${{esc(row.last)}}</span></div>`;
        }}
        return `<div class="tower-row quali"><span>${{row.position}}</span>${{driver}}<span>${{tyre}}</span><span>${{esc(row.best)}}</span><span>${{esc(row.q1)}}</span><span>${{esc(row.q2)}}</span><span>${{esc(row.q3)}}</span><span>${{esc(row.status)}}</span></div>`;
      }}).join("");
    }}

    function renderTrack(snapshot) {{
      const positions = snapshot.positions || {{}};
      const drivers = snapshot.drivers || {{}};
      const entries = Object.entries(positions)
        .map(([number, pos]) => ({{
          number,
          x: Number(pos.x),
          y: Number(pos.y),
          status: pos.status || "-",
          driver: drivers[String(number)] || {{}}
        }}))
        .filter(pos => Number.isFinite(pos.x) && Number.isFinite(pos.y));

      const panel = document.getElementById("trackPanel");
      if (!entries.length) {{
        panel.innerHTML = `<div class="track-title">Live Track Position</div><div class="track-empty"><strong>Waiting for Position.z</strong><span>Cars will appear during an active session.</span></div>`;
        return;
      }}

      const minX = Math.min(...entries.map(e => e.x));
      const maxX = Math.max(...entries.map(e => e.x));
      const minY = Math.min(...entries.map(e => e.y));
      const maxY = Math.max(...entries.map(e => e.y));
      const spanX = Math.max(maxX - minX, 1);
      const spanY = Math.max(maxY - minY, 1);
      const padX = spanX * 0.12;
      const padY = spanY * 0.12;
      const viewBox = `${{minX - padX}} ${{minY - padY}} ${{spanX + padX * 2}} ${{spanY + padY * 2}}`;

      const cars = entries.map(e => {{
        const c = teamColor(e.driver);
        const label = esc(code(e.driver, e.number));
        return `<g><circle cx="${{e.x}}" cy="${{e.y}}" r="${{Math.max(spanX, spanY) * 0.018}}" fill="${{c}}" stroke="#fff" stroke-width="${{Math.max(spanX, spanY) * 0.004}}"></circle><text class="car-label" x="${{e.x}}" y="${{e.y - Math.max(spanX, spanY) * 0.035}}" text-anchor="middle">${{label}}</text></g>`;
      }}).join("");

      panel.innerHTML = `<div class="track-title">Live Track Position</div><svg viewBox="${{viewBox}}" preserveAspectRatio="xMidYMid meet">${{cars}}</svg>`;
    }}

    function renderMetrics(snapshot) {{
      const carData = snapshot.car_data || {{}};
      const timingRows = rowsFromSnapshot(snapshot);
      const selected = state.lastDriver && carData[state.lastDriver] ? state.lastDriver : (timingRows[0]?.number || Object.keys(carData)[0]);
      state.lastDriver = selected;
      const car = carData[String(selected)] || {{}};
      const driver = (snapshot.drivers || {{}})[String(selected)] || {{}};
      const metrics = [
        ["Driver", code(driver, selected), team(driver)],
        ["Speed", car.speed ?? "-", "km/h"],
        ["RPM", car.rpm ?? "-", ""],
        ["Throttle", car.throttle ?? "-", "%"],
        ["Brake", car.brake ? "ON" : "OFF", ""],
      ];
      document.getElementById("metricCards").innerHTML = metrics.map(([label, value, unit]) => `<div class="metric-card"><span>${{esc(label)}}</span><strong>${{esc(value)}}</strong><small>${{esc(unit)}}</small></div>`).join("");
    }}

    function renderRaceControl(snapshot) {{
      const messages = (snapshot.race_control || []).slice(-8).reverse();
      const target = document.getElementById("raceControl");
      if (!messages.length) {{
        target.innerHTML = `<div class="race-row"><strong>No race-control messages available</strong><p>Waiting for RaceControlMessages.</p></div>`;
        return;
      }}
      target.innerHTML = messages.map(msg => `<div class="race-row"><span>${{esc(msg.date || "-")}}</span><strong>${{esc(msg.category || msg.flag || "MESSAGE")}}</strong><p>${{esc(msg.message || "-")}}</p></div>`).join("");
    }}

    function renderHeader(snapshot) {{
      const session = snapshot.session || {{}};
      const connected = Boolean(snapshot.connected);
      const status = document.getElementById("status");
      status.className = connected ? "status live" : "status";
      document.getElementById("statusText").textContent = connected ? "LIVE SERVICE" : "WAITING";
      document.getElementById("eventName").textContent = session.Name || session.country_name || "F1";
      document.getElementById("sessionName").textContent = `${{session.session_name || session.Meeting?.Name || "Live timing"}} · Race operations`;
      document.getElementById("loadedAt").textContent = `messages=${{snapshot.message_count || 0}} · last=${{snapshot.seconds_since_last_message ?? "-"}}s`;
    }}

    function render(snapshot) {{
      state.lastSnapshot = snapshot;
      state.failures = 0;
      state.offlineRendered = false;
      renderHeader(snapshot);
      renderTower(snapshot);
      renderTrack(snapshot);
      renderMetrics(snapshot);
      renderRaceControl(snapshot);
    }}

    function setOfflineStatus(error) {{
      state.failures += 1;
      const status = document.getElementById("status");
      status.className = "status";
      document.getElementById("statusText").textContent = state.lastSnapshot ? "RECONNECTING" : "SERVICE OFFLINE";
      document.getElementById("loadedAt").textContent = state.lastSnapshot
        ? `Connection retry ${{state.failures}} · keeping last snapshot`
        : `Waiting for live timing · retry ${{state.failures}}`;

      if (state.lastSnapshot || state.offlineRendered) return;
      state.offlineRendered = true;
      document.getElementById("towerRows").innerHTML = "";
      document.getElementById("metricCards").innerHTML = "";
      document.getElementById("raceControl").innerHTML = "";
      document.getElementById("trackPanel").innerHTML = `
        <div class="track-title">Live Track Position</div>
        <div class="track-empty">
          <div class="service-hint">
            <strong>Live timing is not connected yet.</strong><br>
            Keep this page open while the session feed initializes.
          </div>
        </div>`;
    }}

    async function fetchSnapshot(url) {{
      const controller = new AbortController();
      const timeout = window.setTimeout(() => controller.abort(), 1600);
      try {{
        const response = await fetch(`${{url}}/snapshot`, {{
          cache: "no-store",
          signal: controller.signal,
        }});
        if (!response.ok) throw new Error(`HTTP ${{response.status}}`);
        return await response.json();
      }} finally {{
        window.clearTimeout(timeout);
      }}
    }}

    async function poll() {{
      const candidates = state.serviceUrl ? [state.serviceUrl, ...SERVICE_URLS] : SERVICE_URLS;
      let lastError = new Error("No SignalR service URL configured");
      for (const url of unique(candidates)) {{
        try {{
          const snapshot = await fetchSnapshot(url);
          state.serviceUrl = url;
          render(snapshot);
          return;
        }} catch (error) {{
          lastError = error;
        }}
      }}
      setOfflineStatus(lastError);
    }}

    poll();
    window.setInterval(poll, POLL_MS);
  </script>
</body>
</html>
"""


def _build_reference_timing_wall_html(service_url: str, poll_ms: int = 2000) -> str:
    safe_url = service_url.rstrip("/")
    template = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <style>
    :root {
      color-scheme: dark;
      --bg: #0b1220;
      --bg-2: #101a2d;
      --row: #10182a;
      --row-alt: #172238;
      --header: #243f99;
      --grid: rgba(219, 230, 255, 0.24);
      --text: #f6f8ff;
      --muted: #7d8ba7;
      --green: #00c957;
      --purple: #a000ff;
      --yellow: #d38a00;
      --red: #f0143c;
      --orange: #ff7a00;
      --blue: #3b82f6;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Tektur, Inter, Arial, sans-serif;
      overflow: hidden;
    }
    .wall {
      min-height: 100vh;
      background:
        linear-gradient(180deg, rgba(255,255,255,0.035), transparent 140px),
        var(--bg);
      border: 1px solid rgba(255,255,255,0.08);
    }
    .top-nav {
      height: 56px;
      display: flex;
      align-items: center;
      gap: 28px;
      padding: 0 22px;
      background: #0a1324;
      border-bottom: 1px solid rgba(255,255,255,0.07);
      white-space: nowrap;
    }
    .signal {
      width: 38px;
      height: 38px;
      border-radius: 50%;
      background:
        conic-gradient(#58b65c 0 25%, #467ad8 0 50%, #ffd23f 0 75%, #ef233c 0);
      position: relative;
      box-shadow: inset 0 0 0 2px rgba(255,255,255,0.22);
    }
    .signal::after {
      content: "";
      position: absolute;
      left: 17px;
      top: 5px;
      width: 3px;
      height: 28px;
      background: rgba(255,255,255,0.86);
      transform: rotate(45deg);
      transform-origin: 50% 75%;
    }
    .nav-tab {
      padding: 9px 12px;
      border-radius: 4px;
      color: #f5f7fb;
      font-size: 20px;
      font-weight: 900;
    }
    .nav-tab.active { background: rgba(255,255,255,0.08); }
    .nav-spacer { flex: 1; }
    .pause {
      font-size: 26px;
      line-height: 1;
      opacity: 0.95;
    }
    .counter {
      min-width: 58px;
      padding: 7px 16px;
      border-radius: 10px;
      background: #f1f2f4;
      color: #111827;
      text-align: center;
      font-size: 20px;
      font-weight: 900;
    }
    .gear,
    .user {
      width: 28px;
      height: 28px;
      border: 3px solid #f3f6ff;
      border-radius: 50%;
      opacity: 0.95;
    }
    .user { border-radius: 45% 45% 35% 35%; }
    .session-bar {
      min-height: 72px;
      display: grid;
      grid-template-columns: minmax(280px, 1fr) auto auto auto;
      align-items: center;
      gap: 22px;
      padding: 12px 22px;
      background: #0d1730;
      border-bottom: 2px solid rgba(229, 237, 255, 0.35);
    }
    .event {
      display: flex;
      align-items: center;
      gap: 14px;
      min-width: 0;
    }
    .flag {
      width: 58px;
      height: 40px;
      border-radius: 6px;
      background: linear-gradient(#ef233c 0 50%, #fff 50%);
      box-shadow: inset 0 0 0 1px rgba(255,255,255,0.22);
      flex: 0 0 auto;
    }
    .event-title {
      min-width: 0;
      font-size: clamp(22px, 3vw, 34px);
      font-weight: 950;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .weather {
      display: flex;
      gap: 20px;
      color: #f2f5ff;
      font-size: 23px;
      font-weight: 950;
    }
    .weather span small {
      margin-left: 4px;
      color: #8591a8;
      font-size: 12px;
      letter-spacing: 0.08em;
    }
    .mode {
      padding: 12px 18px;
      border-radius: 8px;
      background: linear-gradient(135deg, #ff2b3d, #ff7a00);
      font-size: 22px;
      font-weight: 950;
    }
    .lap-status {
      display: flex;
      align-items: center;
      gap: 20px;
      font-size: 28px;
      font-weight: 950;
    }
    .lap-status small {
      color: #76839b;
      font-size: 13px;
      letter-spacing: 0.08em;
    }
    .track-state {
      min-width: 170px;
      padding: 12px 18px;
      border-radius: 8px;
      background: #00a642;
      text-align: center;
      color: white;
      font-size: 22px;
      font-weight: 950;
    }
    .track-state.yellow { background: #d69b00; color: #151515; }
    .track-state.red { background: #cc1735; }
    .track-state.sc { background: #f5c400; color: #101010; }
    .table-wrap {
      overflow: auto;
      height: calc(100vh - 160px);
      background: var(--bg);
    }
    table {
      width: 100%;
      min-width: 1640px;
      border-collapse: separate;
      border-spacing: 0;
      table-layout: fixed;
      font-variant-numeric: tabular-nums;
    }
    thead th {
      position: sticky;
      top: 0;
      z-index: 3;
      height: 48px;
      padding: 9px 10px;
      background: var(--header);
      border-right: 1px solid rgba(230,238,255,0.22);
      border-bottom: 1px solid rgba(230,238,255,0.35);
      color: #eef3ff;
      font-size: 17px;
      font-weight: 950;
      text-align: left;
      letter-spacing: 0.02em;
    }
    tbody tr { background: var(--row); }
    tbody tr:nth-child(odd) { background: var(--row-alt); }
    tbody td {
      height: 38px;
      padding: 5px 9px;
      border-right: 1px solid var(--grid);
      border-bottom: 1px solid rgba(255,255,255,0.03);
      overflow: hidden;
      white-space: nowrap;
      text-overflow: ellipsis;
      font-size: 20px;
      font-weight: 900;
      line-height: 1;
    }
    .col-pit { width: 72px; text-align: center; }
    .col-driver { width: 210px; }
    .col-interval { width: 130px; }
    .col-tyre { width: 112px; }
    .col-best { width: 150px; }
    .col-leader { width: 125px; }
    .col-last { width: 145px; }
    .col-mini { width: 245px; }
    .col-last-sectors { width: 285px; }
    .col-best-sectors { width: 305px; }
    .pit-badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 54px;
      height: 30px;
      border-radius: 6px;
      background: #a91d80;
      color: #050812;
      font-weight: 950;
    }
    .driver-pill {
      display: grid;
      grid-template-columns: 34px 1fr;
      align-items: center;
      gap: 8px;
      min-width: 0;
      height: 30px;
      padding: 0 10px;
      border-radius: 6px;
      color: #06101c;
      font-weight: 950;
    }
    .driver-pos { text-align: center; }
    .driver-code { overflow: hidden; text-overflow: ellipsis; }
    .chip {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 86px;
      height: 30px;
      padding: 0 10px;
      border-radius: 6px;
      background: transparent;
    }
    .chip.green { background: var(--green); color: #04130a; }
    .chip.purple { background: var(--purple); color: white; }
    .chip.dim { color: #526076; }
    .tyre-cell {
      display: flex;
      align-items: center;
      gap: 8px;
      justify-content: center;
    }
    .tyre-laps { min-width: 24px; text-align: right; }
    .tyre-dot {
      width: 28px;
      height: 28px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border-radius: 50%;
      background: #303948;
      color: white;
      border: 3px solid #111827;
      box-shadow: 0 0 0 2px currentColor;
      font-size: 14px;
      font-weight: 950;
    }
    .tyre-dot.soft { color: #ff2038; }
    .tyre-dot.medium { color: #ffd21e; }
    .tyre-dot.hard { color: #f2f2f2; }
    .tyre-dot.intermediate { color: #25cf68; }
    .tyre-dot.wet { color: #3385ff; }
    .mini {
      display: flex;
      align-items: center;
      gap: 4px;
      height: 28px;
    }
    .seg {
      width: 5px;
      height: 27px;
      border-radius: 4px;
      background: #314059;
    }
    .seg.green { background: var(--green); }
    .seg.purple { background: var(--purple); }
    .seg.yellow { background: var(--yellow); }
    .seg.orange { background: var(--orange); }
    .seg.blue { background: var(--blue); }
    .sector-group {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 8px;
      align-items: center;
    }
    .sector {
      display: inline-flex;
      justify-content: center;
      padding: 5px 6px;
      border-radius: 5px;
      color: #f4f7ff;
    }
    .sector.green { background: var(--green); color: #06120a; }
    .sector.purple { background: var(--purple); color: white; }
    .sector.dim { color: #53617b; }
    .empty {
      height: 520px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #8794ad;
      font-size: 22px;
      font-weight: 900;
    }
    .ticker {
      display: flex;
      gap: 12px;
      padding: 10px 14px;
      border-top: 1px solid rgba(255,255,255,0.08);
      background: #08111f;
      overflow: hidden;
      color: #d7deee;
      font-size: 14px;
      font-family: Inter, Arial, sans-serif;
    }
    .ticker strong { color: #ff4b5d; }
    @media (max-width: 900px) {
      body { overflow: auto; }
      .top-nav { gap: 10px; padding: 0 12px; }
      .nav-tab:not(.active) { display: none; }
      .session-bar { grid-template-columns: 1fr; align-items: start; }
      .weather { flex-wrap: wrap; font-size: 18px; }
      .table-wrap { height: auto; max-height: none; }
    }
  </style>
</head>
<body>
  <main class="wall">
    <nav class="top-nav">
      <div class="signal"></div>
      <div class="nav-tab active">Live Timing</div>
      <div class="nav-tab">Standings</div>
      <div class="nav-tab">Analytics</div>
      <div class="nav-tab">Calendar</div>
      <div class="nav-tab">Teams</div>
      <div class="nav-tab">Circuits</div>
      <div class="nav-tab">Replay</div>
      <div class="nav-spacer"></div>
      <div class="pause">Ⅱ</div>
      <div id="messageCounter" class="counter">0</div>
      <div class="gear"></div>
      <div class="user"></div>
    </nav>

    <section class="session-bar">
      <div class="event">
        <div class="flag"></div>
        <div id="eventTitle" class="event-title">F1 Grand Prix · Race</div>
      </div>
      <div id="weather" class="weather">
        <span>--<small>TRC</small></span>
        <span>--<small>AIR</small></span>
        <span>--<small>HUM</small></span>
        <span>--<small>WIND</small></span>
      </div>
      <div class="lap-status"><span id="lapCounter">-- / --</span><small>LAP</small></div>
      <div id="trackState" class="track-state">CONNECTING</div>
    </section>

    <section class="table-wrap">
      <table>
        <thead>
          <tr>
            <th class="col-pit">PIT</th>
            <th class="col-driver">DRIVER ↑</th>
            <th class="col-interval">INTERVAL</th>
            <th class="col-tyre">TYRE ↕</th>
            <th class="col-best">BEST LAP ↕</th>
            <th class="col-leader">LEADER</th>
            <th class="col-last">LAST LAP ↕</th>
            <th class="col-mini">MINI SECTORS</th>
            <th class="col-last-sectors">LAST SECTORS ↕</th>
            <th class="col-best-sectors">BEST SECTORS ↕</th>
          </tr>
        </thead>
        <tbody id="timingRows">
          <tr><td colspan="10"><div class="empty">LIVE FEED CONNECTING</div></td></tr>
        </tbody>
      </table>
    </section>
    <section id="raceTicker" class="ticker"><strong>Race Control</strong><span>Waiting for session messages.</span></section>
  </main>

  <script>
    const CONFIGURED_SERVICE_URL = __SERVICE_URL__;
    const POLL_MS = __POLL_MS__;
    const TYRES = {SOFT: "S", MEDIUM: "M", HARD: "H", INTERMEDIATE: "I", WET: "W"};
    const TEAM_FALLBACK = ["#00d2be", "#dc0000", "#3671c6", "#ff8700", "#2293d1", "#6692ff", "#b6babd", "#229971", "#c92d4b", "#52e252"];
    const state = {serviceUrl: null, failures: 0, lastSnapshot: null};

    function unique(values) {
      return [...new Set(values.filter(Boolean).map(value => value.replace(new RegExp("/$"), "")))];
    }
    function serviceUrlCandidates() {
      const urls = [CONFIGURED_SERVICE_URL];
      try {
        const configured = new URL(CONFIGURED_SERVICE_URL);
        const port = configured.port || "8765";
        if (["localhost", "127.0.0.1", "0.0.0.0"].includes(configured.hostname)) {
          urls.push(`${configured.protocol}//127.0.0.1:${port}`);
          urls.push(`${configured.protocol}//localhost:${port}`);
          if (window.location.hostname && !["localhost", "127.0.0.1"].includes(window.location.hostname)) {
            urls.push(`${configured.protocol}//${window.location.hostname}:${port}`);
          }
        }
      } catch (_error) {}
      return unique(urls);
    }
    const SERVICE_URLS = serviceUrlCandidates();

    function esc(value) {
      return String(value ?? "-").replace(/[&<>"']/g, ch => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
      }[ch]));
    }
    function setHTML(id, html) {
      const el = document.getElementById(id);
      if (el.dataset.html !== html) {
        el.innerHTML = html;
        el.dataset.html = html;
      }
    }
    function setText(id, text) {
      const el = document.getElementById(id);
      if (el.textContent !== String(text)) el.textContent = text;
    }
    function cleanColor(raw, index = 0) {
      const value = String(raw || "").replace("#", "");
      if (value.length === 3 || value.length === 6) return `#${value}`;
      return TEAM_FALLBACK[index % TEAM_FALLBACK.length];
    }
    function readableText(hex) {
      const clean = hex.replace("#", "");
      if (clean.length !== 6) return "#06101c";
      const r = parseInt(clean.slice(0, 2), 16);
      const g = parseInt(clean.slice(2, 4), 16);
      const b = parseInt(clean.slice(4, 6), 16);
      return (r * 0.299 + g * 0.587 + b * 0.114) > 145 ? "#06101c" : "#ffffff";
    }
    function driverCode(driver, fallback) {
      return driver?.name_acronym || driver?.tla || driver?.Tla || String(fallback);
    }
    function formatTime(value) {
      if (value === undefined || value === null || value === "") return "-- -- ---";
      const num = Number(value);
      if (!Number.isFinite(num)) return String(value);
      const minutes = Math.floor(num / 60);
      const seconds = num - minutes * 60;
      return minutes ? `${minutes}:${seconds.toFixed(3).padStart(6, "0")}` : seconds.toFixed(3);
    }
    function formatGap(value) {
      if (value === undefined || value === null || value === "") return "-- ---";
      const text = String(value);
      if (text.includes("LAP")) return text.replace("+", "");
      if (text.startsWith("+")) return text;
      const num = Number(text);
      return Number.isFinite(num) && num > 0 ? `+${num.toFixed(3)}` : text;
    }
    function tyreInfo(snapshot, number) {
      const tyre = (snapshot.tyres || {})[String(number)] || {};
      const compound = String(tyre.compound || tyre.Compound || "").toUpperCase();
      return {
        short: TYRES[compound] || compound.slice(0, 1) || "-",
        cls: compound.toLowerCase().replace(/\\s+/g, "-") || "unknown",
        laps: tyre.total_laps || tyre.TotalLaps || "0"
      };
    }
    function sectorValue(sector) {
      if (!sector) return "-- ---";
      if (typeof sector === "string" || typeof sector === "number") return formatTime(sector);
      return formatTime(sector.Value ?? sector.value ?? sector.Time ?? sector.time);
    }
    function sectorClass(sector) {
      const text = JSON.stringify(sector || {}).toLowerCase();
      if (text.includes("overall") || text.includes("purple")) return "purple";
      if (text.includes("personal") || text.includes("green")) return "green";
      return "";
    }
    function segmentClass(segment) {
      const value = String(segment?.Status ?? segment?.status ?? segment ?? "").toLowerCase();
      if (value.includes("overall") || value.includes("purple") || value === "2051") return "purple";
      if (value.includes("personal") || value.includes("green") || value === "2049") return "green";
      if (value.includes("yellow") || value === "2064") return "yellow";
      if (value.includes("blue")) return "blue";
      if (value && value !== "0" && value !== "2048") return "orange";
      return "";
    }
    function sectors(row) {
      const items = Array.isArray(row.sectors) ? row.sectors : [];
      return [items[0], items[1], items[2]];
    }
    function miniSectors(row) {
      const segments = [];
      for (const sector of sectors(row)) {
        const sectorSegments = sector?.Segments || sector?.segments || [];
        if (Array.isArray(sectorSegments)) segments.push(...sectorSegments);
      }
      const padded = segments.length ? segments.slice(0, 34) : Array(34).fill(null);
      return `<div class="mini">${padded.map(seg => `<i class="seg ${segmentClass(seg)}"></i>`).join("")}</div>`;
    }
    function sectorGroup(row, best = false) {
      const html = sectors(row).map(sector => {
        const cls = best ? sectorClass(sector) : sectorClass(sector);
        return `<span class="sector ${cls || "dim"}">${esc(sectorValue(sector))}</span>`;
      }).join("");
      return `<div class="sector-group">${html}</div>`;
    }
    function rowsFromSnapshot(snapshot) {
      const timing = snapshot.timing || {};
      const drivers = snapshot.drivers || {};
      return Object.entries(timing)
        .map(([number, row], index) => {
          const driver = drivers[String(number)] || {};
          const position = Number(row.position || 99);
          const teamColor = cleanColor(driver.team_colour || driver.team_color, index);
          return {
            number,
            index,
            position,
            driver,
            color: teamColor,
            textColor: readableText(teamColor),
            code: driverCode(driver, number),
            tyre: tyreInfo(snapshot, number),
            pit: row.in_pit === true || row.pit_out === true,
            interval: formatGap(row.interval),
            gap: formatGap(row.gap_to_leader),
            best: formatTime(row.best_lap),
            last: formatTime(row.last_lap),
            row
          };
        })
        .filter(row => Number.isFinite(row.position))
        .sort((a, b) => a.position - b.position)
        .slice(0, 22);
    }
    function trackState(snapshot) {
      const status = snapshot.track_status || {};
      const raw = String(status.Status || status.status || status.Message || status.message || "").toLowerCase();
      if (raw.includes("red") || raw === "5") return ["RED FLAG", "red"];
      if (raw.includes("safety") || raw === "4") return ["SAFETY CAR", "sc"];
      if (raw.includes("yellow") || raw === "2" || raw === "3") return ["YELLOW", "yellow"];
      return ["TRACK CLEAR", ""];
    }
    function displayRaceLap(lap) {
      const current = Number(lap?.CurrentLap);
      if (!Number.isFinite(current)) return "--";
      return current;
    }
    function renderHeader(snapshot) {
      const session = snapshot.session || {};
      const event = session.Name || session.Meeting?.Name || session.country_name || "F1 Grand Prix";
      const sessionName = session.session_name || session.NameShort || "Race";
      const weather = snapshot.weather || {};
      const lap = snapshot.lap_count || {};
      const hasTimingData = Object.keys(snapshot.timing || {}).length > 0;
      const [statusText, statusClass] = (snapshot.connected || hasTimingData)
        ? trackState(snapshot)
        : ["CONNECTING", "yellow"];
      setText("eventTitle", `${event} · ${sessionName}`);
      setText("messageCounter", snapshot.message_count || 0);
      setText("lapCounter", `${displayRaceLap(lap)} / ${lap.TotalLaps || "--"}`);
      setHTML("weather", `
        <span>${esc(weather.TrackTemp || weather.track_temperature || "--")}°<small>TRC</small></span>
        <span>${esc(weather.AirTemp || weather.air_temperature || "--")}°<small>AIR</small></span>
        <span>${esc(weather.Humidity || weather.humidity || "--")}%<small>HUM</small></span>
        <span>${esc(weather.WindSpeed || weather.wind_speed || "--")}<small>WIND</small></span>
      `);
      const el = document.getElementById("trackState");
      el.className = `track-state ${statusClass}`;
      setText("trackState", statusText);
    }
    function renderRows(snapshot) {
      const rows = rowsFromSnapshot(snapshot);
      if (!rows.length) {
        setHTML("timingRows", `<tr><td colspan="10"><div class="empty">LIVE TIMING CONNECTING</div></td></tr>`);
        return;
      }
      const fastestBest = rows.reduce((acc, row) => {
        const raw = Number(row.row.best_lap);
        return Number.isFinite(raw) && (acc === null || raw < acc) ? raw : acc;
      }, null);
      const html = rows.map(row => {
        const isFastestBest = fastestBest !== null && Number(row.row.best_lap) === fastestBest;
        return `
          <tr>
            <td class="col-pit">${row.pit ? `<span class="pit-badge">PIT</span>` : ""}</td>
            <td class="col-driver">
              <div class="driver-pill" style="background:${row.color};color:${row.textColor}">
                <span class="driver-pos">${row.position}</span>
                <span class="driver-code">${esc(row.code)}</span>
              </div>
            </td>
            <td class="col-interval"><span class="chip ${row.interval.startsWith("+") ? "green" : ""}">${esc(row.interval)}</span></td>
            <td class="col-tyre"><span class="tyre-cell"><span class="tyre-laps">${esc(row.tyre.laps)}</span><span class="tyre-dot ${esc(row.tyre.cls)}">${esc(row.tyre.short)}</span></span></td>
            <td class="col-best"><span class="chip ${isFastestBest ? "purple" : ""}">${esc(row.best)}</span></td>
            <td class="col-leader">${esc(row.gap)}</td>
            <td class="col-last"><span class="chip">${esc(row.last)}</span></td>
            <td class="col-mini">${miniSectors(row.row)}</td>
            <td class="col-last-sectors">${sectorGroup(row.row)}</td>
            <td class="col-best-sectors">${sectorGroup(row.row, true)}</td>
          </tr>`;
      }).join("");
      setHTML("timingRows", html);
    }
    function renderTicker(snapshot) {
      const messages = (snapshot.race_control || []).slice(-3).reverse();
      if (!messages.length) {
        setHTML("raceTicker", `<strong>Race Control</strong><span>Waiting for session messages.</span>`);
        return;
      }
      setHTML("raceTicker", `<strong>Race Control</strong>${messages.map(message => `<span>${esc(message.message || message.category || "Message")}</span>`).join("")}`);
    }
    function render(snapshot) {
      state.lastSnapshot = snapshot;
      state.failures = 0;
      renderHeader(snapshot);
      renderRows(snapshot);
      renderTicker(snapshot);
    }
    function setOfflineStatus() {
      state.failures += 1;
      if (state.lastSnapshot) {
        setText("trackState", "RECONNECTING");
        return;
      }
      setHTML("timingRows", `<tr><td colspan="10"><div class="empty">LIVE FEED CONNECTING</div></td></tr>`);
      setText("messageCounter", state.failures);
      setText("trackState", "CONNECTING");
    }
    async function fetchSnapshot(url) {
      const controller = new AbortController();
      const timeout = window.setTimeout(() => controller.abort(), 1800);
      try {
        const response = await fetch(`${url}/snapshot`, {cache: "no-store", signal: controller.signal});
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
      } finally {
        window.clearTimeout(timeout);
      }
    }
    async function poll() {
      const candidates = state.serviceUrl ? [state.serviceUrl, ...SERVICE_URLS] : SERVICE_URLS;
      for (const url of unique(candidates)) {
        try {
          const snapshot = await fetchSnapshot(url);
          state.serviceUrl = url;
          render(snapshot);
          return;
        } catch (_error) {}
      }
      setOfflineStatus();
    }
    poll();
    window.setInterval(poll, POLL_MS);
  </script>
</body>
</html>
"""
    return template.replace("__SERVICE_URL__", repr(safe_url)).replace(
        "__POLL_MS__", str(int(poll_ms))
    )


def _build_live_timing_component_html(service_url: str, poll_ms: int = 2000) -> str:
    safe_url = service_url.rstrip("/")
    template = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <style>
    :root {
      color-scheme: dark;
      --page: #191919;
      --panel: #0f1117;
      --panel-soft: #111319;
      --panel-deep: #080a0f;
      --line: rgba(216, 221, 231, 0.13);
      --line-strong: rgba(255, 75, 75, 0.34);
      --red: #7d0e0e;
      --red-bright: #ff4b4b;
      --text: #ffffff;
      --muted: #aeb4be;
      --dim: #687080;
      --green: #30ff8a;
      --purple: #b02dff;
      --yellow: #ffb000;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--page);
      color: var(--text);
      font-family: Playfair, Georgia, serif;
      overflow: hidden;
    }
    .live-shell {
      display: grid;
      gap: 18px;
      padding: 2px;
      background: var(--page);
    }
    .live-hero {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 24px;
      align-items: end;
      padding: clamp(18px, 3vw, 34px);
      border: 1px solid var(--line);
      border-radius: 8px;
      background:
        linear-gradient(135deg, rgba(125, 14, 14, 0.28), transparent 42%),
        repeating-linear-gradient(90deg, rgba(255,255,255,0.035) 0, rgba(255,255,255,0.035) 1px, transparent 1px, transparent 76px),
        var(--panel);
      box-shadow: 0 18px 46px rgba(0,0,0,0.22);
    }
    .kicker {
      display: block;
      margin-bottom: 8px;
      color: var(--red-bright);
      font-family: Tektur, Inter, sans-serif;
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.16em;
      text-transform: uppercase;
    }
    h1 {
      margin: 0;
      color: #fff;
      font-family: Tektur, Inter, sans-serif;
      font-size: clamp(34px, 5vw, 66px);
      line-height: 0.96;
    }
    .hero-subtitle {
      margin-top: 10px;
      color: #c8cdd6;
      font-size: 16px;
    }
    .session-card {
      min-width: 260px;
      padding: 16px 18px;
      border: 1px solid rgba(255, 75, 75, 0.26);
      border-radius: 8px;
      background: rgba(8, 10, 15, 0.82);
    }
    .status-line {
      display: flex;
      align-items: center;
      gap: 8px;
      color: #d8dde7;
      font-family: Tektur, Inter, sans-serif;
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }
    .status-dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: var(--yellow);
      box-shadow: 0 0 14px rgba(255, 176, 0, 0.65);
    }
    .status-line.live .status-dot {
      background: var(--green);
      box-shadow: 0 0 14px rgba(48, 255, 138, 0.85);
    }
    .session-card strong {
      display: block;
      margin-top: 10px;
      font-family: Tektur, Inter, sans-serif;
      font-size: 20px;
      line-height: 1.1;
    }
    .session-card small {
      display: block;
      margin-top: 6px;
      color: var(--muted);
    }
    .summary-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
    }
    .summary-card {
      min-height: 86px;
      padding: 14px 16px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel-soft);
    }
    .summary-card span {
      display: block;
      color: var(--muted);
      font-family: Tektur, Inter, sans-serif;
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }
    .summary-card strong {
      display: block;
      margin-top: 8px;
      color: #fff;
      font-family: Tektur, Inter, sans-serif;
      font-size: clamp(24px, 3vw, 34px);
      line-height: 1;
    }
    .main-grid {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(280px, 0.28fr);
      gap: 18px;
      align-items: start;
    }
    .timing-panel,
    .race-control {
      overflow: hidden;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel-deep);
      box-shadow: 0 0 28px rgba(0, 0, 0, 0.32);
    }
    .panel-title {
      min-height: 48px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      background: linear-gradient(90deg, rgba(125, 14, 14, 0.84), rgba(125, 14, 14, 0.25));
      font-family: Tektur, Inter, sans-serif;
      font-size: 14px;
      font-weight: 800;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .panel-title small {
      color: #c8cdd6;
      font-size: 11px;
      letter-spacing: 0.06em;
    }
    .table-scroll {
      overflow: auto;
      max-height: 760px;
    }
    table {
      width: 100%;
      min-width: 1120px;
      border-collapse: separate;
      border-spacing: 0;
      table-layout: fixed;
      font-variant-numeric: tabular-nums;
    }
    thead th {
      position: sticky;
      top: 0;
      z-index: 2;
      padding: 12px 10px;
      border-bottom: 1px solid var(--line-strong);
      border-right: 1px solid rgba(216, 221, 231, 0.08);
      background: #12161f;
      color: #d8dde7;
      font-family: Tektur, Inter, sans-serif;
      font-size: 12px;
      font-weight: 800;
      letter-spacing: 0.08em;
      text-align: left;
      text-transform: uppercase;
    }
    tbody tr { background: #0d1017; }
    tbody tr:nth-child(odd) { background: #10141d; }
    tbody td {
      height: 44px;
      padding: 8px 10px;
      border-bottom: 1px solid rgba(255,255,255,0.04);
      border-right: 1px solid rgba(216, 221, 231, 0.07);
      color: #f5f7fb;
      font-family: Tektur, Inter, sans-serif;
      font-size: 15px;
      font-weight: 750;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .col-state { width: 88px; text-align: center; }
    .col-pos { width: 58px; text-align: center; }
    .col-driver { width: 190px; }
    .col-team { width: 170px; }
    .col-stops { width: 78px; text-align: center; }
    .col-tyre { width: 92px; text-align: center; }
    .col-lap { width: 88px; text-align: center; }
    .col-gap,
    .col-int,
    .col-last,
    .col-best { width: 118px; }
    .col-sectors { width: 190px; }
    .position {
      display: inline-flex;
      justify-content: center;
      align-items: center;
      width: 32px;
      height: 28px;
      border-radius: 5px;
      background: rgba(255,255,255,0.08);
    }
    .run-state {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 64px;
      height: 28px;
      padding: 0 8px;
      border-radius: 5px;
      color: #101010;
      font-family: Tektur, Inter, sans-serif;
      font-size: 12px;
      font-weight: 900;
      letter-spacing: 0.08em;
    }
    .run-state.inpit { background: #ff4b4b; color: #ffffff; }
    .run-state.pitout { background: #ffb000; color: #101010; }
    .run-state.pitstop { background: #ff4b4b; color: #ffffff; }
    .run-state.out { background: #aeb4be; color: #101010; }
    .driver {
      display: flex;
      align-items: center;
      gap: 10px;
      min-width: 0;
    }
    .team-stripe {
      width: 4px;
      height: 26px;
      border-radius: 999px;
      background: #888;
      box-shadow: 0 0 12px currentColor;
      flex: 0 0 auto;
    }
    .driver-code {
      color: #fff;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .penalty {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      margin-left: 7px;
      color: #ffb000;
      font-size: 12px;
      font-weight: 900;
      vertical-align: middle;
    }
    .penalty-mark {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 16px;
      height: 16px;
      border-radius: 50%;
      background: #ffb000;
      color: #101010;
      font-size: 12px;
      line-height: 1;
    }
    .team-name {
      color: #b9c0ce;
      font-family: Playfair, Georgia, serif;
      font-size: 15px;
      font-weight: 700;
    }
    .chip {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 72px;
      height: 28px;
      padding: 0 8px;
      border-radius: 5px;
      background: rgba(255,255,255,0.06);
    }
    .chip.good {
      background: rgba(48, 255, 138, 0.9);
      color: #07130b;
    }
    .chip.fastest {
      background: var(--purple);
      color: #fff;
      box-shadow: 0 0 18px rgba(176, 45, 255, 0.24);
    }
    .tyre {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 28px;
      height: 28px;
      border-radius: 50%;
      background: #20242e;
      border: 2px solid currentColor;
      color: #8f98a8;
      font-size: 12px;
      font-weight: 900;
    }
    .tyre.soft { color: #ff2038; }
    .tyre.medium { color: #ffd21e; }
    .tyre.hard { color: #f2f2f2; }
    .tyre.intermediate { color: #25cf68; }
    .tyre.wet { color: #3385ff; }
    .tyre-laps {
      margin-left: 7px;
      color: var(--muted);
      font-size: 12px;
    }
    .sectors {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 6px;
    }
    .sector {
      min-width: 0;
      padding: 5px 6px;
      border-radius: 5px;
      background: rgba(255,255,255,0.06);
      text-align: center;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .sector.good { background: rgba(48, 255, 138, 0.9); color: #07130b; }
    .sector.fastest { background: var(--purple); color: #fff; }
    .sector.dim { color: var(--dim); }
    .empty {
      height: 280px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: var(--muted);
      font-family: Tektur, Inter, sans-serif;
      font-weight: 800;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }
    .race-control-list {
      display: grid;
      gap: 0;
      max-height: 760px;
      overflow: auto;
    }
    .race-message {
      padding: 14px 16px;
      border-top: 1px solid rgba(255,255,255,0.07);
      border-left: 3px solid var(--red);
      background: #111319;
    }
    .race-message:first-child { border-top: 0; }
    .race-message span {
      color: var(--muted);
      font-size: 12px;
    }
    .race-message strong {
      display: block;
      margin: 4px 0;
      color: #fff;
      font-family: Tektur, Inter, sans-serif;
      font-size: 13px;
    }
    .race-message p {
      margin: 0;
      color: #d8dde7;
      font-size: 14px;
      line-height: 1.35;
    }
    @media (max-width: 1050px) {
      body { overflow: auto; }
      .live-hero,
      .main-grid { grid-template-columns: 1fr; }
      .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .table-scroll,
      .race-control-list { max-height: none; }
    }
    @media (max-width: 620px) {
      .summary-grid { grid-template-columns: 1fr; }
      .session-card { min-width: 0; }
    }
  </style>
</head>
<body>
  <main class="live-shell">
    <section class="live-hero">
      <div>
        <span class="kicker">F1 Pit Wall</span>
        <h1>Live Timing</h1>
        <div id="eventTitle" class="hero-subtitle">Waiting for session data</div>
      </div>
      <aside class="session-card">
        <div id="statusLine" class="status-line"><span class="status-dot"></span><span id="statusText">CONNECTING</span></div>
        <strong id="sessionName">Race operations</strong>
        <small id="lastUpdated">Waiting for first snapshot</small>
      </aside>
    </section>

    <section class="summary-grid">
      <div class="summary-card"><span>Track Status</span><strong id="trackStatus">--</strong></div>
      <div class="summary-card"><span>Lap</span><strong id="lapCounter">-- / --</strong></div>
      <div class="summary-card"><span>Leader</span><strong id="leaderCode">--</strong></div>
      <div class="summary-card"><span>Live Rows</span><strong id="rowCount">0</strong></div>
    </section>

    <section class="main-grid">
      <div class="timing-panel">
        <div class="panel-title">
          <span>Race Classification</span>
          <small id="tableStatus">Live feed</small>
        </div>
        <div class="table-scroll">
          <table>
            <thead>
              <tr>
                <th class="col-state">State</th>
                <th class="col-pos">Pos</th>
                <th class="col-driver">Driver</th>
                <th class="col-team">Team</th>
                <th class="col-stops">Stops</th>
                <th class="col-tyre">Tyre</th>
                <th class="col-lap">Lap</th>
                <th class="col-gap">Leader</th>
                <th class="col-int">Interval</th>
                <th class="col-last">Last Lap</th>
                <th class="col-best">Best Lap</th>
                <th class="col-sectors">Sectors</th>
              </tr>
            </thead>
            <tbody id="timingRows">
              <tr><td colspan="12"><div class="empty">Live feed connecting</div></td></tr>
            </tbody>
          </table>
        </div>
      </div>
      <aside class="race-control">
        <div class="panel-title"><span>Race Control</span><small id="messageCounter">0 msgs</small></div>
        <div id="raceControlList" class="race-control-list">
          <div class="race-message"><strong>Waiting for messages</strong><p>Race-control events will appear here during the session.</p></div>
        </div>
      </aside>
    </section>
  </main>

  <script>
    const CONFIGURED_SERVICE_URL = __SERVICE_URL__;
    const POLL_MS = __POLL_MS__;
    const TYRES = {SOFT: "S", MEDIUM: "M", HARD: "H", INTERMEDIATE: "I", WET: "W"};
    const TEAM_FALLBACK = ["#00d2be", "#dc0000", "#3671c6", "#ff8700", "#2293d1", "#6692ff", "#b6babd", "#229971", "#c92d4b", "#52e252"];
    const state = {serviceUrl: null, failures: 0, lastSnapshot: null, drivers: {}};

    function unique(values) {
      return [...new Set(values.filter(Boolean).map(value => value.replace(new RegExp("/$"), "")))];
    }
    function serviceUrlCandidates() {
      const urls = [CONFIGURED_SERVICE_URL];
      try {
        const configured = new URL(CONFIGURED_SERVICE_URL);
        const port = configured.port || "8765";
        if (["localhost", "127.0.0.1", "0.0.0.0"].includes(configured.hostname)) {
          urls.push(`${configured.protocol}//127.0.0.1:${port}`);
          urls.push(`${configured.protocol}//localhost:${port}`);
          if (window.location.hostname && !["localhost", "127.0.0.1"].includes(window.location.hostname)) {
            urls.push(`${configured.protocol}//${window.location.hostname}:${port}`);
          }
        }
      } catch (_error) {}
      return unique(urls);
    }
    const SERVICE_URLS = serviceUrlCandidates();

    function esc(value) {
      return String(value ?? "-").replace(/[&<>"']/g, ch => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
      }[ch]));
    }
    function setHTML(id, html) {
      const el = document.getElementById(id);
      if (el.dataset.html !== html) {
        el.innerHTML = html;
        el.dataset.html = html;
      }
    }
    function setText(id, value) {
      const el = document.getElementById(id);
      const text = String(value);
      if (el.textContent !== text) el.textContent = text;
    }
    function teamColor(driver, index) {
      const raw = String(driver?.team_colour || driver?.team_color || "").replace("#", "");
      if (raw.length === 3 || raw.length === 6) return `#${raw}`;
      return TEAM_FALLBACK[index % TEAM_FALLBACK.length];
    }
    function mergeDrivers(snapshot) {
      for (const [number, driver] of Object.entries(snapshot.drivers || {})) {
        const cached = state.drivers[String(number)] || {};
        const cleaned = {};
        for (const [key, value] of Object.entries(driver || {})) {
          if (value === undefined || value === null || value === "") continue;
          if (["tla", "Tla", "name_acronym", "broadcast_name", "full_name"].includes(key) && String(value) === String(number)) continue;
          cleaned[key] = value;
        }
        state.drivers[String(number)] = {...cached, ...cleaned, driver_number: String(number)};
      }
      return state.drivers;
    }
    function driverCode(driver) {
      return driver?.name_acronym || driver?.tla || driver?.Tla || driver?.broadcast_name || driver?.full_name || "---";
    }
    function driverTeam(driver) {
      return driver?.team_name || driver?.team || "-";
    }
    function formatTime(value) {
      if (value === undefined || value === null || value === "") return "-";
      const num = Number(value);
      if (!Number.isFinite(num)) return String(value);
      const minutes = Math.floor(num / 60);
      const seconds = num - minutes * 60;
      return minutes ? `${minutes}:${seconds.toFixed(3).padStart(6, "0")}` : seconds.toFixed(3);
    }
    function formatGap(value) {
      if (value === undefined || value === null || value === "") return "-";
      const text = String(value);
      if (text.includes("LAP")) return text.replace("+", "");
      if (text.startsWith("+")) return text;
      const num = Number(text);
      return Number.isFinite(num) && num > 0 ? `+${num.toFixed(3)}` : text;
    }
    function tyreInfo(snapshot, number) {
      const tyre = (snapshot.tyres || {})[String(number)] || {};
      const compound = String(tyre.compound || tyre.Compound || "").toUpperCase();
      return {
        short: TYRES[compound] || compound.slice(0, 1) || "-",
        cls: compound.toLowerCase().replace(/\\s+/g, "-") || "unknown",
        laps: tyre.total_laps || tyre.TotalLaps || "",
        stops: tyre.pit_stops ?? tyre.PitStops ?? "-"
      };
    }
    function sectorValue(sector) {
      if (!sector) return "-";
      if (typeof sector === "string" || typeof sector === "number") return formatTime(sector);
      return formatTime(sector.Value ?? sector.value ?? sector.Time ?? sector.time);
    }
    function sectorClass(sector) {
      const text = JSON.stringify(sector || {}).toLowerCase();
      if (text.includes("overall") || text.includes("purple")) return "fastest";
      if (text.includes("personal") || text.includes("green")) return "good";
      return "dim";
    }
    function sectorGroup(row) {
      const sectors = Array.isArray(row.sectors)
        ? row.sectors.slice(0, 3)
        : ["0", "1", "2"].map(key => (row.sectors || {})[key]);
      while (sectors.length < 3) sectors.push(null);
      return `<div class="sectors">${sectors.map(sector => `<span class="sector ${sectorClass(sector)}">${esc(sectorValue(sector))}</span>`).join("")}</div>`;
    }
    function isRedFlag(snapshot) {
      const status = snapshot.track_status || {};
      const raw = String(status.Status || status.status || status.Message || status.message || "").toLowerCase();
      return raw.includes("red") || raw === "5";
    }
    function runState(row, snapshot) {
      if (row.stopped === true) return {label: "Out", cls: "out"};
      if (isRedFlag(snapshot)) return {label: "", cls: ""};
      if (row.pit_out === true) return {label: "PitOut", cls: "pitout"};
      const speed = Number(row.speed);
      if (row.in_pit === true && Number.isFinite(speed) && speed <= 3) return {label: "PitStop", cls: "pitstop"};
      if (row.in_pit === true) return {label: "InPit", cls: "inpit"};
      return {label: "", cls: ""};
    }
    function penaltySeconds(text) {
      const numeric = text.match(/(\\d+)\\s*(?:second|sec|s)\\b/i);
      if (numeric) return `${numeric[1]}s`;
      const word = text.match(/\\b(five|ten|twenty|thirty)\\s+second\\b/i);
      if (!word) return "";
      return {five: "5s", ten: "10s", twenty: "20s", thirty: "30s"}[word[1].toLowerCase()] || "";
    }
    function penaltyLabel(value) {
      if (!value) return "";
      if (typeof value === "string" || typeof value === "number") return String(value).replace(/^\\+/, "");
      if (value.label) return String(value.label).replace(/^\\+/, "");
      if (value.seconds !== undefined && value.seconds !== null) return `${value.seconds}s`;
      return "";
    }
    function penaltyMap(snapshot) {
      const penalties = {};
      for (const [number, penalty] of Object.entries(snapshot.penalties || {})) {
        const label = penaltyLabel(penalty);
        if (label) penalties[String(number)] = label;
      }
      for (const message of snapshot.race_control || []) {
        const text = String(message.message || message.Message || "");
        if (!/penalty/i.test(text)) continue;
        const seconds = penaltyLabel(message.penalty_seconds) || penaltySeconds(text);
        const carMatch = text.match(/\\bcar\\s*#?\\s*(\\d{1,3})\\b/i);
        const number = String(message.driver_number || message.RacingNumber || message.DriverNumber || (carMatch && carMatch[1]) || "");
        if (!number || !seconds) continue;
        penalties[number] = seconds;
      }
      return penalties;
    }
    function sessionEventName(session) {
      return session?.Meeting?.Name
        || session?.meeting_name
        || session?.event_name
        || session?.country_name
        || session?.Name
        || "F1 Grand Prix";
    }
    function sessionLabel(session) {
      return session?.session_name
        || session?.Type
        || session?.Name
        || session?.NameShort
        || "Race";
    }
    function displayRaceLap(lap) {
      const current = Number(lap?.CurrentLap);
      if (!Number.isFinite(current)) return "--";
      return current;
    }
    function rowsFromSnapshot(snapshot) {
      const timing = snapshot.timing || {};
      const drivers = mergeDrivers(snapshot);
      const penalties = penaltyMap(snapshot);
      const carData = snapshot.car_data || {};
      return Object.entries(timing)
        .map(([number, row], index) => {
          const driver = drivers[String(number)] || {};
          const car = carData[String(number)] || carData[number] || {};
          const stateInput = {...row, speed: car.speed};
          const state = runState(stateInput, snapshot);
          return {
            number,
            index,
            position: Number(row.position),
            driver,
            color: teamColor(driver, index),
            code: driverCode(driver),
            team: driverTeam(driver),
            tyre: tyreInfo(snapshot, number),
            lap: row.lap_number || "-",
            gap: formatGap(row.gap_to_leader),
            interval: formatGap(row.interval),
            last: formatTime(row.last_lap),
            best: formatTime(row.best_lap),
            state,
            penalty: penalties[String(number)] || "",
            row
          };
        })
        .filter(row => Number.isFinite(row.position) && row.position > 0)
        .sort((a, b) => a.position - b.position || Number(a.number) - Number(b.number))
        .slice(0, 22);
    }
    function trackStatus(snapshot) {
      const status = snapshot.track_status || {};
      const raw = String(status.Status || status.status || status.Message || status.message || "").toLowerCase();
      if (raw.includes("red") || raw === "5") return "RED FLAG";
      if (raw.includes("safety") || raw === "4") return "SAFETY CAR";
      if (raw.includes("yellow") || raw === "2" || raw === "3") return "YELLOW";
      return "TRACK CLEAR";
    }
    function renderHeader(snapshot, rows) {
      const session = snapshot.session || {};
      const hasTiming = rows.length > 0;
      const event = sessionEventName(session);
      const sessionName = sessionLabel(session);
      const lap = snapshot.lap_count || {};
      const leader = rows[0]?.code || "--";
      document.getElementById("statusLine").className = hasTiming ? "status-line live" : "status-line";
      setText("statusText", hasTiming ? "LIVE DATA" : "CONNECTING");
      setText("eventTitle", `${event} · ${sessionName}`);
      setText("sessionName", sessionName);
      setText("lastUpdated", `messages=${snapshot.message_count || 0} · last=${snapshot.seconds_since_last_message ?? "-"}s`);
      setText("trackStatus", hasTiming ? trackStatus(snapshot) : "--");
      setText("lapCounter", `${displayRaceLap(lap)} / ${lap.TotalLaps || "--"}`);
      setText("leaderCode", leader);
      setText("rowCount", rows.length);
      setText("tableStatus", hasTiming ? "Live classification" : "Waiting for timing");
    }
    function renderRows(snapshot, rows) {
      if (!rows.length) {
        setHTML("timingRows", `<tr><td colspan="12"><div class="empty">Live feed connecting</div></td></tr>`);
        return;
      }
      const fastest = rows.reduce((acc, row) => {
        const value = Number(row.row.best_lap);
        return Number.isFinite(value) && (acc === null || value < acc) ? value : acc;
      }, null);
      const html = rows.map(row => {
        const isFastest = fastest !== null && Number(row.row.best_lap) === fastest;
        return `
          <tr>
            <td class="col-state">${row.state.label ? `<span class="run-state ${row.state.cls}">${esc(row.state.label)}</span>` : ""}</td>
            <td class="col-pos"><span class="position">${row.position}</span></td>
            <td class="col-driver"><div class="driver"><span class="team-stripe" style="background:${row.color};color:${row.color}"></span><span class="driver-code">${esc(row.code)}${row.penalty ? `<span class="penalty"><span class="penalty-mark">!</span>+${esc(row.penalty)}</span>` : ""}</span></div></td>
            <td class="col-team"><span class="team-name">${esc(row.team)}</span></td>
            <td class="col-stops">${esc(row.tyre.stops)}</td>
            <td class="col-tyre"><span class="tyre ${esc(row.tyre.cls)}">${esc(row.tyre.short)}</span>${row.tyre.laps ? `<span class="tyre-laps">${esc(row.tyre.laps)}</span>` : ""}</td>
            <td class="col-lap">${esc(row.lap)}</td>
            <td class="col-gap">${esc(row.gap)}</td>
            <td class="col-int"><span class="chip ${row.interval.startsWith("+") ? "good" : ""}">${esc(row.interval)}</span></td>
            <td class="col-last">${esc(row.last)}</td>
            <td class="col-best"><span class="chip ${isFastest ? "fastest" : ""}">${esc(row.best)}</span></td>
            <td class="col-sectors">${sectorGroup(row.row)}</td>
          </tr>`;
      }).join("");
      setHTML("timingRows", html);
    }
    function renderRaceControl(snapshot) {
      const messages = (snapshot.race_control || []).slice(-8).reverse();
      setText("messageCounter", `${messages.length} msgs`);
      if (!messages.length) {
        setHTML("raceControlList", `<div class="race-message"><strong>Waiting for messages</strong><p>Race-control events will appear here during the session.</p></div>`);
        return;
      }
      const html = messages.map(message => `
        <div class="race-message">
          <span>${esc(message.date || "-")}</span>
          <strong>${esc(message.category || message.flag || "MESSAGE")}</strong>
          <p>${esc(message.message || "-")}</p>
        </div>`).join("");
      setHTML("raceControlList", html);
    }
    function render(snapshot) {
      state.lastSnapshot = snapshot;
      state.failures = 0;
      const rows = rowsFromSnapshot(snapshot);
      renderHeader(snapshot, rows);
      renderRows(snapshot, rows);
      renderRaceControl(snapshot);
    }
    function setOfflineStatus() {
      state.failures += 1;
      if (state.lastSnapshot) {
        setText("statusText", "RECONNECTING");
        return;
      }
      setText("statusText", "CONNECTING");
      setText("lastUpdated", `retry=${state.failures}`);
    }
    async function fetchSnapshot(url) {
      const controller = new AbortController();
      const timeout = window.setTimeout(() => controller.abort(), 1800);
      try {
        const response = await fetch(`${url}/snapshot`, {cache: "no-store", signal: controller.signal});
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
      } finally {
        window.clearTimeout(timeout);
      }
    }
    async function poll() {
      const candidates = state.serviceUrl ? [state.serviceUrl, ...SERVICE_URLS] : SERVICE_URLS;
      for (const url of unique(candidates)) {
        try {
          const snapshot = await fetchSnapshot(url);
          state.serviceUrl = url;
          render(snapshot);
          return;
        } catch (_error) {}
      }
      setOfflineStatus();
    }
    poll();
    window.setInterval(poll, POLL_MS);
  </script>
</body>
</html>
"""
    return template.replace("__SERVICE_URL__", repr(safe_url)).replace(
        "__POLL_MS__", str(int(poll_ms))
    )


def _render_client_live_timing_app() -> None:
    st.iframe(
        _build_live_timing_component_html(LIVE_TIMING_BROWSER_SIGNALR_URL),
        height=1220,
    )


def run_page() -> None:
    st.set_page_config(page_title="Official Live Timing – AI Race Engineer", layout="wide")

    apply_dark_page_shell()
    load_css()
    navbar()

    _render_client_live_timing_app()
