import streamlit as st

from app.utils.error_ui import DOMAIN_EXCEPTIONS, show_domain_error
from src.application.home_service import (
    get_home_context,
    get_season_started_events,
    load_event_results as load_event_results_core,
)
from src.logging import get_logger
from src.models import HomeContextPayload

logger = get_logger(__name__)


@st.cache_resource
def load_event_results(year: int, event_key: str) -> dict:
    try:
        return load_event_results_core(year, event_key)
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


@st.cache_data(ttl=600, show_spinner="Loading F1 schedule...")
def get_home_context_cached(year: int | None = None) -> HomeContextPayload:
    return get_home_context(year)


@st.cache_data(show_spinner=False)
def get_season_started_events_cached(season_year: int) -> list:
    return get_season_started_events(season_year)


def load_home_context() -> HomeContextPayload:
    try:
        session_data = get_home_context_cached()
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

    return session_data


def get_started_events_for_season(season_year: int) -> list:
    try:
        return get_season_started_events_cached(season_year)
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
