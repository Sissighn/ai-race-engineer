"""
Feature Engineering for Telemetry Data.

Implements corner detection, segmentation, and extraction of
performance metrics (speeds, brake, throttle).
"""

import pandas as pd
import numpy as np
from scipy.signal import find_peaks

from src.logging import get_logger
from src.exceptions import FeatureEngineeringError
from src.config import settings

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────────────
# 1. Corner Segmentation
# ──────────────────────────────────────────────────────────────────────


def segment_corners(
    tel: pd.DataFrame,
    prominence: int = None,
    window: int = None,
) -> pd.DataFrame:
    """
    Segment corners from telemetry data.

    Uses local speed minima to detect corner apexes,
    then expands to detect entry and exit points.

    Args:
        tel: Telemetry DataFrame with Distance and Speed columns
        prominence: Apex prominence threshold (default: from config)
        window: Search window size (default: from config)

    Returns:
        DataFrame with Corner ID column assigned

    Raises:
        FeatureEngineeringError: If segmentation fails
    """
    if tel is None or tel.empty:
        raise FeatureEngineeringError("Telemetry is None or empty")

    if prominence is None:
        prominence = settings.CORNER_PROMINENCE
    if window is None:
        window = settings.CORNER_WINDOW

    log_context = {"samples": len(tel), "prominence": prominence, "window": window}

    try:
        logger.debug("Segmenting corners", **log_context)

        df = tel.copy()

        # Use smoothed speed if available, otherwise raw
        speed = df["Speed_smooth"] if "Speed_smooth" in df.columns else df["Speed"]

        # 1) Apex detection: local minima of speed
        inv_speed = -speed.values
        apex_indices, _ = find_peaks(inv_speed, prominence=prominence)

        logger.debug("Apexes detected", apex_count=len(apex_indices), **log_context)

        segments = []
        corner_id = 1

        for apex in apex_indices:
            # Apex distance
            apex_dist = df["Distance"].iloc[apex]

            # 2) Entry detection: scan backwards until speed increases
            entry = max(0, apex - window)
            while entry > 1 and speed.iloc[entry] <= speed.iloc[entry - 1]:
                entry -= 1
            entry_dist = df["Distance"].iloc[entry]

            # 3) Exit detection: scan forward until speed increases
            exit = min(len(df) - 1, apex + window)
            while exit < len(df) - 2 and speed.iloc[exit] <= speed.iloc[exit + 1]:
                exit += 1
            exit_dist = df["Distance"].iloc[exit]

            segments.append((entry_dist, apex_dist, exit_dist))
            corner_id += 1

        # Assign Corner ID to telemetry
        df["Corner"] = 0
        cid = 1

        for entry, apex, exit in segments:
            mask = (df["Distance"] >= entry) & (df["Distance"] <= exit)
            df.loc[mask, "Corner"] = cid
            cid += 1

        # Remove non-corner data
        df = df[df["Corner"] > 0].copy()

        logger.info(
            "Corners segmented",
            corners_found=len(df["Corner"].unique()),
            **log_context,
        )
        return df

    except Exception as e:
        msg = "Corner segmentation failed"
        logger.error(msg, error=str(e), **log_context, exc_info=True)
        raise FeatureEngineeringError(msg) from e


# ──────────────────────────────────────────────────────────────────────
# 2. Corner Metrics: Entry / Apex / Exit Speed
# ──────────────────────────────────────────────────────────────────────


def compute_corner_features(tel: pd.DataFrame) -> pd.DataFrame:
    """
    Extract performance metrics for each corner.

    For each detected corner:
    - Entry Speed (speed at corner entry)
    - Apex Speed (minimum speed)
    - Exit Speed (speed at corner exit)
    - Speed Loss (Entry - Apex)
    - Speed Gain (Exit - Apex)

    Args:
        tel: Segmented telemetry with Corner column

    Returns:
        DataFrame with one row per corner and metrics

    Raises:
        FeatureEngineeringError: If feature computation fails
    """
    if tel is None or tel.empty or "Corner" not in tel.columns:
        raise FeatureEngineeringError("Invalid telemetry for feature computation")

    log_context = {"input_samples": len(tel)}

    try:
        logger.debug("Computing corner features", **log_context)

        corner_ids = tel["Corner"].unique()
        features = []

        for c in corner_ids:
            seg = tel[tel["Corner"] == c]

            if len(seg) < settings.MIN_TELEMETRY_SAMPLES:
                logger.debug("Corner segment too small, skipping", corner=c)
                continue

            entry = seg["Speed"].iloc[0]
            apex = seg["Speed"].min()
            exit = seg["Speed"].iloc[-1]

            # Data validation
            if apex < 0 or apex > settings.MAX_REALISTIC_SPEED:
                logger.warning(
                    "Invalid apex speed, skipping corner",
                    corner=c,
                    apex_speed=apex,
                )
                continue

            features.append(
                {
                    "Corner": int(c),
                    "EntrySpeed": float(entry),
                    "ApexSpeed": float(apex),
                    "ExitSpeed": float(exit),
                    "SpeedLoss": float(entry - apex),
                    "SpeedGain": float(exit - apex),
                }
            )

        logger.info(
            "Corner features computed",
            features_count=len(features),
            **log_context,
        )
        return pd.DataFrame(features)

    except Exception as e:
        msg = "Failed to compute corner features"
        logger.error(msg, error=str(e), **log_context, exc_info=True)
        raise FeatureEngineeringError(msg) from e


