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
    exc: Exception, fallback: str = "Ein unerwarteter Fehler ist aufgetreten."
) -> None:
    """Map domain exceptions to clear user-facing Streamlit messages."""
    if isinstance(exc, SessionDataError):
        st.error("Session-Daten konnten nicht geladen werden.")
    elif isinstance(exc, DriverNotFoundError):
        st.error("Mindestens ein Fahrer wurde in der Session nicht gefunden.")
    elif isinstance(exc, (InvalidSessionError, InvalidTelemetryError)):
        st.error("Session- oder Telemetry-Daten sind unvollständig oder ungültig.")
    elif isinstance(exc, (FastF1APIError, APIError)):
        st.error(
            "FastF1 API ist aktuell nicht erreichbar. Bitte später erneut versuchen."
        )
    elif isinstance(exc, CacheError):
        st.error("Cache-Fehler erkannt. Bitte Seite neu laden.")
    elif isinstance(exc, DataError):
        st.error("Event-Daten sind unvollständig oder ungültig.")
    elif isinstance(exc, TelemetryError):
        st.error(
            "Telemetry konnte nicht verarbeitet werden. Bitte andere Fahrer/Session testen."
        )
    elif isinstance(exc, ComparisonError):
        st.error(
            "Driver-Vergleich fehlgeschlagen. Daten konnten nicht sauber synchronisiert werden."
        )
    elif isinstance(exc, TimeCalculationError):
        st.error("Time-Loss-Berechnung fehlgeschlagen.")
    elif isinstance(exc, ReportGenerationError):
        st.error("Executive Report konnte nicht erzeugt werden.")
    elif isinstance(exc, CoachingEngineError):
        st.error("Coaching-Analyse konnte nicht erstellt werden.")
    else:
        st.error(fallback)
