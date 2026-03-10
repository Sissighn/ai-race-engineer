"""
Time Loss Estimation Engine.

Calculates lap time delta between drivers using weighted telemetry deltas.
Uses speed differences at Entry, Apex, and Exit to estimate time loss per corner.
"""

import pandas as pd

from src.exceptions import TimeCalculationError
from src.logging import get_logger

logger = get_logger(__name__)

TIME_WEIGHT_ENTRY = 0.015
TIME_WEIGHT_APEX = 0.030
TIME_WEIGHT_EXIT = 0.060


def estimate_time_loss_per_corner(
    df: pd.DataFrame, driver_a: str, driver_b: str
) -> pd.DataFrame:
    log_context = {
        "driver_a": driver_a,
        "driver_b": driver_b,
        "corners": len(df) if df is not None else 0,
    }

    if df is None or df.empty:
        logger.warning("No data for time loss calculation", **log_context)
        return pd.DataFrame()

    try:
        logger.debug("Calculating time loss per corner", **log_context)

        df = df.copy()

        for col in ["Delta_EntrySpeed", "Delta_ApexSpeed", "Delta_ExitSpeed"]:
            if col not in df.columns:
                logger.debug("Column missing, using zero", column=col)
                df[col] = 0.0

        df["TimeLoss"] = (
            df["Delta_EntrySpeed"] * TIME_WEIGHT_ENTRY
            + df["Delta_ApexSpeed"] * TIME_WEIGHT_APEX
            + df["Delta_ExitSpeed"] * TIME_WEIGHT_EXIT
        )

        df["TimeLossSeconds_A_loses"] = df["TimeLoss"].apply(
            lambda x: -x if x < 0 else 0
        )
        df["TimeGainSeconds_A_gains"] = df["TimeLoss"].apply(
            lambda x: x if x > 0 else 0
        )

        if "Speed_1" in df.columns:
            df["ApexSpeed_A"] = df["Speed_1"]
        elif "ApexSpeed_A" not in df.columns and f"{driver_a}_ApexSpeed" in df.columns:
            df["ApexSpeed_A"] = df[f"{driver_a}_ApexSpeed"]

        if "Speed_2" in df.columns:
            df["ApexSpeed_B"] = df["Speed_2"]
        elif "ApexSpeed_B" not in df.columns and f"{driver_b}_ApexSpeed" in df.columns:
            df["ApexSpeed_B"] = df[f"{driver_b}_ApexSpeed"]

        logger.info(
            "Time loss calculated",
            total_loss=df["TimeLoss"].sum(),
            mean_loss=df["TimeLoss"].mean(),
            **log_context,
        )
        return df

    except Exception as e:
        msg = f"Time loss calculation failed for {driver_a} vs {driver_b}"
        logger.error(msg, error=str(e), **log_context, exc_info=True)
        raise TimeCalculationError(msg) from e
