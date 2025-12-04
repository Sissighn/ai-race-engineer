import os
import shutil
import fastf1
import pandas as pd
import numpy as np
import streamlit as st

# ---------------------------------------------------------
# CONFIG & CACHE SETUP
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
# HELPER: CUSTOM HASH FUNCTION
# -------------------------------------------------------
def hash_session_id(session):
    if not session:
        return "no_session"
    try:
        event = (
            session.event["EventName"] if "EventName" in session.event else "Unknown"
        )
        name = session.name
        return f"{session.event.Year}_{event}_{name}"
    except Exception:
        return str(session)


# -------------------------------------------------------
# HELPER: CACHE CLEARING (SELF-HEALING)
# -------------------------------------------------------
def clear_specific_session_cache(year, grand_prix, session_type):
    """
    Versucht, den Cache für ein spezifisches Event zu löschen,
    falls die Daten korrupt sind.
    """
    try:
        # FastF1 speichert Cache oft unter: cache_dir / year / event_name / session_type
        # Da wir den genauen Ordnernamen schwer raten können (wegen Fuzzy Matching),
        # löschen wir im Zweifel den Cache für das ganze Jahr oder warnen den User.

        # Sicherer Ansatz: Wir nutzen FastF1's interne Struktur nicht direkt,
        # sondern probieren, ob wir den Ordner finden.
        year_path = os.path.join(cache_path, str(year))
        if os.path.exists(year_path):
            # Wir löschen einfach nichts automatisch, um keine User-Daten zu verlieren,
            # aber wir geben das Signal zurück, dass neu geladen werden soll.
            pass

        # Alternative: FastF1 Cache deaktivieren für den Retry
        return True
    except Exception as e:
        print(f"Error clearing cache: {e}")
        return False


# ---------------------------------------------------------
# 1. LOAD SESSION (Robuster mit Retry)
# ---------------------------------------------------------
@st.cache_resource(show_spinner="Loading session data...")
def load_session(year: int, grand_prix: str, session_type: str):
    """
    Load a FastF1 session with corruption handling.
    """
    session = None
    try:
        # 1. Session Objekt holen
        session = fastf1.get_session(year, grand_prix, session_type)

        # 2. Zukunfts-Check
        now = (
            pd.Timestamp.now(tz=session.date.tzinfo)
            if session.date.tzinfo
            else pd.Timestamp.now()
        )
        # session.date kann tz-aware sein, now muss matchen
        if session.date.tzinfo is None:
            now = pd.Timestamp.now()

        if session.date > now:
            st.warning(
                f"⚠️ Session '{grand_prix}' hasn't happened yet ({session.date.date()})."
            )
            return None

        # 3. Daten laden (Normaler Versuch)
        session.load()
        return session

    except Exception as e:
        error_msg = str(e)

        # PRÜFUNG AUF KAPUTTEN CACHE
        if "not been loaded yet" in error_msg or "dictionary changed size" in error_msg:
            print(
                f"⚠️ Cache corruption detected for {grand_prix}. Retrying without cache..."
            )

            try:
                # RETRY: Wir deaktivieren den Cache temporär für diesen Aufruf
                fastf1.Cache.disable_cache()

                # Objekt neu erstellen, um sauberen State zu haben
                session = fastf1.get_session(year, grand_prix, session_type)
                session.load()

                # Cache danach wieder aktivieren für andere Sessions
                fastf1.Cache.enable_cache(cache_path)

                return session

            except Exception as retry_err:
                fastf1.Cache.enable_cache(
                    cache_path
                )  # Sicherstellen, dass Cache wieder an ist
                st.error(
                    f"❌ Failed to load session even after cache bypass: {retry_err}"
                )
                return None
        else:
            # Anderer Fehler (z.B. API down)
            st.error(f"Error loading session: {e}")
            return None


# ---------------------------------------------------------
# 2. LOAD TELEMETRY
# ---------------------------------------------------------
@st.cache_data(
    show_spinner="Processing telemetry...",
    hash_funcs={fastf1.core.Session: hash_session_id},
)
def load_telemetry(session, driver_code: str):
    if session is None:
        return None
    try:
        # Prüfen ob Daten wirklich da sind
        if not hasattr(session, "laps"):
            return None

        laps = session.laps.pick_driver(driver_code)
        if laps.empty:
            return None

        fastest = laps.pick_fastest()
        if fastest is None:
            return None

        tel = fastest.get_car_data().add_distance()
        if "nGear" not in tel.columns:
            tel["nGear"] = 0
        return tel
    except Exception as e:
        print(f"Telemetry Error ({driver_code}): {e}")
        return None


# ---------------------------------------------------------
# 3. LOAD TELEMETRY WITH POSITION
# ---------------------------------------------------------
@st.cache_data(
    show_spinner="Loading position data...",
    hash_funcs={fastf1.core.Session: hash_session_id},
)
def load_telemetry_with_position(session, driver_code: str):
    if session is None:
        return None
    try:
        if not hasattr(session, "laps"):
            return None

        laps = session.laps.pick_driver(driver_code)
        if laps.empty:
            return None

        fastest = laps.pick_fastest()
        if fastest is None:
            return None

        # Positionsdaten können fehlen (z.B. 2017 und früher oft lückenhaft)
        try:
            pos = fastest.get_telemetry()[["Time", "X", "Y"]].copy()
        except:
            # Fallback für alte Jahre ohne GPS-Daten
            return None

        pos["Time_s"] = pos["Time"].dt.total_seconds()
        car = fastest.get_car_data().copy()
        car["Time_s"] = car["Time"].dt.total_seconds()

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

        return merged
    except Exception as e:
        print(f"Pos Telemetry Error ({driver_code}): {e}")
        return None


# ---------------------------------------------------------
# 4. GET TRACK LIST (DYNAMIC)
# ---------------------------------------------------------
@st.cache_data(show_spinner=False)
def get_tracks_for_year(year: int):
    try:
        schedule = fastf1.get_event_schedule(year, include_testing=False)
        if schedule.empty:
            return []

        if "Location" in schedule.columns:
            tracks = schedule["Location"].dropna().astype(str).tolist()
        elif "EventName" in schedule.columns:
            tracks = schedule["EventName"].dropna().astype(str).tolist()
        else:
            return []

        # Deduplicate
        seen = set()
        return [
            x.strip()
            for x in tracks
            if x.strip() and not (x.strip() in seen or seen.add(x.strip()))
        ]
    except Exception as e:
        print(f"Schedule Error {year}: {e}")
        return []
