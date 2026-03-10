import os
from typing import Any, Optional

import fastf1
import pandas as pd
import numpy as np

from src.logging import get_logger
from src.exceptions import (
    SessionDataError,
    TelemetryError,
    FastF1APIError,
)
from src.config import settings

# ─────────────────────────────────────────────────────────────────────
# LOGGING SETUP
# ─────────────────────────────────────────────────────────────────────

logger = get_logger(__name__)

# ---------------------------------------------------------
# CONFIG & CACHE SETUP
# ---------------------------------------------------------

cache_path = str(settings.CACHE_DIR)
os.makedirs(cache_path, exist_ok=True)

# Cache aktivieren
try:
    if settings.FASTF1_CACHE_ENABLED:
        fastf1.Cache.enable_cache(cache_path)
        logger.info("FastF1 cache enabled", cache_path=cache_path)
    else:
        fastf1.Cache.disable_cache()
        logger.info("FastF1 cache disabled")
except Exception as e:
    logger.error("Failed to configure FastF1 cache", error=str(e))
    # Continue anyway

# -------------------------------------------------------
# HELPER: CUSTOM HASH FUNCTION
# -------------------------------------------------------


def hash_session_id(session: Any) -> str:
    """Generate hash for session caching."""
    if not session:
        return "no_session"
    try:
        event = (
            session.event["EventName"] if "EventName" in session.event else "Unknown"
        )
        name = session.name
        return f"{session.event.Year}_{event}_{name}"
    except Exception as e:
        logger.warning("Failed to generate session hash", error=str(e))
        return str(session)


# -------------------------------------------------------
# HELPER: CACHE CLEARING (SELF-HEALING)
# -------------------------------------------------------


def clear_specific_session_cache(year: int, grand_prix: str, session_type: str) -> bool:
    """
    Attempt to clear cache for a specific session if corrupted.

    Args:
        year: Championship year
        grand_prix: Grand Prix name
        session_type: Session type (Q, R, FP1, etc.)

    Returns:
        True if attempted, False on error
    """
    try:
        year_path = os.path.join(cache_path, str(year))
        if os.path.exists(year_path):
            # We don't automatically delete to avoid data loss,
            # but we signal that reload is needed.
            logger.info(
                "Cache clear requested",
                year=year,
                grand_prix=grand_prix,
                session_type=session_type,
            )
            pass

        return True
    except Exception as e:
        logger.error(
            "Error clearing cache",
            error=str(e),
            year=year,
            grand_prix=grand_prix,
        )
        return False


# ---------------------------------------------------------
# 1. LOAD SESSION (Robuster mit Retry)
# ---------------------------------------------------------


def load_session(year: int, grand_prix: str, session_type: str) -> Any:
    """
    Load a FastF1 session with corruption handling and logging.

    Args:
        year: Championship year
        grand_prix: Grand Prix name/location
        session_type: Session type (Q, R, FP1, FP2, FP3, S)

    Returns:
        FastF1 Session object or None if loading failed

    Raises:
        SessionDataError: If session is in the future
        FastF1APIError: If FastF1 API fails after retries
    """
    session = None
    log_context = {
        "year": year,
        "grand_prix": grand_prix,
        "session_type": session_type,
    }

    try:
        logger.info("Loading session", **log_context)

        # 1. Get session object
        session = fastf1.get_session(year, grand_prix, session_type)

        # 2. Check if session is in the future
        now = (
            pd.Timestamp.now(tz=session.date.tzinfo)
            if session.date.tzinfo
            else pd.Timestamp.now()
        )

        if session.date.tzinfo is None:
            now = pd.Timestamp.now()

        if session.date > now:
            msg = f"Session has not occurred yet: {session.date.date()}"
            logger.warning(msg, **log_context)
            raise SessionDataError(msg)

        # 3. Load data (normal attempt)
        logger.debug("Loading session data from FastF1", **log_context)
        session.load()
        logger.info("Session loaded successfully", **log_context)
        return session

    except SessionDataError:
        raise

    except Exception as e:
        error_msg = str(e)
        logger.error("Failed to load session", error=error_msg, **log_context)

        # Check for cache corruption
        if "not been loaded yet" in error_msg or "dictionary changed size" in error_msg:
            logger.warning(
                "Detected cache corruption, retrying without cache", **log_context
            )

            try:
                # Retry with cache disabled
                fastf1.Cache.disable_cache()
                session = fastf1.get_session(year, grand_prix, session_type)
                session.load()
                fastf1.Cache.enable_cache(cache_path)

                logger.info(
                    "Session loaded successfully after cache bypass",
                    **log_context,
                )
                return session

            except Exception as retry_err:
                fastf1.Cache.enable_cache(cache_path)
                msg = f"Failed to load session even after cache bypass: {retry_err}"
                logger.error(msg, error=str(retry_err), **log_context)
                raise FastF1APIError(msg) from retry_err

        else:
            # Other error (e.g., API down, network issue)
            msg = f"Error loading session: {e}"
            logger.error(msg, error=error_msg, **log_context)
            raise FastF1APIError(msg) from e


