import streamlit as st

st.set_page_config(
    page_title="AI Race Engineer",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# completely hide sidebar everywhere
st.markdown("""
<style>
[data-testid="stSidebar"] { display: none !important; }
[data-testid="stSidebarNav"] { display: none !important; }
[data-testid="stSidebarUserContent"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

# redirect
st.switch_page("pages/1_Home.py")
