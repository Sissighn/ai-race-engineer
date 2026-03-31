import fastf1
import pandas as pd


def get_event_schedule(year: int, include_testing: bool = False) -> pd.DataFrame:
    """Fetch the F1 event schedule for a given year.

    Args:
        year: Championship season year.
        include_testing: Whether to include pre-season testing events.

    Returns:
        DataFrame with event schedule data.
    """
    return fastf1.get_event_schedule(year, include_testing=include_testing)
