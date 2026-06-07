from __future__ import annotations

from typing import Optional

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field


class RaceEngineerReport(BaseModel):
    headline: str = Field(..., min_length=1)
    type_summary: list[str] = Field(default_factory=list)
    key_fix: str = Field(..., min_length=1)


class DriverDNAMetrics(BaseModel):
    aggressiveness: float = Field(..., ge=0, le=100)
    cornering: float = Field(..., ge=0, le=100)
    smoothness: float = Field(..., ge=0, le=100)
    full_throttle: float = Field(..., ge=0, le=100)
    gear_workload: float = Field(..., ge=0, le=100)

    def to_legacy_dict(self) -> dict[str, float]:
        return {
            "Aggressiveness": round(self.aggressiveness, 1),
            "Cornering": round(self.cornering, 1),
            "Smoothness": round(self.smoothness, 1),
            "FullThrottle": round(self.full_throttle, 1),
            "GearWorkload": round(self.gear_workload, 1),
        }


class LatestSessionsPayload(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    events: pd.DataFrame
    latest_completed_index: int
    next_session_name: str
    next_session_time: Optional[pd.Timestamp] = None
    next_event_index: Optional[int] = None


class SeasonResultsPayload(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    Q: Optional[pd.DataFrame] = None
    SQ: Optional[pd.DataFrame] = None
    S: Optional[pd.DataFrame] = None
    R: Optional[pd.DataFrame] = None

    def get(self, session_key: str, default=None):
        if hasattr(self, session_key):
            value = getattr(self, session_key)
            return value if value is not None else default
        return default

    def to_session_dict(self) -> dict[str, Optional[pd.DataFrame]]:
        return {
            "Q": self.Q,
            "SQ": self.SQ,
            "S": self.S,
            "R": self.R,
        }


class ChampionshipStandingsPayload(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    drivers_df: pd.DataFrame
    constructors_df: pd.DataFrame
    season_year: int
    events_count: int
    sessions_loaded: int


class ComparisonComputeResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    missing: list[str] = Field(default_factory=list)
    tel_a: Optional[pd.DataFrame] = None
    tel_b: Optional[pd.DataFrame] = None
    comp: Optional[pd.DataFrame] = None
    tl: Optional[pd.DataFrame] = None


class ComparisonSessionState(BaseModel):
    """Immutable state object holding a complete driver comparison result."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    session: object  # FastF1 Session – not serializable, hence 'object'
    driver_a: str
    driver_b: str
    tel_a: pd.DataFrame
    tel_b: pd.DataFrame
    comp: pd.DataFrame
    tl: pd.DataFrame


class CornerAnalysisPayload(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tl_classified: Optional[pd.DataFrame] = None
    agg_types: Optional[pd.DataFrame] = None
    advice_list: list[str] = Field(default_factory=list)


class HomeContextPayload(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    events_df: pd.DataFrame
    latest_completed_idx: int
    next_session_name: str
    next_session_time: Optional[pd.Timestamp] = None
    display_event: pd.Series
    season_year: int
    event_key: str
