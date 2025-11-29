# app/components/navbar.py
import streamlit as st

def navbar():
    st.markdown("""
    <style>
    section[data-testid="stSidebar"] {
        display: none !important;
    }
    div[data-testid="collapsedControl"] {
        display: none !important;
    }
    /* Remove the left margin reserved for the sidebar */
    .main {
        margin-left: 0 !important;
    }
    /* Remove padding from container */
    .block-container {
        padding-top: 4rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }

    /* NAVBAR styling */
    .navbar {
        background: #ffffff;
        padding: 16px 32px;
        border-bottom: 1px solid #EDE7FF;
        display: flex;
        align-items: center;
        justify-content: space-between;
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        z-index: 999;
    }

    .nav-title {
        font-family: 'Poppins', sans-serif;
        font-size: 20px;
        font-weight: 700;
        color: #4636C5;
    }

    .nav-links a {
        margin-left: 32px;
        text-decoration: none;
        color: #5e4ac7;
        font-size: 16px;
        font-weight: 500;
    }

    .nav-links a:hover {
        color: #8c6bff;
    }
    </style>
    """, unsafe_allow_html=True)

    # Navbar links (Streamlit native routing)
    with st.container():
        col1, col2, col3 = st.columns([4, 1, 1])
        with col1:
            st.markdown("<div class='nav-title'>AI Race Engineer</div>", unsafe_allow_html=True)
        with col2:
            st.page_link("pages/1_Home.py", label="Home")
        with col3:
            st.page_link("pages/2_Driver_Comparison.py", label="Driver Comparison")

        st.markdown("<div class='navbar'></div>", unsafe_allow_html=True)
