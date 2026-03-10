import pytest

from src.exceptions import (
    AiRaceEngineerException,
    DataError,
    SessionDataError,
    TelemetryError,
    CornerSegmentationError,
    FeatureEngineeringError,
    PreprocessingError,
    APIError,
    FastF1APIError,
    CacheError,
    CacheCorruptionError,
    ValidationError,
    DriverNotFoundError,
    InvalidSessionError,
    InvalidTelemetryError,
    AnalysisError,
    TimeCalculationError,
    ComparisonError,
    ReportGenerationError,
    CoachingEngineError,
    ConfigError,
    UIError,
    handle_error,
)


@pytest.mark.parametrize(
    ("child", "parent"),
    [
        (DataError, AiRaceEngineerException),
        (SessionDataError, DataError),
        (TelemetryError, DataError),
        (CornerSegmentationError, DataError),
        (FeatureEngineeringError, DataError),
        (PreprocessingError, DataError),
        (APIError, AiRaceEngineerException),
        (FastF1APIError, APIError),
        (CacheError, APIError),
        (CacheCorruptionError, CacheError),
        (ValidationError, AiRaceEngineerException),
        (DriverNotFoundError, ValidationError),
        (InvalidSessionError, ValidationError),
        (InvalidTelemetryError, ValidationError),
        (AnalysisError, AiRaceEngineerException),
        (TimeCalculationError, AnalysisError),
        (ComparisonError, AnalysisError),
        (ReportGenerationError, AnalysisError),
        (CoachingEngineError, AnalysisError),
        (ConfigError, AiRaceEngineerException),
        (UIError, AiRaceEngineerException),
    ],
)
def test_exception_inheritance(child, parent):
    assert issubclass(child, parent)


def test_handle_error_reraises_as_domain_exception():
    with pytest.raises(SessionDataError):
        with handle_error(SessionDataError, context="test context"):
            raise RuntimeError("boom")


def test_handle_error_no_reraise_calls_callback():
    captured = []

    def _cb(exc):
        captured.append(str(exc))

    with handle_error(SessionDataError, context="x", reraise=False, on_error=_cb):
        raise RuntimeError("boom")

    assert captured == ["boom"]


def test_handle_error_passes_through_existing_domain_exception():
    with pytest.raises(TelemetryError):
        with handle_error(SessionDataError, context="pass-through"):
            raise TelemetryError("already domain")
