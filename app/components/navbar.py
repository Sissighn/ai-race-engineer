import streamlit as st

def navbar():
    """
    Custom navbar with working Streamlit page navigation
    """
    
    # CSS Styling
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Science+Gothic:wght@400;700&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');

    /* Navbar container - fixed height */
    .customNavbar {
        background: #ffffff;
        width: 100%;
        padding: 12px 32px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 1px solid #F1ECFF;
        box-shadow: 0px 3px 12px rgba(80, 60, 180, 0.05);
        position: fixed;
        top: 0;
        left: 0;
        z-index: 999;
        box-sizing: border-box;
        min-height: 60px;
        max-height: 60px;
    }

    .navBrand {
    font-family: 'Science Gothic', sans-serif;
    font-weight: 700;
    font-size: 2.8rem;
    letter-spacing: -0.5px;
    color: #ffffff;
    line-height: 1;
    white-space: nowrap;
}


    .navButtonContainer {
        display: flex;
        gap: 10px;
        align-items: center;
        flex-shrink: 0;
    }

    /* Remove default streamlit spacing */
    .block-container {
        padding-top: 2.0rem !important;
    }

    /* Hide default streamlit button container */
    div[data-testid="column"] {
        padding: 0 !important;
    }

    /* Style Streamlit buttons - compact size */
    div[data-testid="column"] > div > div > div > button {
        font-family: 'Inter', sans-serif !important;
        font-size: 0.9rem !important;
        font-weight: 500 !important;
        padding: 6px 14px !important;
        color: #4A3FD9 !important;
        background: #F4F1FF !important;
        border: none !important;
        border-radius: 8px !important;
        transition: all 0.25s ease !important;
        width: auto !important;
        min-width: 120px !important;
        max-width: 180px !important;
        height: 36px !important;
        white-space: nowrap;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
    }

    div[data-testid="column"] > div > div > div > button:hover {
        background: #E9E4FF !important;
        transform: translateY(-1px);
        box-shadow: 0px 3px 8px rgba(80, 60, 180, 0.12) !important;
    }

    /* Responsive adjustments */
    @media screen and (max-width: 1024px) {
        .customNavbar {
            padding: 10px 20px;
        }
        
        div[data-testid="column"] > div > div > div > button {
            font-size: 0.85rem !important;
            padding: 5px 12px !important;
            min-width: 100px !important;
        }
    }
        
        div[data-testid="column"] > div > div > div > button {
            font-size: 0.8rem !important;
            padding: 5px 10px !important;
            min-width: 90px !important;
        }
        
        .navButtonContainer {
            gap: 8px;
        }
    }

    @media screen and (max-width: 480px) {
        .customNavbar {
            padding: 8px 12px;
            min-height: 52px;
            max-height: 52px;
        }
        
        .navBrand {
            font-size: 1.1rem;
        }
        
        div[data-testid="column"] > div > div > div > button {
            font-size: 0.75rem !important;
            padding: 4px 8px !important;
            min-width: 70px !important;
            height: 32px !important;
        }
        
        .navButtonContainer {
            gap: 6px;
        }
        
        .block-container {
            padding-top: 5rem !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)

    # Navbar structure with fixed layout
    col_left, col_spacer, col_right = st.columns([5, 3, 2])
    
    with col_left:
        st.markdown('<div class="navBrand">AI Race Engineer</div>', unsafe_allow_html=True)
    
    with col_spacer:
        st.empty()  # Spacer
    
    with col_right:
        st.markdown('<div class="navButtonContainer">', unsafe_allow_html=True)
        btn_col1, btn_col2 = st.columns(2)
        
        with btn_col1:
            if st.button("Home", key="nav_home"):
                st.switch_page("pages/1_Home.py")
        
        with btn_col2:
            if st.button("Drivers", key="nav_driver"):
                st.switch_page("pages/2_Driver_Comparison.py")
        
        st.markdown('</div>', unsafe_allow_html=True)