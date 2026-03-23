"""
Session and Driver Selection Module

Handles user interface for selecting F1 season, track, and session type,
loading session data from FastF1, and initiating driver comparison analysis.
Provides caching for session data and track calendars to optimize performance.
"""

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
from src.models import ComparisonSessionState

logger = get_logger(__name__)

# Fallback track list used when FastF1 calendar API fails or returns no data
# Contains major F1 circuits as a safe default
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
    """
    Cache-decorated wrapper for loading F1 session data.

    Uses Streamlit's cache_resource to persist session data across reruns,
    reducing API calls to FastF1 and improving application responsiveness.

    Args:
        year (int): F1 season year
        track (str): Circuit/track name
        session_type (str): Session type code ('Q'=Qualifying, 'R'=Race, 'FP1-3'=Practice)

    Returns:
        Session object containing full telemetry and timing data, or None if unavailable
    """
    return load_session(year, track, session_type)


@st.cache_data(show_spinner=False)
def get_tracks_for_year_cached(year: int) -> list[str]:
    """
    Cache-decorated wrapper for retrieving F1 calendar tracks for a given year.

    Uses Streamlit's cache_data to cache calendar information across reruns.
    Reduces repeated API calls to FastF1 service.

    Args:
        year (int): F1 season year

    Returns:
        List of track names scheduled for the given season
    """
    return get_tracks_for_year_for_ui(year)


def render_session_selection() -> tuple[int, str, str]:
    """
    Render UI for selecting F1 season, track, and session type.

    Provides three dropdown selectors arranged horizontally:
    - Year: Current year down to 2017
    - Track: Calendar tracks for selected year (with fallback)
    - Session Type: Q (Qualifying), R (Race), FP1/FP2/FP3 (Practice)

    Returns:
        tuple[int, str, str]: Selected (year, track, session_type)
    """
    st.markdown(
        "<h2 class='section-title'>Session Selection</h2>", unsafe_allow_html=True
    )

    # Create three-column layout for year/track/session selection
    col1, col2, col3 = st.columns(3)

    with col1:
        # Year selection: current year down to 2017
        current_year = datetime.now().year
        year_options = list(range(current_year, 2017, -1))
        year = st.selectbox("Year", year_options, index=0)

    with col2:
        # Track selection: fetch from FastF1 with fallback to predefined list
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

        # Use fallback if calendar fetch failed or returned empty
        if not tracks_for_year:
            tracks_for_year = _FALLBACK_TRACKS

        # Default to Silverstone if available, otherwise first track
        default_idx = (
            tracks_for_year.index("Silverstone")
            if "Silverstone" in tracks_for_year
            else 0
        )
        track = st.selectbox("Track", tracks_for_year, index=default_idx)

    with col3:
        # Session type selection
        session_type = st.selectbox("Session", ["Q", "R", "FP1", "FP2", "FP3"])

    return year, track, session_type


def handle_session_load(year: int, track: str, session_type: str) -> None:
    """
    Handle session data loading when user clicks 'Load session' button.

    Fetches session data from FastF1, builds driver map, stores in session state,
    and warns about drivers with no telemetry. Handles domain and unexpected exceptions.
    Triggers app rerun on success to update UI with loaded data.

    Args:
        year (int): Selected F1 season year
        track (str): Selected track name
        session_type (str): Selected session type code
    """
    # Exit early if button not clicked
    if not st.button("Load session"):
        return

    try:
        # Attempt to load session data from FastF1 API
        logger.info(
            "Loading session", year=year, track=track, session_type=session_type
        )
        session = load_session_cached(year, track, session_type)

        # Validate that session was loaded successfully
        if session is None:
            st.error("Could not load session data from FastF1.")
            return

        # Build driver map: full names -> abbreviations, identify drivers without telemetry
        drivers_full, driver_map, no_tel_drivers = build_driver_map(session)

        # Store session data in Streamlit session state for downstream use
        st.session_state["session"] = session
        st.session_state["drivers_full"] = drivers_full
        st.session_state["driver_map"] = driver_map

        # Warn user about drivers without car telemetry (cannot be compared)
        if no_tel_drivers:
            st.warning(
                f"⚠️ No car telemetry available for: **{', '.join(no_tel_drivers)}** "
                "in this session (marked in the dropdowns below). "
                "These drivers cannot be compared."
            )

        # Notify success and trigger UI rerun to display driver selection
        st.success(f"Loaded: {year} {track} {session_type}")
        st.rerun()

    except DOMAIN_EXCEPTIONS as e:
        # Handle known domain-specific exceptions
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
        # Handle unexpected exceptions
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
    """
    Render UI for selecting two drivers to compare from the loaded session.

    Displays two dropdown selectors (Driver A and Driver B) populated from
    the session's driver list, respecting FastF1 telemetry availability.
    Returns selected drivers only when 'Compare drivers' button is clicked.

    Returns:
        tuple[str, str] | None: Selected (driver_a_full, driver_b_full) or None if not ready
    """
    # Early return if session data not loaded yet
    drivers_full = st.session_state.get("drivers_full")
    if not drivers_full:
        return None

    st.markdown(
        "<h2 class='section-title'>Driver Selection</h2>", unsafe_allow_html=True
    )

    # Create two-column layout for driver A and driver B selection
    col_a, col_b = st.columns(2)
    with col_a:
        driver_a_full = st.selectbox("Driver A", drivers_full, key="drvA")
    with col_b:
        driver_b_full = st.selectbox("Driver B", drivers_full, key="drvB")

    # Return selected drivers only when compare button is clicked
    if not st.button("Compare drivers"):
        return None

    return driver_a_full, driver_b_full


def handle_driver_comparison(driver_a_full: str, driver_b_full: str) -> None:
    """
    Handle driver comparison analysis when two drivers are selected.

    Retrieves driver abbreviations from map, performs telemetry comparison analysis,
    validates telemetry availability, and stores comparison results in session state.
    Handles domain and unexpected exceptions with appropriate error messages.
    Triggers app rerun to display comparison results.

    Args:
        driver_a_full (str): Full name of first driver
        driver_b_full (str): Full name of second driver
    """
    try:
        # Retrieve driver abbreviations and session from session state
        driver_a = st.session_state["driver_map"][driver_a_full]
        driver_b = st.session_state["driver_map"][driver_b_full]
        session = st.session_state["session"]
        logger.info("Comparing drivers", driver_a=driver_a, driver_b=driver_b)

        # Perform telemetry comparison analysis with loading spinner
        with st.spinner("Analyzing Telemetry..."):
            service_result = compare_session_drivers(session, driver_a, driver_b)

            # Validate that both drivers have car telemetry available
            if service_result.missing:
                st.error(
                    f"❌ No car telemetry data available for: **{', '.join(service_result.missing)}** "
                    "in this session. The F1 data API does not provide car data for "
                    "every driver in every session. Please select a different driver."
                )
                st.stop()

        # Store comparison results in session state for downstream visualization
        st.session_state["compare_result"] = ComparisonSessionState(
            session=session,
            driver_a=driver_a,
            driver_b=driver_b,
            tel_a=service_result.tel_a,
            tel_b=service_result.tel_b,
            comp=service_result.comp,
            tl=service_result.tl,
        )
        logger.info("Comparison complete", driver_a=driver_a, driver_b=driver_b)
        # Trigger UI rerun to display comparison results
        st.rerun()

    except DOMAIN_EXCEPTIONS as e:
        # Handle known domain-specific exceptions
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
        # Handle unexpected exceptions
        logger.error("Driver comparison failed", error=str(e), exc_info=True)
        st.error(f"Compare failed: {e}")
