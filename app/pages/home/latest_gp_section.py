import html
from zoneinfo import ZoneInfo

import fastf1
import numpy as np
import pandas as pd
import streamlit as st

from app.components.glow_card import GlowCard
from src.config import settings
from src.logging import get_logger

LOCAL_TZ = ZoneInfo("Europe/Berlin")
logger = get_logger(__name__)

try:
    if settings.FASTF1_CACHE_ENABLED:
        fastf1.Cache.enable_cache(settings.FASTF1_CACHE_PATH)
except Exception as e:
    logger.warning("Could not enable FastF1 cache for home track map", error=str(e))


def _format_weekend_range(display_event) -> str:
    session_dates = []
    for idx in range(1, 6):
        date_value = display_event.get(f"Session{idx}DateUtc")
        if pd.notna(date_value):
            session_dates.append(pd.to_datetime(date_value, utc=True).tz_convert(LOCAL_TZ))

    if not session_dates:
        event_date = pd.to_datetime(display_event["EventDate"])
        return event_date.strftime("%d %B %Y")

    start = min(session_dates)
    end = max(session_dates)
    if start.date() == end.date():
        return start.strftime("%d %B %Y")
    if start.year == end.year and start.month == end.month:
        return f"{start.strftime('%d')}-{end.strftime('%d %B %Y')}"
    if start.year == end.year:
        return f"{start.strftime('%d %B')} - {end.strftime('%d %B %Y')}"
    return f"{start.strftime('%d %B %Y')} - {end.strftime('%d %B %Y')}"


def _session_status(
    session_time: pd.Timestamp,
    next_session_time: pd.Timestamp | None,
) -> str:
    if pd.notna(next_session_time) and session_time == pd.to_datetime(next_session_time, utc=True):
        return "next"
    if session_time < pd.Timestamp.now(tz="UTC"):
        return "completed"
    return "upcoming"


def build_weekend_sessions(
    display_event,
    next_session_time: pd.Timestamp | None = None,
) -> list[dict[str, str]]:
    """Build presentation data for all sessions in a Grand Prix weekend."""
    sessions = []

    for idx in range(1, 6):
        name = display_event.get(f"Session{idx}")
        date_value = display_event.get(f"Session{idx}DateUtc")
        if pd.isna(name) or pd.isna(date_value):
            continue

        session_time_utc = pd.to_datetime(date_value, utc=True)
        session_time_local = session_time_utc.tz_convert(LOCAL_TZ)
        sessions.append(
            {
                "name": str(name),
                "day": session_time_local.strftime("%A"),
                "date": session_time_local.strftime("%d %b"),
                "time": session_time_local.strftime("%H:%M"),
                "status": _session_status(session_time_utc, next_session_time),
            }
        )

    return sessions


def _render_sessions_html(sessions: list[dict[str, str]]) -> str:
    rows = []
    for session in sessions:
        status = html.escape(session["status"])
        rows.append(
            '<article class="gp-session-row">'
            f'<div class="gp-session-status gp-session-status--{status}"></div>'
            '<div class="gp-session-main">'
            f"<strong>{html.escape(session['name'])}</strong>"
            f"<span>{html.escape(session['day'])}, {html.escape(session['date'])}</span>"
            "</div>"
            f'<div class="gp-session-time">{html.escape(session["time"])}</div>'
            "</article>"
        )
    return "".join(rows)


