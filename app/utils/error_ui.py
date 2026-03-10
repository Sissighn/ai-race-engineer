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
    fallback: str = "Ein unerwarteter Fehler ist aufgetreten.",
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
                "Session-Daten konnten nicht geladen werden. Bitte Jahr/Track/Session prüfen."
            )
        else:
            st.error("Session-Daten konnten nicht geladen werden.")
    elif isinstance(exc, DriverNotFoundError):
        if context == "comparison":
            st.error("Mindestens ein Fahrer wurde in der Session nicht gefunden.")
        else:
            st.error("Fahrer-Daten konnten nicht aufgelöst werden.")
    elif isinstance(exc, (InvalidSessionError, InvalidTelemetryError)):
        if context == "comparison":
            st.error("Session- oder Telemetry-Daten sind unvollständig oder ungültig.")
        else:
            st.error("Geladene Session-Daten sind unvollständig oder ungültig.")
    elif isinstance(exc, (FastF1APIError, APIError)):
        st.error(
            "FastF1 API ist aktuell nicht erreichbar. Bitte später erneut versuchen."
        )
    elif isinstance(exc, CacheError):
        st.error("Cache-Fehler erkannt. Bitte Seite neu laden.")
    elif isinstance(exc, DataError):
        st.error("Event-Daten sind unvollständig oder ungültig.")
    elif isinstance(exc, TelemetryError):
        if context == "comparison":
            st.error(
                "Telemetry konnte nicht verarbeitet werden. Bitte andere Fahrer/Session testen."
            )
        else:
            st.error("Telemetry-Daten konnten nicht verarbeitet werden.")
    elif isinstance(exc, ComparisonError):
        if context == "comparison":
            st.error(
                "Driver-Vergleich fehlgeschlagen. Daten konnten nicht sauber synchronisiert werden."
            )
        else:
            st.error("Analyse konnte nicht abgeschlossen werden.")
    elif isinstance(exc, TimeCalculationError):
        if context == "comparison":
            st.error("Time-Loss-Berechnung fehlgeschlagen.")
        else:
            st.error("Zeitberechnung fehlgeschlagen.")
    elif isinstance(exc, ReportGenerationError):
        if context == "comparison":
            st.error("Executive Report konnte nicht erzeugt werden.")
        else:
            st.error("Report konnte nicht erzeugt werden.")
    elif isinstance(exc, CoachingEngineError):
        if context == "comparison":
            st.error("Coaching-Analyse konnte nicht erstellt werden.")
        else:
            st.error("Coaching-Hinweise konnten nicht erstellt werden.")
    else:
        st.error(fallback)
