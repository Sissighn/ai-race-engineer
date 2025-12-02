import streamlit as st

# redirect immediately to Home page
st.switch_page("pages/1_Home.py")
st.markdown(
    """
<style>
header {visibility: hidden !important;}
</style>
""",
    unsafe_allow_html=True,
)
