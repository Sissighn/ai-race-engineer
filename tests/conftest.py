"""Pytest shared fixtures and hooks."""

from unittest.mock import MagicMock

import pandas as pd
import pytest


@pytest.fixture()
def sample_telemetry() -> pd.DataFrame:
    """Minimal telemetry DataFrame used across plot and analysis tests."""
    return pd.DataFrame(
        {
            "Distance": [0, 50, 100, 150, 200, 250, 300],
            "Speed": [120, 140, 130, 160, 180, 150, 170],
            "Brake": [0, 20, 80, 0, 0, 40, 0],
            "Throttle": [100, 60, 10, 80, 100, 30, 90],
            "nGear": [4, 5, 4, 5, 6, 4, 5],
        }
    )


@pytest.fixture()
def sample_time_loss_df() -> pd.DataFrame:
    """Minimal time-loss / corner DataFrame for analysis tests."""
    return pd.DataFrame(
        {
            "Corner": [1, 2, 3],
            "TimeLoss": [0.2, -0.1, 0.05],
            "Delta_ApexSpeed": [-2.0, 1.0, -0.5],
            "Delta_ExitSpeed": [-1.0, 2.0, 0.3],
            "CornerType": ["Low Speed", "High Speed", "Medium Speed"],
        }
    )


@pytest.fixture()
def mock_session() -> MagicMock:
    """Mock FastF1 session object for service-layer tests."""
    session = MagicMock()
    session.event = {"Location": "Silverstone", "EventName": "British Grand Prix"}
    session.session_info = {"Meeting": {"Name": "British Grand Prix"}}
    return session
