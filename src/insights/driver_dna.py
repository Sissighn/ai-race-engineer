"""
Driver DNA Analysis - Driver Characteristic Profiling.

Analyzes telemetry patterns to extract driver characteristics:
- Aggressiveness (braking intensity)
- Cornering ability (corner confidence)
- Smoothness (throttle modulation)
- Full throttle percentage
- Gear workload
"""

import numpy as np
import pandas as pd
from typing import Optional, Dict

from src.logging import get_logger
from src.exceptions import AnalysisError

logger = get_logger(__name__)


def calculate_driver_dna(telemetry: Optional[pd.DataFrame]) -> Dict[str, float]:
    """
    Extrahiert Fahrercharakteristiken aus der Telemetrie.

    Gibt ein Dictionary mit Metriken auf einer Skala von 0-100 zurück.
    """
    log_context = {"samples": len(telemetry) if telemetry is not None else 0}

    if telemetry is None or telemetry.empty:
        logger.warning("Empty telemetry for DNA analysis", **log_context)
        return {}

    try:
        logger.info("Calculating driver DNA", **log_context)

        # 1. AGGRESSIVENESS (Braking deceleration)
        telemetry_work = telemetry.copy()
        telemetry_work["acc"] = telemetry_work["Speed"].diff() / 0.1
        braking_zones = telemetry_work[telemetry_work["Brake"] > 0]

        if not braking_zones.empty:
            top_decel = braking_zones["acc"].abs().quantile(0.95)
            aggressiveness = np.interp(top_decel, [20, 65], [0, 100])
        else:
            aggressiveness = 50
            logger.warning("No braking zones found", **log_context)

        # 2. CORNERING (Mid-corner confidence)
        max_speed = telemetry_work["Speed"].max()
        avg_corner_speed = telemetry_work[telemetry_work["Speed"] < max_speed * 0.85][
            "Speed"
        ].mean()

        cornering_ability = np.interp(avg_corner_speed, [80, 230], [0, 100])

        # 3. SMOOTHNESS (Throttle modulation)
        throttle_transition = telemetry_work[
            (telemetry_work["Throttle"] > 20) & (telemetry_work["Throttle"] < 95)
        ]
        if not throttle_transition.empty:
            throttle_std = throttle_transition["Throttle"].diff().abs().mean()
            smoothness = np.interp(throttle_std, [0.5, 8.0], [100, 20])
        else:
            smoothness = 80

        # 4. FULL THROTTLE %
        full_throttle_pct = (
            telemetry_work[telemetry_work["Throttle"] >= 99].shape[0]
            / len(telemetry_work)
        ) * 100
        full_throttle_score = np.interp(full_throttle_pct, [40, 85], [0, 100])

        # 5. GEAR USAGE (Downshift workload)
        if "nGear" in telemetry_work.columns:
            gear_changes = telemetry_work["nGear"].diff().abs().sum()
            gear_workload = np.interp(gear_changes, [30, 90], [0, 100])
        else:
            gear_workload = 50

        result = {
            "Aggressiveness": round(aggressiveness, 1),
            "Cornering": round(cornering_ability, 1),
            "Smoothness": round(smoothness, 1),
            "FullThrottle": round(full_throttle_score, 1),
            "GearWorkload": round(gear_workload, 1),
        }

        logger.info("Driver DNA calculated", metrics=result, **log_context)
        return result

    except Exception as e:
        msg = "Driver DNA calculation failed"
        logger.error(msg, error=str(e), **log_context, exc_info=True)
        raise AnalysisError(msg) from e


def compare_driver_dna(dna_a: Dict, dna_b: Dict, driver_a: str, driver_b: str) -> Dict:
    """
    Vergleicht zwei DNA-Profile und berechnet die Differenzen (Deltas).
    """
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
    """
    Berechnet die DNA für zwei Datensätze und gibt das Ergebnis als Pandas DataFrame zurück.
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
