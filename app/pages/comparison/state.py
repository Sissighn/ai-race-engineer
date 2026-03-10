import streamlit as st

from src.logging import get_logger

logger = get_logger(__name__)


_SESSION_KEYS_TO_RESET = ["session", "drivers_full", "driver_map", "compare_result"]


def reset_cache() -> None:
    """Reset comparison-related session cache keys."""
    for key in _SESSION_KEYS_TO_RESET:
        if key in st.session_state:
            st.session_state[key] = None
    logger.info("Comparison cache reset")


def ensure_selection_state(year: int, track: str, session_type: str) -> bool:
    """Ensure selection state consistency.

    Returns True when a rerun was triggered due to selection change.
    """
    sel_tuple = (year, track, session_type)

    if "last_selection" not in st.session_state:
        st.session_state["last_selection"] = sel_tuple
        return False

    if st.session_state["last_selection"] != sel_tuple:
        reset_cache()
        st.session_state["last_selection"] = sel_tuple
        st.rerun()
        return True

    return False
