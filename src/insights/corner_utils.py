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


def get_corner_type_advice(
    agg_df: Optional[pd.DataFrame],
    driver_a: str = "Driver A",
    driver_b: str = "Driver B",
) -> list[str]:
    """
    Generate post-race engineering insights from corner-type deltas.

    Produces concise, professional recommendations based on where
    the largest time deficit occurred.

    Args:
        agg_df: Aggregated time loss by corner type

    Returns:
        List of insight strings

    Raises:
        ValidationError: If analysis fails
    """
    log_context = {
        "rows": len(agg_df) if agg_df is not None else 0,
        "driver_a": driver_a,
        "driver_b": driver_b,
    }

    try:
        if agg_df is None or agg_df.empty:
            logger.warning("No aggregated data for advice", **log_context)
            return []

        logger.debug("Generating corner type advice", **log_context)

        if "CornerType" not in agg_df.columns or "TimeLoss" not in agg_df.columns:
            logger.warning(
                "Missing required columns for advice",
                columns=list(agg_df.columns),
                **log_context,
            )
            return []

        work = agg_df.copy()
        work["TimeLoss"] = pd.to_numeric(work["TimeLoss"], errors="coerce").fillna(0.0)

        total_delta = float(work["TimeLoss"].sum())

        # TimeLoss convention from time_loss_engine:
        # Positive => driver_a gains (driver_b loses)
        # Negative => driver_a loses
        if total_delta > 0:
            losing_driver = driver_b
            reference_driver = driver_a
            work["Deficit"] = work["TimeLoss"].clip(lower=0.0)
        elif total_delta < 0:
            losing_driver = driver_a
            reference_driver = driver_b
            work["Deficit"] = (-work["TimeLoss"]).clip(lower=0.0)
        else:
            losing_driver = None
            reference_driver = None
            work["Deficit"] = 0.0

        # Sort by deficit from largest to smallest
        deficits = work.sort_values("Deficit", ascending=False)
        top = deficits.iloc[0]

        # Ignore tiny differences
        if float(top["Deficit"]) < 0.05:
            logger.info("Time loss insignificant", max_loss=float(top["Deficit"]))
            return [
                "No dominant deficit by corner category (all deltas below 0.050s).",
                "Maintain current setup baseline and focus on execution consistency corner-to-corner.",
                "For the next run, prioritize repeatability metrics (brake release timing, minimum speed, throttle pickup) over setup changes.",
            ]

        primary_type = str(top["CornerType"])
        primary_loss = float(top["Deficit"])

        tips: list[str] = [
            f"Primary deficit for {losing_driver}: {primary_type} corners ({primary_loss:.3f}s) relative to {reference_driver}.",
        ]

        # Type-specific, post-race technical actions
        if primary_type == "Low Speed":
            tips.append(
                "Action: improve low-speed rotation by refining trail-brake release, reducing entry under-rotation, and checking differential/coast settings on corner entry."
            )
        elif primary_type == "Medium Speed":
            tips.append(
                "Action: stabilize the transition phase by reducing brake-throttle overlap and smoothing steering-rate input through mid-corner."
            )
        elif primary_type == "High Speed":
            tips.append(
                "Action: improve high-speed commitment by reviewing lift points, minimizing steering scrub, and validating aero balance stability in fast direction changes."
            )
        else:
            tips.append(
                "Action: validate corner classification and telemetry consistency before applying setup changes."
            )

        # Secondary and tertiary priorities (if meaningful)
        secondary_rows = deficits.iloc[1:]
        secondary_rows = secondary_rows[secondary_rows["Deficit"] >= 0.05]

        if not secondary_rows.empty:
            sec = secondary_rows.iloc[0]
            tips.append(
                f"Secondary priority: {sec['CornerType']} corners ({float(sec['Deficit']):.3f}s). Address this after the primary category."
            )

        # Closing operational recommendation (always included)
        tips.append(
            "Validation plan: compare min speed, brake release point, and throttle-at-apex for the top deficit category before the next setup iteration."
        )

        logger.info("Advice generated", tips_count=len(tips), **log_context)
        return tips

    except Exception as e:
        msg = "Corner type advice generation failed"
        logger.error(msg, error=str(e), **log_context, exc_info=True)
        raise ValidationError(msg) from e
