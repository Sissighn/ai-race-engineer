import streamlit as st
import os


def load_css(file_name="style.css"):
    css_path = os.path.join(os.path.dirname(__file__), "..", "assets", file_name)

    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
