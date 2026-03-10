from datetime import datetime

import streamlit as st

from app.utils.error_ui import DOMAIN_EXCEPTIONS, show_domain_error
from src.application.comparison_service import (
    build_driver_map,
    compare_session_drivers,
    get_tracks_for_year_for_ui,
)
from src.data.load_data import load_session
from src.logging import get_logger

logger = get_logger(__name__)

_FALLBACK_TRACKS = [
    "Silverstone",
    "Monza",
    "Monaco",
    "Spa",
    "Red Bull Ring",
    "Suzuka",
    "Interlagos",
    "Bahrain",
    "Barcelona",
]


@st.cache_resource(show_spinner="Loading session data...")
def load_session_cached(year: int, track: str, session_type: str):
    return load_session(year, track, session_type)


@st.cache_data(show_spinner=False)
def get_tracks_for_year_cached(year: int) -> list[str]:
    return get_tracks_for_year_for_ui(year)


def render_session_selection() -> tuple[int, str, str]:
    st.markdown(
        "<h2 class='section-title'>Session Selection</h2>", unsafe_allow_html=True
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        current_year = datetime.now().year
        year_options = list(range(current_year, 2017, -1))
        year = st.selectbox("Year", year_options, index=0)

    with col2:
        with st.spinner(f"Loading {year} Calendar..."):
            try:
                tracks_for_year = get_tracks_for_year_cached(year)
                logger.debug(
                    "Tracks loaded", year=year, count=len(tracks_for_year or [])
                )
            except Exception as e:
                logger.warning(
                    "Track list load failed, using fallback", year=year, error=str(e)
                )
                tracks_for_year = []

        if not tracks_for_year:
            tracks_for_year = _FALLBACK_TRACKS

        default_idx = (
            tracks_for_year.index("Silverstone")
            if "Silverstone" in tracks_for_year
            else 0
        )
        track = st.selectbox("Track", tracks_for_year, index=default_idx)

    with col3:
        session_type = st.selectbox("Session", ["Q", "R", "FP1", "FP2", "FP3"])

    return year, track, session_type


def handle_session_load(year: int, track: str, session_type: str) -> None:
    if not st.button("Load session"):
        return

    try:
        logger.info(
            "Loading session", year=year, track=track, session_type=session_type
        )
        session = load_session_cached(year, track, session_type)

        if session is None:
            st.error("Could not load session data from FastF1.")
            return

        drivers_full, driver_map, no_tel_drivers = build_driver_map(session)

        st.session_state["session"] = session
        st.session_state["drivers_full"] = drivers_full
        st.session_state["driver_map"] = driver_map

        if no_tel_drivers:
            st.warning(
                f"⚠️ No car telemetry available for: **{', '.join(no_tel_drivers)}** "
                "in this session (marked in the dropdowns below). "
                "These drivers cannot be compared."
            )

        st.success(f"Loaded: {year} {track} {session_type}")
        st.rerun()

    except DOMAIN_EXCEPTIONS as e:
        logger.error(
            "Session load failed (domain exception)",
            year=year,
            track=track,
            session_type=session_type,
            error=str(e),
            exc_info=True,
        )
        show_domain_error(e, fallback="Error loading session.", context="comparison")
    except Exception as e:
        logger.error(
            "Session load failed",
            year=year,
            track=track,
            session_type=session_type,
            error=str(e),
            exc_info=True,
        )
        st.error(f"Error loading session: {e}")


def render_driver_selection() -> tuple[str, str] | None:
    drivers_full = st.session_state.get("drivers_full")
    if not drivers_full:
        return None

    st.markdown(
        "<h2 class='section-title'>Driver Selection</h2>", unsafe_allow_html=True
    )

    col_a, col_b = st.columns(2)
    with col_a:
        driver_a_full = st.selectbox("Driver A", drivers_full, key="drvA")
    with col_b:
        driver_b_full = st.selectbox("Driver B", drivers_full, key="drvB")

    if not st.button("Compare drivers"):
        return None

    return driver_a_full, driver_b_full


def handle_driver_comparison(driver_a_full: str, driver_b_full: str) -> None:
    try:
        driver_a = st.session_state["driver_map"][driver_a_full]
        driver_b = st.session_state["driver_map"][driver_b_full]
        session = st.session_state["session"]
        logger.info("Comparing drivers", driver_a=driver_a, driver_b=driver_b)

        with st.spinner("Analyzing Telemetry..."):
            service_result = compare_session_drivers(session, driver_a, driver_b)

            if service_result["missing"]:
                st.error(
                    f"❌ No car telemetry data available for: **{', '.join(service_result['missing'])}** "
                    "in this session. The F1 data API does not provide car data for "
                    "every driver in every session. Please select a different driver."
                )
                st.stop()

        st.session_state["compare_result"] = {
            "session": session,
            "driverA": driver_a,
            "driverB": driver_b,
            "telA": service_result["telA"],
            "telB": service_result["telB"],
            "comp": service_result["comp"],
            "tl": service_result["tl"],
        }
        logger.info("Comparison complete", driver_a=driver_a, driver_b=driver_b)
        st.rerun()

    except DOMAIN_EXCEPTIONS as e:
        logger.error(
            "Driver comparison failed (domain exception)",
            driver_a=driver_a_full,
            driver_b=driver_b_full,
            error=str(e),
            exc_info=True,
        )
        show_domain_error(e, fallback="Compare failed.", context="comparison")
        st.caption(f"Details: `{type(e).__name__}: {e}`")
    except Exception as e:
        logger.error("Driver comparison failed", error=str(e), exc_info=True)
        st.error(f"Compare failed: {e}")
