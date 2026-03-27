import html
import re

import streamlit as st

from src.logging import get_logger

logger = get_logger(__name__)


def render_race_engineer_report(report_data):
    """
    Renders the report data in a stylized container.
    """
    if not report_data:
        logger.info("No report data provided")
        return

    # 1. Define CSS styles
    st.markdown(
        """
    <style>
    .report-container {
        background-color: #1E1E1E;
        border-left: 4px solid #7d0e0e;
        padding: 20px;
        border-radius: 4px;
        margin-bottom: 20px;
        font-family: 'Courier New', Courier, monospace;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .report-header {
        color: #A48FFF;
        font-weight: bold;
        font-size: 0.9rem;
        letter-spacing: 1px;
        margin-bottom: 15px;
        border-bottom: 1px solid #333;
        padding-bottom: 5px;
        text-transform: uppercase;
    }
    .report-section {
        margin-bottom: 12px;
        font-size: 1.0rem;
        line-height: 1.5;
        color: #EEE;
    }
    .report-fix {
        background-color: #2D1A1A;
        padding: 12px;
        border-radius: 4px;
        border: 1px solid #7d0e0e;
        color: #FFB7D5;
        font-weight: bold;
        margin-top: 15px;
    }
    /* Bold text styling */
    .report-section b, .report-fix b {
        color: #FFF;
        font-weight: 900;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )

    # 2. Prepare data
    headline = report_data.get("headline", "")
    type_summary = report_data.get("type_summary", [])
    key_fix = report_data.get("key_fix", "")

    # Helper: Convert Markdown bold (**) to HTML bold (<b>)
    def md_to_html(text):
        if not text:
            return ""
        return re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)

    headline_html = md_to_html(headline)
    # Join summary lines with line breaks
    summary_html = "<br>".join([md_to_html(s) for s in type_summary])
    fix_html = md_to_html(key_fix)

    # 3. Assemble HTML output
    # Use .strip() to prevent whitespace from confusing Markdown rendering.
    html_content = f"""
<div class="report-container">
    <div class="report-header">🏁 RACE ENGINEER SUMMARY // AI GENERATED</div>
    <div class="report-section">
        {headline_html}
    </div>
    <div class="report-section">
        {summary_html}
    </div>
    <div class="report-fix">
        {fix_html}
    </div>
</div>
"""

    try:
        st.markdown(html_content.strip(), unsafe_allow_html=True)
        logger.debug("Race engineer report rendered")
    except Exception as e:
        logger.error(
            "Failed to render race engineer report", error=str(e), exc_info=True
        )
        st.warning("Report could not be rendered.")
