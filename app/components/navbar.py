import base64
import os

import streamlit as st

from app.utils.ui import get_assets_dir
from src.logging import get_logger

logger = get_logger(__name__)


class Navbar:
    def __init__(self):
        self.assets_path = str(get_assets_dir())

    def _load_asset(self, filename):
        path = os.path.join(self.assets_path, filename)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                logger.error(
                    "Failed to load text asset", filename=filename, error=str(e)
                )
        return ""

    def _get_logo_b64(self):
        path = os.path.join(self.assets_path, "logo.png")
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    return base64.b64encode(f.read()).decode()
            except Exception as e:
                logger.warning("Failed to read navbar logo", error=str(e), path=path)
        return None

    def render(self):
        html_tpl = self._load_asset("navbar.html")
        css_content = self._load_asset("navbar.css")
        logo_b64 = self._get_logo_b64()

        if not html_tpl:
            logger.warning("Navbar template missing or empty")
            return

        logo_tag = (
            f'<img src="data:image/png;base64,{logo_b64}" class="nav-logo">'
            if logo_b64
            else ""
        )

        # Inject CSS and logo into the HTML template placeholders
        full_html = html_tpl.replace("{{CSS_STYLE}}", css_content).replace(
            "{{LOGO_HTML}}", logo_tag
        )

        # Collapse the HTML into a single line to prevent Streamlit from
        # misinterpreting indented lines as Markdown code blocks.
        clean_html = "".join([line.strip() for line in full_html.splitlines()])

        # Use st.markdown instead of st.html — st.html renders inside an iframe,
        # which breaks position:fixed (it becomes relative to the iframe, not the viewport).
        try:
            st.markdown(clean_html, unsafe_allow_html=True)
            logger.debug("Navbar rendered")
        except Exception as e:
            logger.error("Failed to render navbar", error=str(e), exc_info=True)


def navbar():
    try:
        Navbar().render()
    except Exception as e:
        logger.error("Navbar render crashed", error=str(e), exc_info=True)
