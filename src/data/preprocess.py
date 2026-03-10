"""
Telemetry Data Preprocessing.

Applies signal smoothing and data cleaning to raw telemetry.
"""

import pandas as pd
import numpy as np
from scipy.signal import savgol_filter

from src.logging import get_logger
from src.exceptions import PreprocessingError

logger = get_logger(__name__)


def smooth_signal(series: pd.Series, window: int = 51, poly: int = 3) -> np.ndarray:
    """
    Apply Savitzky–Golay smoothing to a telemetry signal.

    Args:
        series: Input signal (e.g., Speed, Throttle)
        window: Filter window length (must be odd)
        poly: Polynomial order

    Returns:
        Smoothed signal as numpy array
    """
    try:
        if len(series) < window:
            logger.warning(
                "Series too short for smoothing",
                series_len=len(series),
                window=window,
            )
            return series.values

        result = savgol_filter(series, window_length=window, polyorder=poly)
        return result
    except Exception as e:
        logger.error(
            "Smoothing failed",
            error=str(e),
            series_len=len(series),
            exc_info=True,
        )
        raise PreprocessingError(f"Signal smoothing failed: {e}") from e


def preprocess_telemetry(tel: pd.DataFrame) -> pd.DataFrame:
    """
    Preprocess telemetry data with signal smoothing.

    Adds smoothed versions of key signals:
    - Speed_smooth
    - Throttle_smooth
    - Brake_smooth

    Args:
        tel: Raw telemetry DataFrame

    Returns:
        DataFrame with smoothed signals

    Raises:
        PreprocessingError: If preprocessing fails
    """
    if tel is None or tel.empty:
        raise PreprocessingError("Telemetry is None or empty")

    log_context = {"samples": len(tel)}

    try:
        logger.debug("Preprocessing telemetry", **log_context)

        tel = tel.copy()

        # Apply smoothing to key signals
        if "Speed" in tel.columns:
            tel["Speed_smooth"] = smooth_signal(tel["Speed"])

        if "Throttle" in tel.columns:
            tel["Throttle_smooth"] = smooth_signal(tel["Throttle"])

        if "Brake" in tel.columns:
            tel["Brake_smooth"] = smooth_signal(tel["Brake"])

        logger.info("Telemetry preprocessed successfully", **log_context)
        return tel

    except PreprocessingError:
        raise

    except Exception as e:
        msg = "Telemetry preprocessing failed"
        logger.error(msg, error=str(e), **log_context, exc_info=True)
        raise PreprocessingError(msg) from e
