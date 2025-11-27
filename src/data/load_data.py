import fastf1
import pandas as pd

def load_session(year: int, grand_prix: str, session_type: str):
    """
    Loads a FastF1 session and returns the session object.
    session_type: 'Q' for Qualifying, 'R' for Race, 'FP1', 'FP2', etc.
    """
    fastf1.Cache.enable_cache("./cache")
    
    session = fastf1.get_session(year, grand_prix, session_type)
    session.load()
    return session


def load_telemetry(session, driver_code: str):
    """
    Returns a telemetry DataFrame for the selected driver.
    """
    laps = session.laps.pick_driver(driver_code)
    fastest_lap = laps.pick_fastest()
    tel = fastest_lap.get_car_data().add_distance()
    return tel
