import pandas as pd
import numpy as np
from src.data.load_data import load_telemetry
from src.data.feature_engineering import build_features

# Falls preprocess_telemetry existiert, nutzen wir es.
# Falls du die Datei nicht hast, können wir es hier auch weglassen oder einen Dummy nutzen.
try:
    from src.data.preprocess import preprocess_telemetry
except ImportError:
    # Fallback, falls preprocess.py fehlt: Einfach Daten durchreichen
    def preprocess_telemetry(df):
        return df


def load_and_process_driver(session, driver_code):
    """Loads telemetry for a driver and runs full preprocessing + feature engineering."""
    tel = load_telemetry(session, driver_code)

    if tel is None or tel.empty:
        return pd.DataFrame()

    tel_clean = preprocess_telemetry(tel)
    features = build_features(tel_clean)

    if features.empty:
        return pd.DataFrame()

    features["Driver"] = driver_code
    return features


def sync_telemetry(tel1, tel2):
    """
    Synchronizes two telemetry datasets on the 'Distance' column.
    Returns a DataFrame with matched speeds and timestamps.
    """
    if tel1 is None or tel2 is None:
        return pd.DataFrame()

    merged = pd.merge_asof(
        tel1.sort_values("Distance"),
        tel2.sort_values("Distance"),
        on="Distance",
        direction="nearest",
        suffixes=("_1", "_2"),
    )
    return merged


def compare_drivers_corner_level(session, driver_a: str, driver_b: str) -> pd.DataFrame:
    """
    Corner-by-corner comparison for two drivers.

    Steps:
    1. Load telemetry for each driver
    2. Build corner-level features (ApexSpeed, EntrySpeed...)
    3. Merge on Corner ID
    4. Compute deltas
    5. Add standardized aliases (CRITICAL for downstream classification)
    """

    # 1. Load & Process
    # Wir nutzen hier direkt die Hilfsfunktion von oben, um Code zu sparen
    feat_a = load_and_process_driver(session, driver_a)
    feat_b = load_and_process_driver(session, driver_b)

    if feat_a.empty or feat_b.empty:
        return pd.DataFrame()

    # 2. Rename columns dynamically (e.g. VER_ApexSpeed)
    # Wir exkludieren 'Corner', damit wir darauf mergen können
    feat_a = feat_a.rename(
        columns={col: f"{driver_a}_{col}" for col in feat_a.columns if col != "Corner"}
    )
    feat_b = feat_b.rename(
        columns={col: f"{driver_b}_{col}" for col in feat_b.columns if col != "Corner"}
    )

    # 3. Merge on Corner
    merged = feat_a.merge(feat_b, on="Corner", how="inner")

    # 4. Compute Deltas (A - B)
    # Apex Speed
    merged["Delta_ApexSpeed"] = (
        merged[f"{driver_a}_ApexSpeed"] - merged[f"{driver_b}_ApexSpeed"]
    )
    # Entry Speed
    merged["Delta_EntrySpeed"] = (
        merged[f"{driver_a}_EntrySpeed"] - merged[f"{driver_b}_EntrySpeed"]
    )
    # Exit Speed
    merged["Delta_ExitSpeed"] = (
        merged[f"{driver_a}_ExitSpeed"] - merged[f"{driver_b}_ExitSpeed"]
    )
    # Speed Gain/Loss
    merged["Delta_SpeedLoss"] = (
        merged[f"{driver_a}_SpeedLoss"] - merged[f"{driver_b}_SpeedLoss"]
    )
    merged["Delta_SpeedGain"] = (
        merged[f"{driver_a}_SpeedGain"] - merged[f"{driver_b}_SpeedGain"]
    )

    # Inputs (falls vorhanden)
    if (
        f"{driver_a}_AvgBrake" in merged.columns
        and f"{driver_b}_AvgBrake" in merged.columns
    ):
        merged["Delta_AvgBrake"] = (
            merged[f"{driver_a}_AvgBrake"] - merged[f"{driver_b}_AvgBrake"]
        )
        merged["Delta_AvgThrottle"] = (
            merged[f"{driver_a}_AvgThrottle"] - merged[f"{driver_b}_AvgThrottle"]
        )

    # Throttle behavior
    if f"{driver_a}_ThrottleBelow30Pct" in merged.columns:
        merged["Delta_ThrottleBelow30Pct"] = (
            merged[f"{driver_a}_ThrottleBelow30Pct"]
            - merged[f"{driver_b}_ThrottleBelow30Pct"]
        )

    # ---------------------------------------------------------
    # 5. CRITICAL FIX: STANDARD ALIASES
    # ---------------------------------------------------------
    # Damit die time_loss_engine und corner_utils wissen, was "ApexSpeed" ist,
    # ohne den Fahrernamen raten zu müssen.

    # Für Classification (corner_utils):
    merged["ApexSpeed_A"] = merged[f"{driver_a}_ApexSpeed"]
    merged["ApexSpeed_B"] = merged[f"{driver_b}_ApexSpeed"]

    # Legacy Support (falls Code nach Speed_1 sucht):
    merged["Speed_1"] = merged[f"{driver_a}_ApexSpeed"]
    merged["Speed_2"] = merged[f"{driver_b}_ApexSpeed"]

    # CornerNumber explizit setzen (manche Plots suchen danach)
    merged["CornerNumber"] = merged["Corner"]

    return merged