# ---------------------------------------------------------
# 2. LOAD TELEMETRY
# ---------------------------------------------------------


def load_telemetry(session: Any, driver_code: str) -> Optional[pd.DataFrame]:
    """
    Load and process telemetry for a specific driver's fastest lap.

    Args:
        session: FastF1 Session object
        driver_code: 3-letter driver code (e.g., 'VER', 'HAM')

    Returns:
        Telemetry DataFrame or None if unavailable

    Raises:
        TelemetryError: If telemetry processing fails
    """
    log_context = {"driver": driver_code, "session": str(session)[:50]}

    if session is None:
        logger.warning("Session is None, cannot load telemetry", **log_context)
        return None

    try:
        logger.debug("Loading telemetry", **log_context)

        # Check if session has laps data
        if not hasattr(session, "laps"):
            msg = "Session has no laps data"
            logger.error(msg, **log_context)
            raise TelemetryError(msg)

        laps = session.laps.pick_drivers(driver_code)
        if laps.empty:
            msg = f"No laps found for driver {driver_code}"
            logger.warning(msg, **log_context)
            return None

        fastest = laps.pick_fastest()
        if fastest is None:
            msg = f"No fastest lap found for driver {driver_code}"
            logger.warning(msg, **log_context)
            return None

        # get_car_data / add_distance can fail for very recent races
        # where FastF1 hasn't fully processed the telemetry yet.
        # In that case return None gracefully instead of crashing.
        try:
            tel = fastest.get_car_data().add_distance()
        except Exception as tel_err:
            msg = f"Car telemetry not yet available for {driver_code}: {tel_err}"
            logger.warning(msg, error=str(tel_err), **log_context)
            return None

        if tel is None or tel.empty:
            logger.warning("Empty telemetry returned", **log_context)
            return None

        # Ensure nGear column exists
        if "nGear" not in tel.columns:
            tel["nGear"] = 0

        logger.info(
            "Telemetry loaded successfully",
            **log_context,
            samples=len(tel),
        )
        return tel

    except TelemetryError:
        raise

    except Exception as e:
        msg = f"Failed to load telemetry for {driver_code}"
        logger.error(msg, error=str(e), **log_context, exc_info=True)
        raise TelemetryError(msg) from e


# ---------------------------------------------------------
# 3. LOAD TELEMETRY WITH POSITION
# ---------------------------------------------------------


