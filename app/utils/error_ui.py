import streamlit as st

from src.exceptions import (
    SessionDataError,
    FastF1APIError,
    APIError,
    DataError,
    CacheError,
    DriverNotFoundError,
    InvalidSessionError,
    InvalidTelemetryError,
    TelemetryError,
    ComparisonError,
    TimeCalculationError,
    ReportGenerationError,
    CoachingEngineError,
)


DOMAIN_EXCEPTIONS = (
    SessionDataError,
    FastF1APIError,
    APIError,
    DataError,
    CacheError,
    DriverNotFoundError,
    InvalidSessionError,
    InvalidTelemetryError,
    TelemetryError,
    ComparisonError,
    TimeCalculationError,
    ReportGenerationError,
    CoachingEngineError,
)


def show_domain_error(
    exc: Exception,
    fallback: str = "An unexpected error occurred.",
    context: str = "general",
) -> None:
    """Map domain exceptions to clear user-facing Streamlit messages.

    Args:
        exc: Exception raised in the flow.
        fallback: Default message for unknown exceptions.
        context: UI context (e.g., "home", "comparison").
    """
    if isinstance(exc, SessionDataError):
        if context == "comparison":
            st.error(
                "Session data could not be loaded. Please check year/track/session."
            )
        else:
            st.error("Session data could not be loaded.")
    elif isinstance(exc, DriverNotFoundError):
        if context == "comparison":
            st.error("At least one driver was not found in this session.")
        else:
            st.error("Driver data could not be resolved.")
    elif isinstance(exc, (InvalidSessionError, InvalidTelemetryError)):
        if context == "comparison":
            st.error("Session or telemetry data is incomplete or invalid.")
        else:
            st.error("Loaded session data is incomplete or invalid.")
    elif isinstance(exc, (FastF1APIError, APIError)):
        st.error("FastF1 API is currently unreachable. Please try again later.")
    elif isinstance(exc, CacheError):
        st.error("Cache error detected. Please reload the page.")
    elif isinstance(exc, TelemetryError):
        if context == "comparison":
            st.error(
                "Telemetry could not be processed. Please try different drivers/session."
            )
        else:
            st.error("Telemetry data could not be processed.")
    elif isinstance(exc, DataError):
        st.error("Event data is incomplete or invalid.")
    elif isinstance(exc, ComparisonError):
        if context == "comparison":
            st.error(
                "Driver comparison failed. Data could not be synchronized properly."
            )
        else:
            st.error("Analysis could not be completed.")
    elif isinstance(exc, TimeCalculationError):
        if context == "comparison":
            st.error("Time loss calculation failed.")
        else:
            st.error("Time calculation failed.")
    elif isinstance(exc, ReportGenerationError):
        if context == "comparison":
            st.error("Executive report could not be generated.")
        else:
            st.error("Report could not be generated.")
    elif isinstance(exc, CoachingEngineError):
        if context == "comparison":
            st.error("Coaching analysis could not be generated.")
        else:
            st.error("Coaching suggestions could not be generated.")
    else:
        st.error(fallback)
