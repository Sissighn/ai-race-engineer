import os
import fastf1
import pandas as pd

# ---- FIND PROJECT ROOT CORRECTLY ----
# File is located at: project/src/data/load_data.py
# We want to go UP 2 LEVELS: load_data.py -> data -> src -> project root
data_folder = os.path.dirname(os.path.abspath(__file__))
src_folder = os.path.dirname(data_folder)
project_root = os.path.dirname(src_folder)
cache_path = os.path.join(project_root, "cache")

# Create cache folder if missing
os.makedirs(cache_path, exist_ok=True)

# Enable FastF1 cache
fastf1.Cache.enable_cache(cache_path)


def load_session(year: int, grand_prix: str, session_type: str):
    session = fastf1.get_session(year, grand_prix, session_type)
    session.load()
    return session


def load_telemetry(session, driver_code: str):
    laps = session.laps.pick_driver(driver_code)
    fastest = laps.pick_fastest()
    tel = fastest.get_car_data().add_distance()
    return tel
