"""Navbar component for the Streamlit app."""

import streamlit as st
import base64
import os


def load_logo_base64(path):
    """Loads image as base64 string."""
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def load_navbar_css():
    """Loads the external CSS file."""
    css_path = os.path.join(os.path.dirname(__file__), "..", "assets", "navbar.css")
    if os.path.exists(css_path):
        with open(css_path) as f:
            return f"<style>{f.read()}</style>"
    return ""


def navbar():
    """Renders the navigation bar."""
    # 1. Load assets
    logo_path = "app/assets/logo.png"
    logo_base64 = load_logo_base64(logo_path)
    css_style = load_navbar_css()

    # Prepare logo HTML
    if logo_base64:
        logo_html = f'<img src="data:image/png;base64,{logo_base64}" class="nav-logo">'
    else:
        logo_html = ""

    # 2. Define HTML structure
    # IMPORTANT: The string is not indented to avoid rendering issues.
    html_content = f"""
{css_style}
 <div class="f1-nav-container">
    <div class="f1-nav-content">
        <!-- LEFT: BRANDING -->
        <a href="Home" target="_self" class="f1-brand-group">
            <div class="f1-brand-content" style="display: flex; align-items: center; gap: 15px;">
                {logo_html}
                <div class="nav-title">AI Race Engineer</div>
            </div>
        </a>
        <!-- RIGHT: MOBILE TOGGLE -->
        <input type="checkbox" id="nav-toggle">
        <label for="nav-toggle" class="nav-burger">
            <div></div>
            <div></div>
            <div></div>
        </label>
        <!-- RIGHT: LINKS -->
        <div class="f1-links">
            <a href="Home" target="_self">Home</a>
            <a href="Driver_Comparison" target="_self">Driver Comparison</a>
        </div>
    </div>
 </div>
"""

    # 3. Render component
    st.markdown(html_content, unsafe_allow_html=True)
