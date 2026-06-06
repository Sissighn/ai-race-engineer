"""
Driver DNA telemetry-derived heuristic score domain logic.

The returned 0-100 values are normalized driving-style indicators, not
objective performance ratings.
"""

from typing import Optional

import numpy as np
import pandas as pd

from src.exceptions import AnalysisError
from src.logging import get_logger
from src.models import DriverDNAMetrics

logger = get_logger(__name__)


def calculate_driver_dna(telemetry: Optional[pd.DataFrame]) -> dict[str, float]:
    """Calculate telemetry-derived heuristic driving-style scores.

    The thresholds below are hand-tuned normalization ranges for FastF1
    telemetry channels. They make different dimensions comparable on a 0-100
    scale, but they are not calibrated proof of absolute driver performance.
    """
    log_context = {"samples": len(telemetry) if telemetry is not None else 0}

    if telemetry is None or telemetry.empty:
        logger.warning("Empty telemetry for DNA analysis", **log_context)
        return {}

    try:
        logger.info("Calculating driver DNA", **log_context)

        telemetry_work = telemetry.copy()
        # 0.1s is the standard FastF1 telemetry sampling interval
        telemetry_work["acc"] = telemetry_work["Speed"].diff() / 0.1
        braking_zones = telemetry_work[telemetry_work["Brake"] > 0]

        if not braking_zones.empty:
            top_decel = braking_zones["acc"].abs().quantile(0.95)
            # Map 95th-percentile deceleration: 50 km/h/s (gentle) → 0, 200 km/h/s (hard) → 100
            aggressiveness = np.interp(top_decel, [50, 200], [0, 100])
        else:
            aggressiveness = 50
            logger.warning("No braking zones found", **log_context)

        max_speed = telemetry_work["Speed"].max()
        avg_corner_speed = telemetry_work[telemetry_work["Speed"] < max_speed * 0.85][
            "Speed"
        ].mean()
        cornering_ability = np.interp(avg_corner_speed, [80, 230], [0, 100])

        throttle_transition = telemetry_work[
            (telemetry_work["Throttle"] > 20) & (telemetry_work["Throttle"] < 95)
        ]
        if not throttle_transition.empty:
            throttle_std = throttle_transition["Throttle"].diff().abs().mean()
            smoothness = np.interp(throttle_std, [0.5, 8.0], [100, 20])
        else:
            smoothness = 80

        full_throttle_pct = (
            telemetry_work[telemetry_work["Throttle"] >= 99].shape[0]
            / len(telemetry_work)
        ) * 100
        full_throttle_score = np.interp(full_throttle_pct, [40, 85], [0, 100])

        if "nGear" in telemetry_work.columns:
            gear_changes = telemetry_work["nGear"].diff().abs().sum()
            gear_workload = np.interp(gear_changes, [30, 90], [0, 100])
        else:
            gear_workload = 50

        dna_model = DriverDNAMetrics(
            aggressiveness=float(np.clip(aggressiveness, 0, 100)),
            cornering=float(np.clip(cornering_ability, 0, 100)),
            smoothness=float(np.clip(smoothness, 0, 100)),
            full_throttle=float(np.clip(full_throttle_score, 0, 100)),
            gear_workload=float(np.clip(gear_workload, 0, 100)),
        )
        result = dna_model.to_legacy_dict()

        logger.info("Driver DNA calculated", metrics=result, **log_context)
        return result

    except Exception as e:
        msg = "Driver DNA calculation failed"
        logger.error(msg, error=str(e), **log_context, exc_info=True)
        raise AnalysisError(msg) from e


def compare_driver_dna(
    dna_a: dict[str, float],
    dna_b: dict[str, float],
    driver_a: str,
    driver_b: str,
) -> dict[str, float]:
    log_context = {
        "driver_a": driver_a,
        "driver_b": driver_b,
    }

    if not dna_a or not dna_b:
        logger.warning("Invalid DNA data for comparison", **log_context)
        return {}

    try:
        logger.info("Comparing driver DNA profiles", **log_context)

        comparison = {}
        for key in dna_a.keys():
            if key in dna_b:
                delta = dna_a[key] - dna_b[key]
                comparison[f"{key}_Delta"] = round(delta, 1)
                comparison[f"{key}_A"] = dna_a[key]
                comparison[f"{key}_B"] = dna_b[key]

        logger.info("Driver DNA comparison complete", **log_context)
        return comparison

    except Exception as e:
        msg = "Driver DNA comparison failed"
        logger.error(msg, error=str(e), **log_context, exc_info=True)
        raise AnalysisError(msg) from e


def get_driver_dna_comparison_df(
    tel_driver_1: pd.DataFrame, tel_driver_2: pd.DataFrame, name_1: str, name_2: str
) -> pd.DataFrame:
    """Build a comparison DataFrame of driver DNA metrics for two drivers.

    Args:
        tel_driver_1: Telemetry for the first driver.
        tel_driver_2: Telemetry for the second driver.
        name_1: Display name for the first driver.
        name_2: Display name for the second driver.

    Returns:
        DataFrame with columns Metric, name_1, name_2 – or empty if DNA unavailable.
    """
    dna_1 = calculate_driver_dna(tel_driver_1)
    dna_2 = calculate_driver_dna(tel_driver_2)

    if not dna_1 or not dna_2:
        return pd.DataFrame()

    categories = list(dna_1.keys())

    return pd.DataFrame(
        {
            "Metric": categories,
            name_1: [dna_1[c] for c in categories],
            name_2: [dna_2[c] for c in categories],
        }
    )