def load_telemetry_with_position(
    session: Any, driver_code: str
) -> Optional[pd.DataFrame]:
    """
    Load telemetry with GPS position data for track mapping.

    Args:
        session: FastF1 Session object
        driver_code: 3-letter driver code

    Returns:
        Merged telemetry+position DataFrame or None

    Raises:
        TelemetryError: If data loading fails
    """
    log_context = {"driver": driver_code, "session": str(session)[:50]}

    if session is None:
        logger.warning("Session is None, cannot load position data", **log_context)
        return None

    try:
        logger.debug("Loading telemetry with position", **log_context)

        if not hasattr(session, "laps"):
            msg = "Session has no laps data"
            logger.error(msg, **log_context)
            raise TelemetryError(msg)

        laps = session.laps.pick_drivers(driver_code)
        if laps.empty:
            msg = f"No laps for driver {driver_code}"
            logger.warning(msg, **log_context)
            return None

        fastest = laps.pick_fastest()
        if fastest is None:
            msg = f"No fastest lap for driver {driver_code}"
            logger.warning(msg, **log_context)
            return None

        # Position data may be unavailable (especially pre-2018 seasons)
        try:
            pos = fastest.get_telemetry()[["Time", "X", "Y"]].copy()
        except Exception as pos_err:
            msg = f"No position data available for {driver_code} (common in older seasons)"
            logger.warning(msg, error=str(pos_err), **log_context)
            return None

        pos["Time_s"] = pos["Time"].dt.total_seconds()
        car = fastest.get_car_data().copy()
        car["Time_s"] = car["Time"].dt.total_seconds()

        # Merge position and car data
        merged = pd.merge_asof(
            pos.sort_values("Time_s"),
            car.sort_values("Time_s"),
            on="Time_s",
            direction="nearest",
            tolerance=0.03,
        )

        # Fix Speed Gaps
        if "Speed" in merged.columns and merged["Speed"].isna().sum() > 0:
            dx = np.diff(merged["X"])
            dy = np.diff(merged["Y"])
            dist_xy = np.sqrt(dx**2 + dy**2)
            dt = np.diff(merged["Time_s"])
            dt = np.where(dt == 0, np.nan, dt)
            speed_calc = np.zeros(len(merged))
            speed_calc[1:] = (dist_xy / dt) * 3.6
            merged["Speed"] = merged["Speed"].fillna(
                pd.Series(speed_calc, index=merged.index)
            )

        # Fix Distance
        if "Distance" not in merged.columns or merged["Distance"].isna().sum() > 0:
            dx = np.diff(merged["X"])
            dy = np.diff(merged["Y"])
            d = np.sqrt(dx**2 + dy**2)
            merged["Distance"] = np.concatenate([[0], np.cumsum(d)])

        logger.info(
            "Position data loaded and merged",
            **log_context,
            merged_samples=len(merged),
        )
        return merged

    except TelemetryError:
        raise

    except Exception as e:
        msg = f"Failed to load position telemetry for {driver_code}"
        logger.error(msg, error=str(e), **log_context, exc_info=True)
        raise TelemetryError(msg) from e


# ---------------------------------------------------------
# 4. GET TRACK LIST (DYNAMIC)
# ---------------------------------------------------------


def get_tracks_for_year(year: int) -> list[str]:
    """
    Get list of tracks for a given championship year.

    Args:
        year: Championship year

    Returns:
        List of track names/locations

    Note:
        Returns empty list if API fails; UI will fallback to hardcoded list
    """
    log_context = {"year": year}

    try:
        logger.debug("Fetching track schedule", **log_context)
        schedule = fastf1.get_event_schedule(year, include_testing=False)

        if schedule.empty:
            logger.warning("Empty schedule returned from FastF1", **log_context)
            return []

        if "Location" in schedule.columns:
            tracks = schedule["Location"].dropna().astype(str).tolist()
        elif "EventName" in schedule.columns:
            tracks = schedule["EventName"].dropna().astype(str).tolist()
        else:
            msg = "Schedule has unexpected format"
            logger.error(msg, **log_context, columns=list(schedule.columns))
            return []

        # Deduplicate
        seen = set()
        result = [
            x.strip()
            for x in tracks
            if x.strip() and not (x.strip() in seen or seen.add(x.strip()))
        ]

        logger.info("Track schedule fetched", **log_context, count=len(result))
        return result

    except Exception as e:
        msg = f"Failed to fetch schedule for {year}"
        logger.error(msg, error=str(e), **log_context, exc_info=True)
        # Return empty list - UI will fallback to hardcoded list
        return []
