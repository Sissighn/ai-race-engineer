import streamlit as st
import base64
import os


class Navbar:
    def __init__(self):
        # Pfade absolut sicherstellen
        self.script_path = os.path.dirname(os.path.abspath(__file__))
        self.assets_path = os.path.normpath(
            os.path.join(self.script_path, "..", "assets")
        )

    def _load_asset(self, filename):
        path = os.path.join(self.assets_path, filename)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    def _get_logo_b64(self):
        path = os.path.join(self.assets_path, "logo.png")
        if os.path.exists(path):
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode()
        return None

    def render(self):
        html_tpl = self._load_asset("navbar.html")
        css_content = self._load_asset("navbar.css")
        logo_b64 = self._get_logo_b64()

        logo_tag = (
            f'<img src="data:image/png;base64,{logo_b64}" class="nav-logo">'
            if logo_b64
            else ""
        )

        # Platzhalter ersetzen
        full_html = html_tpl.replace("{{CSS_STYLE}}", css_content).replace(
            "{{LOGO_HTML}}", logo_tag
        )

        # DER FIX: Wir entfernen ALLES, was Streamlit als Markdown-Code interpretieren könnte.
        # Wir machen aus dem HTML einen einzigen, langen String ohne Einrückungen.
        clean_html = "".join([line.strip() for line in full_html.splitlines()])

        # Nutze st.html (wenn vorhanden) oder st.markdown
        if hasattr(st, "html"):
            st.html(clean_html)
        else:
            st.markdown(clean_html, unsafe_allow_html=True)


def navbar():
    Navbar().render()
