import os
from pathlib import Path

import streamlit as st

from src.logging import get_logger

logger = get_logger(__name__)


def get_assets_dir() -> Path:
    """Return the app assets directory for local and container runtimes."""
    return Path(
        os.getenv(
            "AI_RACE_ENGINEER_ASSETS_DIR",
            Path(__file__).resolve().parent.parent / "assets",
        )
    ).resolve()


def load_css(file_name: str = "style.css") -> None:
    """Load and inject a CSS file into the Streamlit page.

    Args:
        file_name: Name of the CSS file in the assets directory.
    """
    css_path = get_assets_dir() / file_name
    try:
        with css_path.open(encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
        logger.debug("CSS loaded", file_name=file_name, css_path=css_path)
    except FileNotFoundError:
        logger.error("CSS file not found", file_name=file_name, css_path=str(css_path))
        st.warning(f"CSS file not found: {file_name}")
    except Exception as e:
        logger.error("Failed to load CSS", error=str(e), file_name=file_name)
        st.warning("Styles could not be loaded.")
