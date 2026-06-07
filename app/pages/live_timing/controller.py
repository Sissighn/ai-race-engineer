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
    return (
        driver.get("name_acronym")
        or driver.get("tla")
        or driver.get("Tla")
        or str(fallback)
    )


def _driver_team(driver: dict) -> str:
    return driver.get("team_name") or driver.get("team") or "-"


def _team_colour(driver: dict) -> str:
    colour = driver.get("team_colour") or driver.get("team_color") or "888888"
    colour = str(colour).lstrip("#")
    return f"#{colour}" if len(colour) in (3, 6) else "#888888"


def _session_kind(payload: dict) -> str:
    session = payload.get("session") or {}
    text = " ".join(
        str(session.get(key, ""))
        for key in ("session_type", "session_name", "Name", "Meeting")
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
                "lap": lap.get("lap_number") or payload.get("lap_count", {}).get("CurrentLap") or "-",
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
    event_name = session.get("Name") or session.get("country_name") or "F1"
    session_name = session.get("session_name") or session.get("Meeting", {}).get("Name") or "Live Session"
    circuit_name = session.get("circuit_short_name") or session.get("Location") or "-"

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
          {''.join(html_rows)}
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
              <span>{message.get('date', '-')}</span>
              <strong>{message.get('category', message.get('flag', 'MESSAGE'))}</strong>
              <p>{message.get('message', '-')}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _build_live_timing_component_html(service_url: str, poll_ms: int = 2000) -> str:
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
            lap: (snapshot.lap_count || {{}}).CurrentLap || row.lap_number || "-",
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


def _render_client_live_timing_app() -> None:
    st.iframe(
        _build_live_timing_component_html(LIVE_TIMING_BROWSER_SIGNALR_URL),
        height=1180,
    )


def run_page() -> None:
    st.set_page_config(page_title="Official Live Timing – AI Race Engineer", layout="wide")

    apply_dark_page_shell()
    load_css()
    navbar()

    _render_client_live_timing_app()