# ──────────────────────────────────────────────────────────────────────
# 3. Throttle / Brake Behavior
# ──────────────────────────────────────────────────────────────────────


def compute_throttle_brake_metrics(tel: pd.DataFrame) -> pd.DataFrame:
    """
    Extract brake and throttle characteristics per corner.

    Metrics:
    - Average Brake pressure (0-100)
    - Average Throttle position (0-100)
    - Throttle Below 30% (indicator of hesitation/coasting)

    Args:
        tel: Segmented telemetry with Brake/Throttle columns

    Returns:
        DataFrame with one row per corner

    Raises:
        FeatureEngineeringError: If computation fails
    """
    if tel is None or tel.empty or "Corner" not in tel.columns:
        raise FeatureEngineeringError("Invalid telemetry for brake/throttle metrics")

    log_context = {"input_samples": len(tel)}

    try:
        logger.debug("Computing throttle/brake metrics", **log_context)

        corner_ids = tel["Corner"].unique()
        metrics = []

        for c in corner_ids:
            seg = tel[tel["Corner"] == c]

            if len(seg) < settings.MIN_TELEMETRY_SAMPLES:
                continue

            avg_brake = seg["Brake"].mean() if "Brake" in seg.columns else 0.0
            avg_throttle = seg["Throttle"].mean() if "Throttle" in seg.columns else 0.0

            # Throttle hesitation: percentage of time throttle < 30%
            throttle_col = seg["Throttle"] if "Throttle" in seg.columns else pd.Series()
            throttle_low = (
                len(throttle_col[throttle_col < 30]) / len(seg)
                if len(throttle_col) > 0
                else 0.0
            )

            metrics.append(
                {
                    "Corner": int(c),
                    "AvgBrake": float(avg_brake),
                    "AvgThrottle": float(avg_throttle),
                    "ThrottleBelow30Pct": float(throttle_low),
                }
            )

        logger.info(
            "Throttle/brake metrics computed",
            metrics_count=len(metrics),
            **log_context,
        )
        return pd.DataFrame(metrics)

    except Exception as e:
        msg = "Failed to compute throttle/brake metrics"
        logger.error(msg, error=str(e), **log_context, exc_info=True)
        raise FeatureEngineeringError(msg) from e


# ──────────────────────────────────────────────────────────────────────
# 4. Full Feature Pipeline
# ──────────────────────────────────────────────────────────────────────


def build_features(tel: pd.DataFrame) -> pd.DataFrame:
    """
    Complete feature engineering pipeline.

    Steps:
    1. Segment corners
    2. Extract performance features
    3. Extract brake/throttle behavior
    4. Merge into single feature table

    Args:
        tel: Raw telemetry DataFrame

    Returns:
        Aggregated corner-level features, or empty DataFrame if failed

    Raises:
        FeatureEngineeringError: If any step fails
    """
    log_context = {"input_samples": len(tel) if tel is not None else 0}

    try:
        logger.info("Starting feature engineering pipeline", **log_context)

        # 1. Segment corners
        tel_segmented = segment_corners(tel)
        if tel_segmented.empty:
            logger.warning("No corners found after segmentation", **log_context)
            return pd.DataFrame()

        # 2. Compute performance features
        perf = compute_corner_features(tel_segmented)
        if perf.empty:
            logger.warning("No features computed", **log_context)
            return pd.DataFrame()

        # 3. Compute brake/throttle behavior
        behavior = compute_throttle_brake_metrics(tel_segmented)

        # 4. Merge
        merged = perf.merge(behavior, on="Corner", how="left")

        logger.info(
            "Feature engineering complete",
            features=len(merged),
            **log_context,
        )
        return merged

    except FeatureEngineeringError:
        raise

    except Exception as e:
        msg = "Feature engineering pipeline failed"
        logger.error(msg, error=str(e), **log_context, exc_info=True)
        raise FeatureEngineeringError(msg) from e