def _normalise_track_points(
    pos_data: pd.DataFrame, max_points: int = 180
) -> list[tuple[float, float]]:
    work = pos_data[["X", "Y"]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(work) < 12:
        raise ValueError("Not enough position samples for circuit map.")

    if len(work) > max_points:
        sample_idx = np.linspace(0, len(work) - 1, max_points, dtype=int)
        work = work.iloc[sample_idx]

    x = work["X"].astype(float).to_numpy()
    y = -work["Y"].astype(float).to_numpy()
    x_span = max(float(np.max(x) - np.min(x)), 1.0)
    y_span = max(float(np.max(y) - np.min(y)), 1.0)
    scale = min(390 / x_span, 330 / y_span)

    x = (x - np.min(x)) * scale + (500 - x_span * scale) / 2
    y = (y - np.min(y)) * scale + (500 - y_span * scale) / 2

    return [(round(float(px), 1), round(float(py), 1)) for px, py in zip(x, y, strict=True)]


def _points_to_svg_path(points: list[tuple[float, float]]) -> str:
    first_x, first_y = points[0]
    commands = [f"M{first_x} {first_y}"]
    commands.extend(f"L{x} {y}" for x, y in points[1:])
    return " ".join(commands)


def _load_track_points_for_event(
    event_name: str,
    season_year: int,
) -> tuple[list[tuple[float, float]], int, str] | None:
    for year in range(season_year, max(2017, season_year - 6), -1):
        for session_type in ("R", "Q", "FP2", "FP1"):
            try:
                session = fastf1.get_session(year, event_name, session_type)
                session.load(laps=True, telemetry=True, weather=False, messages=False)
                fastest_lap = session.laps.pick_fastest()
                pos_data = fastest_lap.get_pos_data()
                points = _normalise_track_points(pos_data)
                return points, year, session_type
            except Exception as e:
                logger.info(
                    "Circuit reference unavailable",
                    event_name=event_name,
                    year=year,
                    session_type=session_type,
                    error=str(e),
                )

    return None


@st.cache_data(ttl=86400, show_spinner="Loading circuit map...")
def _get_track_svg_payload(
    event_name: str,
    season_year: int,
) -> dict[str, str] | None:
    loaded = _load_track_points_for_event(event_name, season_year)
    if loaded is None:
        return None

    points, _reference_year, _session_type = loaded
    start_x, start_y = points[0]
    return {
        "path": _points_to_svg_path(points),
        "start_x": str(start_x),
        "start_y": str(start_y),
    }


def _render_track_art(event_name: str, season_year: int) -> str:
    payload = _get_track_svg_payload(event_name, season_year)

    if payload is None:
        return (
            '<div class="gp-track-panel gp-track-panel--empty">'
            '<div class="gp-track-empty-copy">'
            "<strong>Circuit map unavailable</strong>"
            "<span>FastF1 has no usable reference outline for this event yet.</span>"
            "</div>"
            "</div>"
        )

    return (
        '<div class="gp-track-panel">'
        '<svg class="gp-track-svg" viewBox="0 0 500 500" role="img" '
        f'aria-label="{html.escape(event_name)} circuit map">'
        "<defs>"
        '<filter id="trackGlow" x="-40%" y="-40%" width="180%" height="180%">'
        '<feGaussianBlur stdDeviation="5" result="blur" />'
        '<feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>'
        "</filter>"
        "</defs>"
        f'<path class="gp-track-shadow" d="{payload["path"]}" />'
        f'<path class="gp-track-line" d="{payload["path"]}" />'
        '<circle class="gp-track-start" '
        f'cx="{payload["start_x"]}" cy="{payload["start_y"]}" r="5" />'
        "</svg>"
        "</div>"
    )


def render_latest_gp(
    display_event,
    next_session_name: str,
    next_session_time: pd.Timestamp | None = None,
) -> None:
    """Render the current Grand Prix weekend section."""
    event_long_raw = str(display_event["EventName"])
    location_raw = str(display_event["Location"])
    event_long = html.escape(event_long_raw)
    location = html.escape(location_raw)
    country = html.escape(str(display_event["Country"]))
    weekend_range = html.escape(_format_weekend_range(display_event))
    next_session_label = html.escape(str(next_session_name))
    sessions = build_weekend_sessions(display_event, next_session_time)
    sessions_html = _render_sessions_html(sessions)
    season_year = int(pd.Timestamp(display_event["EventDate"]).year)
    track_html = _render_track_art(event_long_raw, season_year)
    location_card = GlowCard.to_html(
        "Location",
        f"{location_raw}, {display_event['Country']}",
    )
    weekend_card = GlowCard.to_html("Race Weekend", _format_weekend_range(display_event))
    next_session_card = GlowCard.to_html("Next Session", next_session_name)

    GlowCard._inject_code()

    section_html = (
        '<section class="latest-gp-section">'
        '<div class="gp-weekend-shell">'
        '<div class="gp-weekend-header">'
        "<div>"
        '<span class="gp-weekend-kicker">Grand Prix Weekend</span>'
        f'<h2 class="gp-weekend-title">{event_long}</h2>'
        f'<p class="gp-weekend-subtitle">{location}, {country} · {weekend_range}</p>'
        "</div>"
        '<div class="gp-weekend-next">'
        "<span>Next</span>"
        f"<strong>{next_session_label}</strong>"
        "</div>"
        "</div>"
        '<div class="gp-weekend-grid">'
        '<div class="gp-weekend-info">'
        '<div class="gp-weekend-card-grid">'
        f"{location_card}{weekend_card}{next_session_card}"
        "</div>"
        '<div class="gp-session-board">'
        '<div class="gp-session-board-title">'
        "<span>Weekend schedule</span>"
        "<small>Local time · Europe/Berlin</small>"
        "</div>"
        f"{sessions_html}"
        "</div>"
        "</div>"
        f"{track_html}"
        "</div>"
        "</div>"
        "</section>"
    )

    st.markdown(section_html, unsafe_allow_html=True)
