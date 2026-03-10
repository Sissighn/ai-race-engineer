import pandas as pd
import pytest
from pydantic import ValidationError

from src.models import (
    DriverDNAMetrics,
    LatestSessionsPayload,
    RaceEngineerReport,
    SeasonResultsPayload,
)


def test_race_engineer_report_model_valid():
    model = RaceEngineerReport(
        headline="Headline",
        type_summary=["a", "b"],
        key_fix="Fix",
    )
    assert model.headline == "Headline"
    assert model.type_summary == ["a", "b"]
    assert model.key_fix == "Fix"


def test_driver_dna_metrics_range_validation():
    with pytest.raises(ValidationError):
        DriverDNAMetrics(
            aggressiveness=150,
            cornering=50,
            smoothness=50,
            full_throttle=50,
            gear_workload=50,
        )


def test_driver_dna_metrics_to_legacy_dict():
    model = DriverDNAMetrics(
        aggressiveness=50.44,
        cornering=70,
        smoothness=80,
        full_throttle=65,
        gear_workload=40,
    )
    legacy = model.to_legacy_dict()
    assert legacy["Aggressiveness"] == 50.4
    assert set(legacy.keys()) == {
        "Aggressiveness",
        "Cornering",
        "Smoothness",
        "FullThrottle",
        "GearWorkload",
    }


def test_latest_sessions_payload_accepts_dataframe_and_timestamp():
    events = pd.DataFrame({"EventName": ["A"]})
    payload = LatestSessionsPayload(
        events=events,
        latest_completed_index=0,
        next_session_name="Q",
        next_session_time=pd.Timestamp("2025-01-01", tz="UTC"),
        next_event_index=1,
    )
    assert isinstance(payload.events, pd.DataFrame)
    assert payload.next_session_name == "Q"


def test_season_results_payload_defaults_to_none():
    payload = SeasonResultsPayload()
    assert payload.Q is None
    assert payload.SQ is None
    assert payload.S is None
    assert payload.R is None
