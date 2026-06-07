from __future__ import annotations

from typing import Iterable

import pandas as pd
from src.infrastructure.fastf1 import get_event_schedule, get_session
from src.logging import get_logger
from src.models import ChampionshipStandingsPayload

logger = get_logger(__name__)

_SCORING_SESSION_LABELS = {
    "Race": "R",
    "Sprint": "S",
}

_SESSION_LABEL_COLUMNS = [f"Session{i}" for i in range(1, 6)]
_SESSION_DATE_COLUMNS = [f"Session{i}DateUtc" for i in range(1, 6)]


def calculate_championship_standings(year: int) -> ChampionshipStandingsPayload:
    """Calculate the current driver and constructor standings for a season."""
    events = get_event_schedule(year, include_testing=False)

    if events is None or events.empty:
        logger.warning(
            "No event schedule available for championship standings", year=year
        )
        return ChampionshipStandingsPayload(
            drivers_df=pd.DataFrame(),
            constructors_df=pd.DataFrame(),
            season_year=year,
            events_count=0,
            sessions_loaded=0,
        )

    points_frames = []
    sessions_loaded = 0
    now = pd.Timestamp.now(tz="UTC")

    for _, event in events.iterrows():
        event_key = event.get("OfficialEventName")
        if not isinstance(event_key, str) or not event_key.strip():
            continue

        completed_scoring_sessions = _get_completed_scoring_sessions(event, now)
        if not completed_scoring_sessions:
            continue

        for session_type in completed_scoring_sessions:
            session_results = _load_session_results(year, event_key, session_type)
            if session_results is None or session_results.empty:
                continue

            if "Points" not in session_results.columns:
                continue

            session_results = session_results.copy()
            session_results["Points"] = pd.to_numeric(
                session_results["Points"], errors="coerce"
            ).fillna(0.0)

            if session_results["Points"].sum() <= 0:
                continue

            session_results["EventName"] = event.get("EventName", event_key)
            session_results["SeasonYear"] = year
            points_frames.append(session_results)
            sessions_loaded += 1

    if not points_frames:
        logger.info("No championship points data available yet", year=year)
        return ChampionshipStandingsPayload(
            drivers_df=pd.DataFrame(),
            constructors_df=pd.DataFrame(),
            season_year=year,
            events_count=0,
            sessions_loaded=0,
        )

    merged = pd.concat(points_frames, ignore_index=True)
    drivers_df = _build_driver_standings(merged)
    constructors_df = _build_constructor_standings(merged)
    events_count = merged["EventName"].nunique()

    return ChampionshipStandingsPayload(
        drivers_df=drivers_df,
        constructors_df=constructors_df,
        season_year=year,
        events_count=events_count,
        sessions_loaded=sessions_loaded,
    )


def _get_completed_scoring_sessions(event: pd.Series, now: pd.Timestamp) -> list[str]:
    completed = []
    for label_col, date_col in zip(_SESSION_LABEL_COLUMNS, _SESSION_DATE_COLUMNS):
        session_label = event.get(label_col)
        session_date = event.get(date_col)

        if not isinstance(session_label, str):
            continue
        if pd.isna(session_date):
            continue

        scoring_type = _SCORING_SESSION_LABELS.get(session_label)
        if scoring_type is None:
            continue

        if pd.to_datetime(session_date, utc=True) < now:
            completed.append(scoring_type)

    return completed


def _load_session_results(
    year: int, event_key: str, session_type: str
) -> pd.DataFrame | None:
    try:
        session = get_session(year, event_key, session_type)
        session.load(laps=False, telemetry=False, weather=False, messages=False)
    except Exception as exc:
        logger.warning(
            "Could not load session for championship points",
            year=year,
            event_key=event_key,
            session_type=session_type,
            error=str(exc),
        )
        return None

    if session.results is None or session.results.empty:
        return None

    results = session.results.copy()
    if "Points" not in results.columns:
        return results

    if "FullName" not in results.columns:
        results["FullName"] = (
            results.get("FirstName", "").fillna("")
            + " "
            + results.get("LastName", "").fillna("")
        )

    return results


def _build_driver_standings(results: pd.DataFrame) -> pd.DataFrame:
    drivers = results.copy()
    drivers["DriverName"] = drivers["FullName"].fillna(
        drivers["Abbreviation"].astype(str)
    )

    aggregation = {
        "DriverName": "last",
        "TeamName": "last",
        "Points": "sum",
        "EventName": pd.Series.nunique,
    }

    standings = (
        drivers.groupby("Abbreviation", dropna=False, as_index=False)
        .agg(aggregation)
        .rename(columns={"EventName": "Events", "TeamName": "Team"})
    )
    standings = standings.sort_values(["Points", "DriverName"], ascending=[False, True])
    standings.insert(0, "Position", range(1, len(standings) + 1))
    return standings.reset_index(drop=True)


def _build_constructor_standings(results: pd.DataFrame) -> pd.DataFrame:
    constructors = results.copy()
    aggregation = {
        "Abbreviation": pd.Series.nunique,
        "Points": "sum",
        "EventName": pd.Series.nunique,
    }

    standings = (
        constructors.groupby("TeamName", dropna=False, as_index=False)
        .agg(aggregation)
        .rename(
            columns={
                "Abbreviation": "Drivers",
                "EventName": "Events",
                "TeamName": "Team",
            }
        )
    )
    standings = standings.sort_values(["Points", "Team"], ascending=[False, True])
    standings.insert(0, "Position", range(1, len(standings) + 1))
    return standings.reset_index(drop=True)
