import sys
import os

# Ensure project root is on sys.path so 'src' is importable
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import streamlit as st

from src.logging import get_logger

logger = get_logger(__name__)

# redirect immediately to Home page
logger.info("App entrypoint loaded, redirecting to home")
st.switch_page("pages/1_Home.py")
st.markdown(
    """
<style>
header {visibility: hidden !important;}
</style>
""",
    unsafe_allow_html=True,
)
