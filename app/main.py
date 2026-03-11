import streamlit as st

from src.logging import get_logger, initialize_logging

initialize_logging()

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
