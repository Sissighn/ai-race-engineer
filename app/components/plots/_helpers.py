"""
Pure utility functions shared across all chart modules.

None of these functions produce side effects – they transform values or
DataFrames and return results, making them straightforward to unit-test
in isolation and safe to import without triggering Streamlit calls.
"""

import pandas as pd

from ._theme import APEX_SPEED_TIE_THRESHOLD, TIME_LOSS_TIE_THRESHOLD


def _format_corner_label(corner_value):
    """Convert a raw corner identifier to a human-readable label.

    Converts numeric values to integers to avoid labels like "Corner 3.0".
    Falls back to a string representation when conversion is not possible.
    """
    try:
        return f"Corner {int(corner_value)}"
    except (TypeError, ValueError):
        return f"Corner {corner_value}"


def _sort_by_corner(df):
    """Return a copy of *df* sorted by corner number in ascending order.

    Coerces the Corner column to numeric for correct ordering (so Corner 10
    comes after Corner 9, not after Corner 1). Non-numeric corners are sorted
    after numeric ones via the stable secondary sort on the raw Corner column.
    The temporary sort key column is dropped before returning.
    """
    plot_df = df.copy()
    plot_df["_corner_sort"] = pd.to_numeric(plot_df["Corner"], errors="coerce")
    plot_df = plot_df.sort_values(["_corner_sort", "Corner"], kind="stable")
    return plot_df.drop(columns=["_corner_sort"])


def _classify_apex_advantage(delta, driver_a, driver_b):
    """Map a signed speed delta (driver_a − driver_b) to a categorical advantage label.

    Values within ±APEX_SPEED_TIE_THRESHOLD are treated as a tie to avoid
    surfacing telemetry noise as meaningful differences.
    """
    if delta > APEX_SPEED_TIE_THRESHOLD:
        return f"{driver_a} faster"
    if delta < -APEX_SPEED_TIE_THRESHOLD:
        return f"{driver_b} faster"
    return "Nearly equal"


def _format_delta_label(value):
    """Format a speed delta value for display on bar chart labels.

    Returns '≈0 km/h' for values within the tie threshold to make
    negligible differences visually obvious at a glance.
    """
    return "≈0 km/h" if abs(value) <= APEX_SPEED_TIE_THRESHOLD else f"{value:+.1f} km/h"


def _format_time_label(value: float) -> str:
    """Format a lap-time delta value for bar labels (millisecond precision)."""
    return "≈0s" if abs(value) <= TIME_LOSS_TIE_THRESHOLD else f"{value:+.3f}s"


def _near_equal_mask(series: pd.Series) -> pd.Series:
    """Return a boolean mask that is True where values are within the tie threshold.

    Used to identify 'Nearly equal' corners so they receive a special
    open-circle marker on delta charts instead of a bar.
    """
    return series.abs() <= APEX_SPEED_TIE_THRESHOLD
