import pandas as pd
import numpy as np
from scipy.signal import find_peaks

# ----------------------------------------------------------
# 1. Corner Segmentation
# ----------------------------------------------------------

def segment_corners(tel, prominence=5, window=40):
    """
    Corner segmentation:
    - Finds apexes via local speed minima
    - Detects entry: where speed begins to fall
    - Detects exit: where speed recovers after apex
    - Assigns a corner ID only for valid corner segments
    """

    df = tel.copy()

    # Speed signal (smoothed if available)
    speed = df["Speed_smooth"] if "Speed_smooth" in df.columns else df["Speed"]

    # 1) Apex detection: local minima of speed
    inv_speed = -speed
    apex_indices, _ = find_peaks(inv_speed, prominence=prominence)

    segments = []
    corner_id = 1

    for apex in apex_indices:
        # Apex distance
        apex_dist = df["Distance"].iloc[apex]

        # 2) ENTRY detection: scan backwards until speed increases
        entry = max(0, apex - window)
        while entry > 1 and speed.iloc[entry] <= speed.iloc[entry - 1]:
            entry -= 1
        entry_dist = df["Distance"].iloc[entry]

        # 3) EXIT detection: scan forward until speed increases consistently
        exit = min(len(df) - 1, apex + window)
        while exit < len(df) - 2 and speed.iloc[exit] <= speed.iloc[exit + 1]:
            exit += 1
        exit_dist = df["Distance"].iloc[exit]

        # Save segment
        segments.append((entry_dist, apex_dist, exit_dist))

        corner_id += 1

    # Assign Corner ID to telemetry
    df["Corner"] = 0
    cid = 1

    for entry, apex, exit in segments:
        mask = (df["Distance"] >= entry) & (df["Distance"] <= exit)
        df.loc[mask, "Corner"] = cid
        cid += 1

    # Remove non-corner (=0)
    df = df[df["Corner"] > 0].copy()

    return df



# ----------------------------------------------------------
# 2. Corner Metrics: Entry / Apex / Exit Speed
# ----------------------------------------------------------

def compute_corner_features(tel):
    """
    Computes basic performance metrics for each corner:
    - Entry Speed
    - Apex Speed (min speed)
    - Exit Speed
    - Speed Loss (Entry → Apex)
    - Speed Gain (Apex → Exit)
    """
    corner_ids = tel["Corner"].unique()
    features = []

    for c in corner_ids:
        seg = tel[tel["Corner"] == c]

        if len(seg) < 5:
            continue

        entry = seg["Speed"].iloc[0]
        apex  = seg["Speed"].min()
        exit  = seg["Speed"].iloc[-1]

        features.append({
            "Corner": int(c),
            "EntrySpeed": float(entry),
            "ApexSpeed": float(apex),
            "ExitSpeed": float(exit),
            "SpeedLoss": float(entry - apex),
            "SpeedGain": float(exit - apex)
        })

    return pd.DataFrame(features)


# ----------------------------------------------------------
# 3. Throttle / Brake Behavior
# ----------------------------------------------------------

def compute_throttle_brake_metrics(tel):
    """
    Computes corner-level throttle/brake characteristics:
    - Average Brake
    - Average Throttle
    - Percent of time throttle < 30% (coasting/hesitation indicator)
    """
    corner_ids = tel["Corner"].unique()
    metrics = []

    for c in corner_ids:
        seg = tel[tel["Corner"] == c]

        avg_brake = seg["Brake"].mean()
        avg_throttle = seg["Throttle"].mean()
        throttle_low = len(seg[seg["Throttle"] < 30]) / len(seg)

        metrics.append({
            "Corner": int(c),
            "AvgBrake": float(avg_brake),
            "AvgThrottle": float(avg_throttle),
            "ThrottleBelow30Pct": float(throttle_low)
        })

    return pd.DataFrame(metrics)


# ----------------------------------------------------------
# 4. Full Feature Pipeline
# ----------------------------------------------------------

def build_features(tel):
    """
    Complete feature engineering pipeline.
    Returns:
    - normal telemetry with 'Corner' labels
    - aggregated corner metrics (performance + behavior)
    """

    tel = segment_corners(tel)
    perf = compute_corner_features(tel)
    behavior = compute_throttle_brake_metrics(tel)

    merged = perf.merge(behavior, on="Corner", how="left")
    return merged
