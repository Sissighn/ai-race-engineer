"""
Time Loss Estimation Engine.

Calculates lap time delta between drivers using weighted telemetry deltas.
Uses Speed differences at Entry, Apex, and Exit to estimate time loss per corner.
"""

import pandas as pd
from typing import Optional

from src.logging import get_logger
from src.exceptions import TimeCalculationError

logger = get_logger(__name__)

# Weighting factors (seconds per km/h delta)
# These represent how much time is lost per km/h difference at each phase
TIME_WEIGHT_ENTRY = 0.015  # Entry speed is relatively important
TIME_WEIGHT_APEX = 0.030  # Apex speed is more critical
TIME_WEIGHT_EXIT = 0.060  # Exit speed is most critical (affects next sector)


def estimate_time_loss_per_corner(
    df: pd.DataFrame, driver_a: str, driver_b: str
) -> pd.DataFrame:
    """
    Estimate lap time loss per corner using weighted speed deltas.

    Formula: TimeLoss = (Entry_delta * 0.015) + (Apex_delta * 0.030) + (Exit_delta * 0.060)

    Convention:
    - Positive TimeLoss: driver_a is faster (gains time)
    - Negative TimeLoss: driver_a is slower (loses time)

    Args:
        df: Comparison DataFrame with Delta_*Speed columns
        driver_a: First driver code
        driver_b: Second driver code

    Returns:
        DataFrame with TimeLoss column added

    Raises:
        TimeCalculationError: If calculation fails
    """
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

        # Ensure required columns exist
        required_cols = [
            "Delta_EntrySpeed",
            "Delta_ApexSpeed",
            "Delta_ExitSpeed",
        ]
        for col in required_cols:
            if col not in df.columns:
                logger.debug(f"Column {col} missing, using 0")
                df[col] = 0.0

        # Calculate time loss using weighted deltas
        df["TimeLoss"] = (
            df["Delta_EntrySpeed"] * TIME_WEIGHT_ENTRY
            + df["Delta_ApexSpeed"] * TIME_WEIGHT_APEX
            + df["Delta_ExitSpeed"] * TIME_WEIGHT_EXIT
        )

        # Direction logic:
        # Negative TimeLoss = driver_a loses time
        # Positive TimeLoss = driver_a gains time
        df["TimeLossSeconds_A_loses"] = df["TimeLoss"].apply(
            lambda x: -x if x < 0 else 0
        )
        df["TimeGainSeconds_A_gains"] = df["TimeLoss"].apply(
            lambda x: x if x > 0 else 0
        )

        # Standard aliases for downstream compatibility
        if "Speed_1" in df.columns:
            df["ApexSpeed_A"] = df["Speed_1"]
        elif "ApexSpeed_A" not in df.columns and "Delta_ApexSpeed" in df.columns:
            # Try to reconstruct from deltas
            if f"{driver_a}_ApexSpeed" in df.columns:
                df["ApexSpeed_A"] = df[f"{driver_a}_ApexSpeed"]

        if "Speed_2" in df.columns:
            df["ApexSpeed_B"] = df["Speed_2"]
        elif "ApexSpeed_B" not in df.columns:
            if f"{driver_b}_ApexSpeed" in df.columns:
                df["ApexSpeed_B"] = df[f"{driver_b}_ApexSpeed"]

        # Statistics
        total_loss = df["TimeLoss"].sum()
        mean_loss = df["TimeLoss"].mean()

        logger.info(
            "Time loss calculated",
            total_loss=total_loss,
            mean_loss=mean_loss,
            **log_context,
        )
        return df

    except Exception as e:
        msg = f"Time loss calculation failed for {driver_a} vs {driver_b}"
        logger.error(msg, error=str(e), **log_context, exc_info=True)
        raise TimeCalculationError(msg) from e
