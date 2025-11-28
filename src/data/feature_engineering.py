import pandas as pd
import numpy as np
from scipy.signal import find_peaks


# ----------------------------------------------------------
# 1. Corner Segmentation
# ----------------------------------------------------------

def segment_corners(tel, min_separation=30):
    """
    Segment corners based on local speed minima (apex detection).
    - Uses the smoothed speed signal
    - Finds minima (turn apexes) by detecting peaks in -Speed
    - Adds a Corner column to the telemetry
    """

    tel = tel.copy()

    # Use smoothed speed if exists
    speed = tel["Speed_smooth"] if "Speed_smooth" in tel.columns else tel["Speed"]

    # Detect minima by finding peaks in -speed
    inverted = -speed
    minima, _ = find_peaks(inverted, distance=min_separation)

    # Assign corner IDs
    tel["Corner"] = 1
    corner_id = 1

    apex_indices = list(minima)

    for i in range(len(tel)):
        if i in apex_indices:
            corner_id += 1
        tel.loc[tel.index[i], "Corner"] = corner_id

    return tel



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
