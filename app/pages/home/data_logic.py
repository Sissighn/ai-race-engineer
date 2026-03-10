import fastf1
import pandas as pd
import streamlit as st

from app.utils.error_ui import DOMAIN_EXCEPTIONS, show_domain_error
from src.data.latest_session import get_latest_sessions, get_season_results
from src.logging import get_logger

logger = get_logger(__name__)

_SESSION_COLS = [
    "Session1DateUtc",
    "Session2DateUtc",
    "Session3DateUtc",
    "Session4DateUtc",
    "Session5DateUtc",
]


@st.cache_resource
def load_event_results(year: int, event_key: str) -> dict:
    try:
        return get_season_results(year, event_key)
    except DOMAIN_EXCEPTIONS as e:
        logger.error(
            "Failed to load event results (domain exception)",
            year=year,
            event_key=event_key,
            error=str(e),
            exc_info=True,
        )
        return {}
    except Exception as e:
        logger.error(
            "Failed to load event results",
            year=year,
            event_key=event_key,
            error=str(e),
            exc_info=True,
        )
        return {}


def load_home_context() -> dict:
    try:
        session_data = get_latest_sessions()
        logger.info("Latest sessions loaded")
    except DOMAIN_EXCEPTIONS as e:
        logger.error(
            "Failed to load latest sessions (domain exception)",
            error=str(e),
            exc_info=True,
        )
        show_domain_error(
            e,
            fallback="Could not load latest session data.",
            context="home",
        )
        st.stop()
    except KeyError as e:
        logger.error(
            "Latest session payload missing key", missing_key=str(e), exc_info=True
        )
        st.error("Session-Daten haben ein ungültiges Format.")
        st.stop()
    except Exception as e:
        logger.error("Failed to load latest sessions", error=str(e), exc_info=True)
        st.error("Could not load latest session data.")
        st.stop()

    events_df = session_data["events"]
    latest_completed_idx = session_data["latest_completed_index"]
    next_session_name = session_data["next_session_name"]
    next_session_time = session_data["next_session_time"]

    display_event = _determine_display_event(
        events_df=events_df,
        latest_completed_idx=latest_completed_idx,
        next_session_time=next_session_time,
    )

    event_date = display_event["EventDate"]
    season_year = int(str(event_date)[:4])

    return {
        "events_df": events_df,
        "latest_completed_idx": latest_completed_idx,
        "next_session_name": next_session_name,
        "next_session_time": next_session_time,
        "display_event": display_event,
        "season_year": season_year,
        "event_key": display_event["OfficialEventName"],
    }


def get_started_events_for_season(season_year: int) -> list:
    try:
        all_events = fastf1.get_event_schedule(
            season_year, include_testing=False
        ).copy()
    except DOMAIN_EXCEPTIONS as e:
        logger.error(
            "Failed to load event schedule (domain exception)",
            season_year=season_year,
            error=str(e),
            exc_info=True,
        )
        show_domain_error(
            e,
            fallback="Could not load event schedule.",
            context="home",
        )
        st.stop()
    except Exception as e:
        logger.error(
            "Failed to load event schedule",
            season_year=season_year,
            error=str(e),
            exc_info=True,
        )
        st.error("Could not load event schedule.")
        st.stop()

    now = pd.Timestamp.now(tz="UTC")

    for col in _SESSION_COLS:
        if col in all_events.columns:
            all_events[col] = pd.to_datetime(all_events[col], utc=True)

    started_events = []
    for _, event in all_events.iterrows():
        if pd.notna(event.get("Session1DateUtc")) and event["Session1DateUtc"] < now:
            started_events.append(event)

    return started_events


def _determine_display_event(events_df, latest_completed_idx: int, next_session_time):
    now = pd.Timestamp.now(tz="UTC")

    if pd.notna(next_session_time) and next_session_time > now:
        display_event = None
        for _, event in events_df.iterrows():
            for col in _SESSION_COLS:
                if pd.notna(event.get(col)) and event[col] == next_session_time:
                    display_event = event
                    break
            if display_event is not None:
                break

        if display_event is None:
            display_event = events_df.iloc[latest_completed_idx]
        return display_event

    return events_df.iloc[latest_completed_idx]
