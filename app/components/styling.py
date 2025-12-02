import streamlit as st

def apply_custom_theme():
   st.markdown("""
<style>

@import url('https://fonts.googleapis.com/css2?family=Tektur:wght@400..900&family=Playfair:ital,opsz,wght@0,5..1200,300..900;1,5..1200,300..900&display=swap');

html, body, [class*="block-container"] {
    background-color: #191919 !important;
    color: #FFFFFF !important;
    font-optical-sizing: auto;
}
               
header[data-testid="stHeader"] {
        visibility: hidden !important;
        height: 0px !important;
    }
               
[data-testid="stSidebar"] {
        display: none !important;
    }
               
/* ------------------------------------
       SOFT PAGE TRANSITION ANIMATION
    ------------------------------------ */
    
    @keyframes fadeInAnimation {
        0% {
            opacity: 0;
            transform: translateY(10px); /* Optional: Leicht von unten einschweben */
        }
        100% {
            opacity: 1;
            transform: translateY(0);
        }
    }

    .stApp > header + div {
        animation-name: fadeInAnimation;
        animation-duration: 0.5s;  /* Dauer: 0.5 Sekunden */
        animation-timing-function: ease-in-out;
        animation-fill-mode: both;
    }
    
    div.block-container {
        animation: fadeInAnimation 0.5s ease-in-out;
    }

               
/* ------------------------------------
   SECTION TITLES
------------------------------------ */
.section-title {
    font-size: 1.6rem;
    font-weight: 700;
    font-family: 'Tektur', sans-serif !important;
    font-optical-sizing: auto;
    font-variation-settings: "wdth" 100;
    margin-top: 1.2rem;
}

.main-content h1,
.main-content h2,
.main-content h3,
.main-content h4,
.main-content h5,
.main-content h6 {
    font-family: 'Tektur', sans-serif !important;
    font-optical-sizing: auto !important;
    font-variation-settings: "wdth" 100 !important;
    font-weight: 700 !important;
}

/* ------------------------------------
   TABLE STYLING
   (Note: The wrapper is now handled by GlowCard classes, 
    we only style the inner table here)
------------------------------------ */

/* Ensure the table scrolls if too wide */
.table-responsive {
    overflow-x: auto;
    width: 100%;
}

table {
    width: 100%;
    min-width: 400px;
    border-collapse: collapse;
}

table th {
    background: #161616 !important;
    color: #FFFFFF !important;
    font-weight: 700 !important;
    border-bottom: 2px solid #7d0e0e !important;
    text-align: left !important;
    padding: 10px 8px !important;
    font-family: 'Tektur', sans-serif !important;
}

table td {
    background: #141414 !important;
    padding: 8px 8px !important;
    border-bottom: 1px solid #222 !important;
    font-family: 'Playfair', serif !important;
}

table tr:hover td {
    background: #1E1E1E !important;
}

/* ------------------------------------
   MISC
------------------------------------ */
.center {
    display: flex;
    justify-content: center;
}

.stButton > button {
    background-color: #7d0e0e !important;
    color: #FFFFFF !important;
    border: none !important;
    padding: 10px 24px !important;
    font-weight: 600 !important;
    transition: all 0.3s ease !important;
}

.stButton > button:hover {
    background-color: #8e1f1f !important;
    box-shadow: 0px 0px 15px rgba(211, 0, 0, 0.4) !important;
}

</style>
""", unsafe_allow_html=True)
