"""
Coaching Engine - Automatic Improvement Suggestions.
"""

import pandas as pd

from src.exceptions import CoachingEngineError
from src.logging import get_logger

logger = get_logger(__name__)


def coaching_suggestions(df: pd.DataFrame, driver_a: str, driver_b: str) -> list[str]:
    log_context = {"driver_a": driver_a, "driver_b": driver_b, "rows": len(df)}

    if df is None or df.empty:
        logger.warning("No data for coaching suggestions", **log_context)
        return []

    try:
        logger.info("Generating coaching suggestions", **log_context)

        suggestions: list[str] = []

        for idx, row in df.iterrows():
            try:
                corner = int(row["Corner"])
                loss = row.get("TimeLoss", 0)

                entry = row.get("Delta_EntrySpeed", 0)
                apex = row.get("Delta_ApexSpeed", 0)
                exit_speed = row.get("Delta_ExitSpeed", 0)
                brake = row.get("Delta_AvgBrake", 0)
                throttle = row.get("Delta_ThrottleBelow30Pct", 0)

                if loss < 0:
                    losing_driver = driver_a
                elif loss > 0:
                    losing_driver = driver_b
                else:
                    continue

                line = f"Corner {corner} – {losing_driver}: "

                if abs(exit_speed) > 1.0:
                    if losing_driver == driver_a and exit_speed < 0:
                        line += "Improve exit acceleration. Consider earlier throttle commitment and smoother rotation. "
                    elif losing_driver == driver_b and exit_speed > 0:
                        line += "Improve exit acceleration. Focus on earlier throttle application and reducing hesitation. "

                if abs(apex) > 1.0:
                    if losing_driver == driver_a and apex < 0:
                        line += "Increase apex speed. Possible later turn-in, less brake pressure at rotation point. "
                    elif losing_driver == driver_b and apex > 0:
                        line += "Increase apex speed. Commit more to mid-corner rotation and carry more minimum speed. "

                if abs(entry) > 1.0:
                    if losing_driver == driver_a and entry < 0:
                        line += "Raise entry speed by braking slightly later and reducing pre-apex conservatism. "
                    elif losing_driver == driver_b and entry > 0:
                        line += "Raise entry speed by braking later and reducing early brake-phase. "

                if abs(brake) > 0.1:
                    if losing_driver == driver_a and brake < 0:
                        line += "Increase brake pressure stability to shorten braking phase. "
                    elif losing_driver == driver_b and brake < 0:
                        line += (
                            "Optimize brake pressure modulation to avoid over-braking. "
                        )

                if abs(throttle) > 0.05:
                    if losing_driver == driver_a and throttle > 0:
                        line += "Reduce throttle hesitation at the exit. "
                    elif losing_driver == driver_b and throttle < 0:
                        line += "Minimize coasting time after apex. "

                if line.strip() != f"Corner {corner} – {losing_driver}:":
                    suggestions.append(line.strip())

            except Exception as e:
                logger.warning(
                    "Error processing corner suggestion",
                    corner_idx=idx,
                    error=str(e),
                )
                continue

        logger.info(
            "Coaching suggestions generated",
            count=len(suggestions),
            **log_context,
        )
        return suggestions

    except Exception as e:
        msg = "Coaching engine failed"
        logger.error(msg, error=str(e), **log_context, exc_info=True)
        raise CoachingEngineError(msg) from e
