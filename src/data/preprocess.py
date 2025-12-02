import pandas as pd
from scipy.signal import savgol_filter


def smooth_signal(series, window=51, poly=3):
    """Apply Savitzky–Golay smoothing to a telemetry series."""
    return savgol_filter(series, window_length=window, polyorder=poly)


def preprocess_telemetry(tel):
    """
    Returns telemetry DataFrame with smoothed signals.
    """
    tel = tel.copy()
    tel["Speed_smooth"] = smooth_signal(tel["Speed"])
    tel["Throttle_smooth"] = smooth_signal(tel["Throttle"])
    tel["Brake_smooth"] = smooth_signal(tel["Brake"])
    return tel
