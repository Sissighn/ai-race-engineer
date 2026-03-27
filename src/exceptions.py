"""
Custom Exception Classes for AI Race Engineer.

This module defines domain-specific exceptions for better error handling
and debugging throughout the application.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Callable, Optional, Type


class AiRaceEngineerException(Exception):
    """Base exception class for all AI Race Engineer errors."""

    pass


# ─────────────────────────────────────────────────────────────────────
# DATA & API ERRORS
# ─────────────────────────────────────────────────────────────────────


class DataError(AiRaceEngineerException):
    """Base exception for data-related errors."""

    pass


class SessionDataError(DataError):
    """Raised when FastF1 session data cannot be loaded."""

    pass


class TelemetryError(DataError):
    """Raised when telemetry processing fails."""

    pass


class CornerSegmentationError(DataError):
    """Raised when corner segmentation algorithm fails."""

    pass


class FeatureEngineeringError(DataError):
    """Raised when feature computation fails."""

    pass


class PreprocessingError(DataError):
    """Raised when telemetry preprocessing fails."""

    pass


# ─────────────────────────────────────────────────────────────────────
# API & CACHE ERRORS
# ─────────────────────────────────────────────────────────────────────


class APIError(AiRaceEngineerException):
    """Base exception for API-related errors."""

    pass


class FastF1APIError(APIError):
    """Raised when FastF1 API call fails."""

    pass


class CacheError(APIError):
    """Raised when cache operations fail."""

    pass


class CacheCorruptionError(CacheError):
    """Raised when cache data is corrupted."""

    pass


# ─────────────────────────────────────────────────────────────────────
# VALIDATION ERRORS
# ─────────────────────────────────────────────────────────────────────


class ValidationError(AiRaceEngineerException):
    """Base exception for validation errors."""

    pass


class DriverNotFoundError(ValidationError):
    """Raised when driver is not found in session."""

    pass


class InvalidSessionError(ValidationError):
    """Raised when session data is invalid."""

    pass


class InvalidTelemetryError(ValidationError):
    """Raised when telemetry data is invalid."""

    pass


# ─────────────────────────────────────────────────────────────────────
# BUSINESS LOGIC ERRORS
# ─────────────────────────────────────────────────────────────────────


class AnalysisError(AiRaceEngineerException):
    """Base exception for analysis/insights engine errors."""

    pass


class TimeCalculationError(AnalysisError):
    """Raised when time loss calculation fails."""

    pass


class ComparisonError(AnalysisError):
    """Raised when driver comparison fails."""

    pass


class ReportGenerationError(AnalysisError):
    """Raised when report generation fails."""

    pass


class CoachingEngineError(AnalysisError):
    """Raised when coaching engine fails."""

    pass


# ─────────────────────────────────────────────────────────────────────
# UI & CONFIG ERRORS
# ─────────────────────────────────────────────────────────────────────


class ConfigError(AiRaceEngineerException):
    """Raised when configuration is invalid."""

    pass


class UIError(AiRaceEngineerException):
    """Base exception for UI-related errors."""

    pass


# ─────────────────────────────────────────────────────────────────────
# CONTEXT MANAGER FOR ERROR TRACKING
# ─────────────────────────────────────────────────────────────────────


logger = logging.getLogger(__name__)


@contextmanager
def handle_error(
    error_type: Type[AiRaceEngineerException],
    context: str = "",
    reraise: bool = True,
    on_error: Optional[Callable] = None,
):
    """
    Context manager for graceful error handling with logging.

    Args:
        error_type: Exception type to catch and convert
        context: Additional context string for logging
        reraise: Whether to re-raise after handling
        on_error: Optional callback function on error

    Example:
        >>> with handle_error(SessionDataError, context="Loading 2024 Monaco"):
        >>>     session = fastf1.get_session(2024, "Monaco", "Q")
    """
    try:
        yield
    except AiRaceEngineerException:
        raise
    except Exception as e:
        msg = f"Error in {context}: {str(e)}" if context else str(e)
        logger.error(msg, exc_info=True)

        if on_error:
            on_error(e)

        if reraise:
            raise error_type(msg) from e
