import pandas as pd
from src.data.load_data import load_telemetry
from src.data.preprocess import preprocess_telemetry
from src.data.feature_engineering import build_features


def load_and_process_driver(session, driver_code):
    """Loads telemetry for a driver and runs full preprocessing + feature engineering."""
    tel = load_telemetry(session, driver_code)
    tel_clean = preprocess_telemetry(tel)
    features = build_features(tel_clean)
    features["Driver"] = driver_code
    return features


def compare_drivers(session, driver_a, driver_b):
    """
    Compares two drivers on corner-level metrics.
    Returns a merged dataframe:
    - Entry/Apex/Exit Speed
    - SpeedLoss/SpeedGain
    - Brake/Throttle behavior
    - Delta between drivers
    """

    fa = load_and_process_driver(session, driver_a)
    fb = load_and_process_driver(session, driver_b)

    merged = fa.merge(fb, on="Corner", suffixes=(f"_{driver_a}", f"_{driver_b}"))

    # Create deltas between Driver A (target) and B
    merged["Delta_ApexSpeed"] = merged[f"ApexSpeed_{driver_a}"] - merged[f"ApexSpeed_{driver_b}"]
    merged["Delta_ExitSpeed"] = merged[f"ExitSpeed_{driver_a}"] - merged[f"ExitSpeed_{driver_b}"]
    merged["Delta_ThrottleBelow30"] = merged[f"ThrottleBelow30Pct_{driver_a}"] - merged[f"ThrottleBelow30Pct_{driver_b}"]

    return merged


import pandas as pd

def sync_telemetry(tel1, tel2):
    """
    Synchronizes two telemetry datasets on the 'Distance' column.
    Returns a DataFrame with matched speeds and timestamps.
    """
    merged = pd.merge_asof(
        tel1.sort_values("Distance"),
        tel2.sort_values("Distance"),
        on="Distance",
        direction="nearest",
        suffixes=("_1", "_2")
    )
    return merged

def compare_drivers_corner_level(session, driver_a: str, driver_b: str) -> pd.DataFrame:
    """
    Corner-by-corner comparison for two drivers.
    Steps:
    - load telemetry for each driver
    - preprocess
    - build corner-level features
    - merge on Corner ID
    - compute deltas between driver_a and driver_b
    """

    # Telemetry + Preprocessing
    tel_a = preprocess_telemetry(load_telemetry(session, driver_a))
    tel_b = preprocess_telemetry(load_telemetry(session, driver_b))

    # Corner-level features
    feat_a = build_features(tel_a)
    feat_b = build_features(tel_b)

    # Prefix columns with driver code, Corner bleibt als Merge-Key
    feat_a = feat_a.rename(columns={
        col: f"{driver_a}_{col}" for col in feat_a.columns if col != "Corner"
    })
    feat_b = feat_b.rename(columns={
        col: f"{driver_b}_{col}" for col in feat_b.columns if col != "Corner"
    })

    # Merge on Corner
    merged = feat_a.merge(feat_b, on="Corner", how="inner")

    # Delta-Metriken (A - B)
    merged["Delta_ApexSpeed"]   = merged[f"{driver_a}_ApexSpeed"]   - merged[f"{driver_b}_ApexSpeed"]
    merged["Delta_EntrySpeed"]  = merged[f"{driver_a}_EntrySpeed"]  - merged[f"{driver_b}_EntrySpeed"]
    merged["Delta_ExitSpeed"]   = merged[f"{driver_a}_ExitSpeed"]   - merged[f"{driver_b}_ExitSpeed"]
    merged["Delta_SpeedLoss"]   = merged[f"{driver_a}_SpeedLoss"]   - merged[f"{driver_b}_SpeedLoss"]
    merged["Delta_SpeedGain"]   = merged[f"{driver_a}_SpeedGain"]   - merged[f"{driver_b}_SpeedGain"]
    merged["Delta_AvgBrake"]    = merged[f"{driver_a}_AvgBrake"]    - merged[f"{driver_b}_AvgBrake"]
    merged["Delta_AvgThrottle"] = merged[f"{driver_a}_AvgThrottle"] - merged[f"{driver_b}_AvgThrottle"]
    merged["Delta_ThrottleBelow30Pct"] = (
        merged[f"{driver_a}_ThrottleBelow30Pct"] - merged[f"{driver_b}_ThrottleBelow30Pct"]
    )

    return merged

