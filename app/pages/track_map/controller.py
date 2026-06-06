from datetime import datetime

import streamlit as st

from app.components.navbar import navbar
from app.components.track_map import plot_pit_wall_track_replay
from app.utils.error_ui import DOMAIN_EXCEPTIONS, show_domain_error
from app.utils.ui import apply_dark_page_shell, load_css
from src.application.comparison_service import build_driver_map, get_tracks_for_year_for_ui
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

_SESSION_OPTIONS = {
    "Qualifying": "Q",
    "Race": "R",
}


@st.cache_resource(show_spinner="Loading FastF1 session...")
def _load_track_map_session(year: int, track: str, session_type: str):
    return load_session(year, track, session_type)


@st.cache_data(show_spinner=False)
def _get_tracks_for_year(year: int) -> list[str]:
    return get_tracks_for_year_for_ui(year)


def _render_header() -> None:
    st.markdown(
        """
        <section class="pit-wall-hero">
          <div>
            <span class="pit-wall-kicker">Race Control / Telemetry Replay</span>
            <h1>Live Track Map</h1>
            <p>
              Pit-wall style multi-car replay from FastF1 position telemetry.
              Current implementation supports Qualifying and Race sessions.
            </p>
          </div>
          <div class="pit-wall-status">
            <span></span>
            FASTF1 POSITION FEED
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_session_controls() -> tuple[int, str, str, str]:
    st.markdown("<h2 class='section-title'>Session Feed</h2>", unsafe_allow_html=True)

    col_year, col_track, col_session = st.columns([1, 2, 1])

    with col_year:
        current_year = datetime.now().year
        year_options = list(range(current_year, 2017, -1))
        year = st.selectbox("Year", year_options, index=0, key="trackmap_year")

    with col_track:
        try:
            tracks = _get_tracks_for_year(year)
        except Exception as e:
            logger.warning("Track map calendar load failed", year=year, error=str(e))
            tracks = []

        if not tracks:
            tracks = _FALLBACK_TRACKS

        default_idx = tracks.index("Silverstone") if "Silverstone" in tracks else 0
        track = st.selectbox("Track", tracks, index=default_idx, key="trackmap_track")

    with col_session:
        session_label = st.selectbox(
            "Session",
            list(_SESSION_OPTIONS.keys()),
            index=0,
            key="trackmap_session_label",
        )

    return year, track, session_label, _SESSION_OPTIONS[session_label]


def _load_session_state(year: int, track: str, session_label: str, session_type: str) -> None:
    if not st.button("Load track feed", key="trackmap_load"):
        return

    try:
        logger.info(
            "Loading track map session",
            year=year,
            track=track,
            session_type=session_type,
        )
        session = _load_track_map_session(year, track, session_type)
        drivers_full, driver_map, no_tel_drivers = build_driver_map(session)

        if not drivers_full:
            st.error("No drivers found for this session.")
            return

        st.session_state["trackmap_session"] = session
        st.session_state["trackmap_session_meta"] = {
            "year": year,
            "track": track,
            "session_label": session_label,
            "session_type": session_type,
        }
        st.session_state["trackmap_drivers_full"] = drivers_full
        st.session_state["trackmap_driver_map"] = driver_map

        if no_tel_drivers:
            st.warning(
                "No car telemetry available for: "
                + ", ".join(no_tel_drivers)
                + ". They may not render in the replay."
            )

        st.success(f"Loaded track feed: {year} {track} {session_label}")
        st.rerun()

    except DOMAIN_EXCEPTIONS as e:
        logger.error(
            "Track map session load failed",
            year=year,
            track=track,
            session_type=session_type,
            error=str(e),
            exc_info=True,
        )
        show_domain_error(e, fallback="Error loading track map session.", context="track-map")
    except Exception as e:
        logger.error(
            "Track map session load failed unexpectedly",
            year=year,
            track=track,
            session_type=session_type,
            error=str(e),
            exc_info=True,
        )
        st.error(f"Error loading track feed: {e}")


def _render_loaded_replay() -> None:
    session = st.session_state.get("trackmap_session")
    meta = st.session_state.get("trackmap_session_meta")
    drivers_full = st.session_state.get("trackmap_drivers_full")
    driver_map = st.session_state.get("trackmap_driver_map")

    if not session or not meta or not drivers_full or not driver_map:
        st.info("Load a Qualifying or Race session to start the live track map replay.")
        return

    st.markdown("<h2 class='section-title'>Pit-Wall Replay</h2>", unsafe_allow_html=True)

    default_selection = drivers_full[: min(6, len(drivers_full))]
    selected_labels = st.multiselect(
        "Cars",
        drivers_full,
        default=default_selection,
        key="trackmap_selected_drivers",
    )

    col_frames, col_note = st.columns([1, 2])
    with col_frames:
        frame_count = st.slider(
            "Replay resolution",
            min_value=48,
            max_value=180,
            value=120,
            step=12,
            key="trackmap_frame_count",
        )

    with col_note:
        st.markdown(
            """
            <div class="pit-wall-note">
              Replay uses fastest-lap position telemetry per selected driver.
              It is a race-engineering visualization, not an official live timing feed.
            </div>
            """,
            unsafe_allow_html=True,
        )

    driver_codes = [driver_map[label] for label in selected_labels if label in driver_map]

    with st.spinner("Building pit-wall track replay..."):
        plot_pit_wall_track_replay(
            session=session,
            driver_codes=driver_codes,
            track=meta["track"],
            session_label=f"{meta['year']} {meta['session_label']}",
            frame_count=frame_count,
        )


def run_page() -> None:
    st.set_page_config(page_title="Live Track Map – AI Race Engineer", layout="wide")

    apply_dark_page_shell()
    load_css()
    navbar()

    _render_header()
    year, track, session_label, session_type = _render_session_controls()
    _load_session_state(year, track, session_label, session_type)
    _render_loaded_replay()
