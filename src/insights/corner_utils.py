"""
Corner Classification & Aggregation Utilities.

Classifies corners by speed type (Low, Medium, High)
and aggregates time loss by corner type.
"""

import pandas as pd
from typing import Optional

from src.logging import get_logger
from src.exceptions import ValidationError

logger = get_logger(__name__)

# Corner type speed thresholds (km/h)
CORNER_SPEED_LOW = 110  # Low speed: < 110 km/h
CORNER_SPEED_MEDIUM = 180  # Medium speed: 110-180 km/h
# High speed: > 180 km/h


def classify_corner_type(speed: float) -> str:
    """
    Classify a corner by apex speed.

    Thresholds:
    - Low Speed: < 110 km/h (dominated by mechanical grip)
    - Medium Speed: 110-180 km/h (balanced grip sources)
    - High Speed: > 180 km/h (dominated by aerodynamics)

    Args:
        speed: Apex speed in km/h

    Returns:
        Corner type classification string
    """
    if pd.isna(speed):
        return "Unknown"

    if speed < CORNER_SPEED_LOW:
        return "Low Speed"
    elif speed < CORNER_SPEED_MEDIUM:
        return "Medium Speed"
    else:
        return "High Speed"


def add_corner_classification(
    time_loss_df: Optional[pd.DataFrame],
) -> Optional[pd.DataFrame]:
    """
    Add corner type classification to time loss DataFrame.

    Searches for apex speed column and classifies each corner.
    Looks for common column names (ApexSpeed_A, Speed_1, Speed, etc.).

    Args:
        time_loss_df: Time loss comparison DataFrame

    Returns:
        DataFrame with CornerType column added, or None if failed

    Raises:
        ValidationError: If no apex speed column found
    """
    log_context = {"rows": len(time_loss_df) if time_loss_df is not None else 0}

    try:
        if time_loss_df is None or time_loss_df.empty:
            logger.warning("No data for corner classification", **log_context)
            return time_loss_df

        logger.debug("Classifying corners", **log_context)

        df = time_loss_df.copy()

        # Search for apex speed column
        possible_cols = [
            "ApexSpeed_A",
            "Speed_1",
            "Speed_A",
            "MinSpeed",
            "Speed",
            "ApexSpeed",
        ]
        target_col = None

        for col in possible_cols:
            if col in df.columns:
                target_col = col
                logger.debug(f"Using column for classification: {col}")
                break

        if target_col is None:
            msg = f"No apex speed column found. Available: {list(df.columns)}"
            logger.error(msg, **log_context)
            raise ValidationError(msg)

        # Classify corners
        df["CornerType"] = df[target_col].apply(classify_corner_type)

        counts = df["CornerType"].value_counts()
        logger.info(
            "Corners classified",
            classification=counts.to_dict(),
            **log_context,
        )
        return df

    except ValidationError:
        raise

    except Exception as e:
        msg = "Corner classification failed"
        logger.error(msg, error=str(e), **log_context, exc_info=True)
        raise ValidationError(msg) from e


def aggregate_time_loss_by_type(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """
    Aggregate time loss by corner type.

    Groups DataFrame by CornerType and sums TimeLoss,
    then sorts by corner speed (Low → Medium → High).

    Args:
        df: Classified DataFrame with TimeLoss and CornerType

    Returns:
        Aggregated DataFrame, or None if CornerType missing

    Raises:
        ValidationError: If aggregation fails
    """
    log_context = {"rows": len(df) if df is not None else 0}

    try:
        if df is None or "CornerType" not in df.columns:
            logger.warning(
                "No CornerType column for aggregation",
                columns=list(df.columns) if df is not None else [],
            )
            return None

        logger.debug("Aggregating time loss by corner type", **log_context)

        agg = df.groupby("CornerType")["TimeLoss"].sum().reset_index()

        # Enforce sort order: Low → Medium → High → Unknown
        sorter = {
            "Low Speed": 0,
            "Medium Speed": 1,
            "High Speed": 2,
            "Unknown": 3,
        }
        agg["sort_key"] = agg["CornerType"].map(sorter)
        agg = agg.sort_values("sort_key").drop("sort_key", axis=1)

        logger.info("Time loss aggregated", counts=agg.to_dict(), **log_context)
        return agg

    except Exception as e:
        msg = "Time loss aggregation failed"
        logger.error(msg, error=str(e), **log_context, exc_info=True)
        raise ValidationError(msg) from e


def get_corner_type_advice(agg_df: Optional[pd.DataFrame]) -> list:
    """
    Generate coaching advice based on time loss by corner type.

    Identifies the corner type with the largest time differential
    and provides targeted coaching based on grip characteristics.

    Args:
        agg_df: Aggregated time loss by corner type

    Returns:
        List of coaching tips

    Raises:
        ValidationError: If analysis fails
    """
    log_context = {"rows": len(agg_df) if agg_df is not None else 0}

    try:
        if agg_df is None or agg_df.empty:
            logger.warning("No aggregated data for advice", **log_context)
            return []

        logger.debug("Generating corner type advice", **log_context)

        # Find category with highest absolute difference
        agg_df["AbsLoss"] = agg_df["TimeLoss"].abs()
        worst = agg_df.loc[agg_df["AbsLoss"].idxmax()]

        type_name = worst["CornerType"]
        loss_val = worst["TimeLoss"]

        tips = []

        # Ignore tiny differences
        if abs(loss_val) < 0.05:
            logger.info("Time loss insignificant", max_loss=abs(loss_val))
            return ["Pace is very evenly matched across all corner types."]

        loss_str = f"{abs(loss_val):.3f}s"

        # Type-specific advice
        if type_name == "Low Speed":
            advice = "Focus on **mechanical grip/rotation**. Optimize trail-braking to rotate the car earlier."
        elif type_name == "Medium Speed":
            advice = (
                "Focus on **balance**. Ensure smooth transition from brake to throttle."
            )
        elif type_name == "High Speed":
            advice = "Focus on **aerodynamic trust**. Commit to throttle earlier and minimize scrubbing."
        else:
            advice = "Check telemetry consistency."

        # Convention: TimeLoss > 0 = Driver A faster (gaining time)
        if loss_val > 0:
            tips.append(
                f"Major deficit in **{type_name}** corners (losing {loss_str}). {advice}"
            )
        else:
            tips.append(
                f"Strong performance in **{type_name}** corners (gaining {loss_str}). Keep it up!"
            )

        logger.info("Advice generated", tips_count=len(tips), **log_context)
        return tips

    except Exception as e:
        msg = "Corner type advice generation failed"
        logger.error(msg, error=str(e), **log_context, exc_info=True)
        raise ValidationError(msg) from e
