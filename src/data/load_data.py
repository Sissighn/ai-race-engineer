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

fastf1.Cache.enable_cache(cache_path)


# ---------------------------------------------------------
# LOAD SESSION
# ---------------------------------------------------------
@st.cache_data(show_spinner="Loading session data...")
def load_session(year: int, grand_prix: str, session_type: str):
    """
    Load a FastF1 session (modern API).
    """
    session = fastf1.get_session(year, grand_prix, session_type)
    session.load()  # <- FastF1 lädt automatisch Telemetry, Positions, Weather
    return session


# ---------------------------------------------------------
# LOAD BASIC TELEMETRY (DISTANCE, SPEED, THROTTLE, BRAKE)
# ---------------------------------------------------------
@st.cache_data(show_spinner="Loading telemetry for driver...")
def load_telemetry(session, driver_code: str):
    """
    Load the fastest lap for the given driver with distance added.
    Returns:
        DataFrame with Distance, Speed, Throttle, Brake, RPM, Gear, etc.
    """
    laps = session.laps.pick_driver(driver_code)

    if laps.empty:
        raise ValueError(f"No laps found for driver {driver_code}")

    fastest = laps.pick_fastest()

    if fastest is None:
        raise ValueError(f"No fastest lap found for driver {driver_code}")

    tel = fastest.get_car_data().add_distance()

    return tel


# ---------------------------------------------------------
# LOAD TELEMETRY WITH X/Y POSITION FOR TRACK MAP
# ---------------------------------------------------------
@st.cache_data(show_spinner="Loading telemetry with position data...")
def load_telemetry_with_position(session, driver_code: str):
    """
    Loads full telemetry including X/Y GPS and real Speed.
    Handles missing Distance/Speed by recalculating from X/Y.
    """

    laps = session.laps.pick_driver(driver_code)
    if laps.empty:
        raise ValueError(f"No laps found for driver {driver_code}")

    fastest = laps.pick_fastest()
    if fastest is None:
        raise ValueError(f"No fastest lap found for driver {driver_code}")

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
    if merged["Speed"].isna().sum() > 0:
        # Recalculate speed from X/Y movement
        dx = np.diff(merged["X"])
        dy = np.diff(merged["Y"])
        dist_xy = np.sqrt(dx**2 + dy**2)

        dt = np.diff(merged["Time_s"])

        dt = np.where(dt == 0, np.nan, dt)

        speed_calc = np.zeros(len(merged))
        speed_calc[1:] = (dist_xy / dt) * 3.6  # m/s → km/h

        speed_calc_series = pd.Series(speed_calc, index=merged.index[: len(speed_calc)])
        merged.loc[merged["Speed"].isna(), "Speed"] = speed_calc_series.loc[
            merged["Speed"].isna()
        ]

    # ----------------------------
    # Fix distance if missing
    # ----------------------------
    if "Distance" not in merged.columns or merged["Distance"].isna().sum() > 0:
        dx = np.diff(merged["X"])
        dy = np.diff(merged["Y"])
        d = np.sqrt(dx**2 + dy**2)
        merged["Distance"] = np.concatenate([[0], np.cumsum(d)])

    return merged
