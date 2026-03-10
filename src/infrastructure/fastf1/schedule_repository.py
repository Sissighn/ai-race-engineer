import fastf1
import pandas as pd


def get_event_schedule(year: int, include_testing: bool = False) -> pd.DataFrame:
    return fastf1.get_event_schedule(year, include_testing=include_testing)
