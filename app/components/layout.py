import streamlit as st

def sidebar_driver_selector():
    st.sidebar.header("Driver Selection")
    driver_a = st.sidebar.text_input("Driver A (e.g., VER)", "VER")
    driver_b = st.sidebar.text_input("Driver B (e.g., PER)", "PER")

    return driver_a.upper(), driver_b.upper()
