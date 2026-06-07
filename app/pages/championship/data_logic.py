import pandas as pd
import streamlit as st

from app.utils.error_ui import DOMAIN_EXCEPTIONS, show_domain_error
from src.application.championship_service import calculate_championship_standings
from src.logging import get_logger
from src.models import ChampionshipStandingsPayload

logger = get_logger(__name__)


def get_season_year_options(history: int = 4) -> list[int]:
    current_year = int(pd.Timestamp.now().year)
    return [current_year - idx for idx in range(history + 1)]


@st.cache_data(ttl=600, show_spinner="Loading championship standings...")
def fetch_championship_standings(year: int) -> ChampionshipStandingsPayload:
    try:
        return calculate_championship_standings(year)
    except DOMAIN_EXCEPTIONS as exc:
        logger.error(
            "Failed to load championship standings (domain exception)",
            year=year,
            error=str(exc),
            exc_info=True,
        )
        return ChampionshipStandingsPayload(
            drivers_df=pd.DataFrame(),
            constructors_df=pd.DataFrame(),
            season_year=year,
            events_count=0,
            sessions_loaded=0,
        )
    except Exception as exc:
        logger.error(
            "Failed to load championship standings",
            year=year,
            error=str(exc),
            exc_info=True,
        )
        show_domain_error(
            exc,
            fallback="Could not load championship standings.",
            context="championship",
        )
        return ChampionshipStandingsPayload(
            drivers_df=pd.DataFrame(),
            constructors_df=pd.DataFrame(),
            season_year=year,
            events_count=0,
            sessions_loaded=0,
        )
