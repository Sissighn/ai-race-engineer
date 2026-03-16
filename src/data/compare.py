"""
Driver Comparison & Data Synchronization.

Loads telemetry for multiple drivers, synchronizes data,
and computes corner-level comparisons.
"""

import pandas as pd
import numpy as np

from src.data.load_data import load_telemetry
from src.data.feature_engineering import build_features
from src.data.preprocess import preprocess_telemetry
from src.logging import get_logger
from src.exceptions import ComparisonError, TelemetryError

logger = get_logger(__name__)


def load_and_process_driver(session, driver_code: str) -> pd.DataFrame:
    """
    Load and process telemetry for a driver in full pipeline.

    Steps:
    1. Load telemetry
    2. Preprocess (smoothing)
    3. Build features (corners, apex speeds, etc.)

    Args:
        session: FastF1 Session object
        driver_code: 3-letter driver code

    Returns:
        DataFrame with features, or empty DataFrame if failed

    Raises:
        TelemetryError: If any step fails
    """
    log_context = {"driver": driver_code}

    try:
        logger.debug("Loading and processing driver", **log_context)

        tel = load_telemetry(session, driver_code)
        if tel is None or tel.empty:
            logger.warning("No telemetry for driver", **log_context)
            return pd.DataFrame()

        tel_clean = preprocess_telemetry(tel)
        features = build_features(tel_clean)

        if features.empty:
            logger.warning("No features generated", **log_context)
            return pd.DataFrame()

        features["Driver"] = driver_code

        logger.info(
            "Driver processed successfully",
            **log_context,
            corners=len(features),
        )
        return features

    except TelemetryError:
        raise

    except Exception as e:
        msg = f"Failed to process driver {driver_code}"
        logger.error(msg, error=str(e), **log_context, exc_info=True)
        raise TelemetryError(msg) from e


def sync_telemetry(tel1: pd.DataFrame, tel2: pd.DataFrame) -> pd.DataFrame:
    """
    Synchronize two telemetry datasets on the Distance column.

    Performs an asof merge to match speeds at same track distances.

    Args:
        tel1: First driver's telemetry
        tel2: Second driver's telemetry

    Returns:
        Merged DataFrame with suffixes _1, _2

    Raises:
        ComparisonError: If synchronization fails
    """
    if tel1 is None or tel1.empty or tel2 is None or tel2.empty:
        logger.warning("One or both telemetry datasets are empty")
        return pd.DataFrame()

    try:
        logger.debug("Synchronizing telemetry datasets")

        merged = pd.merge_asof(
            tel1.sort_values("Distance"),
            tel2.sort_values("Distance"),
            on="Distance",
            direction="nearest",
            suffixes=("_1", "_2"),
        )

        logger.info("Telemetry synchronized", merged_samples=len(merged))
        return merged

    except Exception as e:
        msg = "Telemetry synchronization failed"
        logger.error(msg, error=str(e), exc_info=True)
        raise ComparisonError(msg) from e


def compare_drivers_corner_level(session, driver_a: str, driver_b: str) -> pd.DataFrame:
    """
    Perform corner-by-corner comparison for two drivers.

    Steps:
    1. Load telemetry for each driver
    2. Build corner-level features
    3. Merge on Corner ID
    4. Compute performance deltas
    5. Add standardized column aliases

    Args:
        session: FastF1 Session object
        driver_a: First driver code
        driver_b: Second driver code

    Returns:
        Comparison DataFrame with deltas

    Raises:
        ComparisonError: If comparison fails
    """
    log_context = {"driver_a": driver_a, "driver_b": driver_b}

    try:
        logger.info("Starting driver comparison", **log_context)

        # 1. Load & Process
        feat_a = load_and_process_driver(session, driver_a)
        feat_b = load_and_process_driver(session, driver_b)

        if feat_a.empty or feat_b.empty:
            msg = f"Could not load features for {driver_a} vs {driver_b}"
            logger.error(msg, **log_context)
            raise ComparisonError(msg)

        # 2. Rename columns dynamically (e.g. VER_ApexSpeed)
        feat_a = feat_a.rename(
            columns={
                col: f"{driver_a}_{col}" for col in feat_a.columns if col != "Corner"
            }
        )
        feat_b = feat_b.rename(
            columns={
                col: f"{driver_b}_{col}" for col in feat_b.columns if col != "Corner"
            }
        )

        # 3. Merge on Corner
        merged = feat_a.merge(feat_b, on="Corner", how="inner")

        if merged.empty:
            msg = f"No common corners for {driver_a} vs {driver_b}"
            logger.warning(msg, **log_context)
            return pd.DataFrame()

        # 4. Compute signed deltas (A - B)
        # Positive delta -> driver_a is faster / carries more speed
        # Negative delta -> driver_b is faster / carries more speed
        merged["Delta_ApexSpeed"] = (
            merged[f"{driver_a}_ApexSpeed"] - merged[f"{driver_b}_ApexSpeed"]
        )
        merged["Delta_EntrySpeed"] = (
            merged[f"{driver_a}_EntrySpeed"] - merged[f"{driver_b}_EntrySpeed"]
        )
        merged["Delta_ExitSpeed"] = (
            merged[f"{driver_a}_ExitSpeed"] - merged[f"{driver_b}_ExitSpeed"]
        )
        merged["Delta_SpeedLoss"] = (
            merged[f"{driver_a}_SpeedLoss"] - merged[f"{driver_b}_SpeedLoss"]
        )
        merged["Delta_SpeedGain"] = (
            merged[f"{driver_a}_SpeedGain"] - merged[f"{driver_b}_SpeedGain"]
        )

        # Brake and Throttle inputs (if available)
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

        # 5. Standard Column Aliases (for downstream compatibility)
        merged["ApexSpeed_A"] = merged[f"{driver_a}_ApexSpeed"]
        merged["ApexSpeed_B"] = merged[f"{driver_b}_ApexSpeed"]
        merged["Speed_1"] = merged[f"{driver_a}_ApexSpeed"]
        merged["Speed_2"] = merged[f"{driver_b}_ApexSpeed"]
        merged["CornerNumber"] = merged["Corner"]

        logger.info(
            "Comparison complete",
            **log_context,
            corners=len(merged),
        )
        return merged

    except ComparisonError:
        raise

    except Exception as e:
        msg = f"Driver comparison failed"
        logger.error(msg, error=str(e), **log_context, exc_info=True)
        raise ComparisonError(msg) from e
