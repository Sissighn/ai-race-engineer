import os
import fastf1
import pandas as pd
import numpy as np
import streamlit as st

# ---------------------------------------------------------
# CORRECT PROJECT ROOT
# ---------------------------------------------------------
this_file = os.path.abspath(__file__)
data_folder = os.path.dirname(this_file)
src_folder = os.path.dirname(data_folder)
project_root = os.path.dirname(src_folder)

cache_path = os.path.join(project_root, "cache")
os.makedirs(cache_path, exist_ok=True)

# Cache aktivieren
fastf1.Cache.enable_cache(cache_path)


# -------------------------------------------------------
# HELPER: CUSTOM HASH FUNCTION (FIXED)
# Prevents "Cannot hash argument 'session'" error
# -------------------------------------------------------
def hash_session_id(session):
    """
    Erstellt eine eindeutige ID für die Session.
    Fix: Wir nutzen session.date statt session.event.Year,
    da das Attribut 'Year' manchmal fehlt.
    """
    if not session:
        return "no_session"

    try:
        # Robustester Weg: EventName + SessionName + Eindeutiger Zeitstempel
        event_name = session.event["EventName"]
        session_name = session.name
        date_str = str(session.date)  # Z.B. "2024-03-02 15:00:00"
        return f"{event_name}_{session_name}_{date_str}"
    except Exception:
        # Fallback, falls irgendetwas an der Struktur unerwartet ist
        return str(session)


# ---------------------------------------------------------
# LOAD SESSION
# ---------------------------------------------------------
@st.cache_resource(show_spinner="Loading session data...")
def load_session(year: int, grand_prix: str, session_type: str):
    """
    Load a FastF1 session (modern API).
    """
    try:
        session = fastf1.get_session(year, grand_prix, session_type)
        session.load()  # Lädt Telemetry, Positioning, Weather
        return session
    except Exception as e:
        st.error(f"Error loading session: {e}")
        return None


# ---------------------------------------------------------
# LOAD BASIC TELEMETRY (DISTANCE, SPEED, THROTTLE, BRAKE)
# ---------------------------------------------------------
@st.cache_data(
    show_spinner="Loading telemetry for driver...",
    hash_funcs={fastf1.core.Session: hash_session_id},
)
def load_telemetry(session, driver_code: str):
    """
    Load the fastest lap for the given driver with distance added.
    """
    if session is None:
        return None

    try:
        laps = session.laps.pick_driver(driver_code)

        if laps.empty:
            return None

        fastest = laps.pick_fastest()

        if fastest is None:
            return None

        tel = fastest.get_car_data().add_distance()

        # Sicherstellen, dass nGear existiert
        if "nGear" not in tel.columns:
            tel["nGear"] = 0

        return tel

    except Exception as e:
        print(f"Error loading telemetry for {driver_code}: {e}")
        return None


# ---------------------------------------------------------
# LOAD TELEMETRY WITH X/Y POSITION FOR TRACK MAP
# ---------------------------------------------------------
@st.cache_data(
    show_spinner="Loading telemetry with position data...",
    hash_funcs={fastf1.core.Session: hash_session_id},
)
def load_telemetry_with_position(session, driver_code: str):
    """
    Loads full telemetry including X/Y GPS and real Speed.
    Handles missing Distance/Speed by recalculating from X/Y.
    """
    if session is None:
        return None

    try:
        laps = session.laps.pick_driver(driver_code)
        if laps.empty:
            return None

        fastest = laps.pick_fastest()
        if fastest is None:
            return None

        # ----------------------------
        # Load position telemetry (X, Y)
        # ----------------------------
        pos = fastest.get_telemetry()[["Time", "X", "Y"]].copy()
        pos["Time_s"] = pos["Time"].dt.total_seconds()

        # ----------------------------
        # Load car telemetry (Speed, Brake, Throttle, RPM, Gear)
        # ----------------------------
        car = fastest.get_car_data().copy()
        car["Time_s"] = car["Time"].dt.total_seconds()

        # ----------------------------
        # Merge (nearest time)
        # ----------------------------
        merged = pd.merge_asof(
            pos.sort_values("Time_s"),
            car.sort_values("Time_s"),
            on="Time_s",
            direction="nearest",
            tolerance=0.03,  # 30ms tolerance
        )

        # ----------------------------
        # Fix missing speed if NaN
        # ----------------------------
        if "Speed" in merged.columns and merged["Speed"].isna().sum() > 0:
            dx = np.diff(merged["X"])
            dy = np.diff(merged["Y"])
            dist_xy = np.sqrt(dx**2 + dy**2)

            dt = np.diff(merged["Time_s"])
            dt = np.where(dt == 0, np.nan, dt)

            speed_calc = np.zeros(len(merged))
            speed_calc[1:] = (dist_xy / dt) * 3.6  # m/s → km/h

            speed_series = pd.Series(speed_calc, index=merged.index)
            merged["Speed"] = merged["Speed"].fillna(speed_series)

        # ----------------------------
        # Fix distance if missing
        # ----------------------------
        if "Distance" not in merged.columns or merged["Distance"].isna().sum() > 0:
            dx = np.diff(merged["X"])
            dy = np.diff(merged["Y"])
            d = np.sqrt(dx**2 + dy**2)
            merged["Distance"] = np.concatenate([[0], np.cumsum(d)])

        return merged

    except Exception as e:
        print(f"Error loading pos telemetry for {driver_code}: {e}")
        return None
