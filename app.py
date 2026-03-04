import streamlit as st
import requests
import hashlib
import time
import uuid
import folium
from streamlit_folium import st_folium
from supabase import create_client

# --- 1. INITIALIZATION & SESSION RECOVERY ---
st.set_page_config(page_title="Singapore Airlines | KrisTracker", page_icon="✈️", layout="wide")

@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

if "user" not in st.session_state:
    try:
        res = supabase.auth.get_session()
        if res and res.session:
            st.session_state["user"] = res.session.user
    except:
        pass

# --- 2. SIA OFFICIAL THEME UI (CLEAN WHITE & NAVY) ---
SIA_NAVY = "#00266B"      # Official SIA Navy
SIA_GOLD = "#BD9B60"      # Official SIA Gold
SIA_LIGHT_GRAY = "#F4F4F4" # Background gray

st.markdown(f"""
    <style>
    /* Global Background */
    .stApp {{ background-color: white; color: {SIA_NAVY}; }}
    
    /* Sidebar Styling - Dark for Branding */
    [data-testid="stSidebar"] {{ 
        background-color: {SIA_NAVY} !important; 
        color: white !important;
    }}
    
    /* Force Sidebar text to Gold/White */
    [data-testid="stSidebar"] label, [data-testid="stSidebar"] .stMarkdown p {{
        color: {SIA_GOLD} !important;
        font-weight: bold !important;
    }}

    /* Input Boxes - SIA Style */
    input {{ 
        background-color: white !important; 
        color: black !important; 
        border: 1px solid #CCC !important;
        border-radius: 2px !important;
        padding: 10px !important;
    }}
    
    /* Main Search Card */
    .search-card {{
        background-color: white;
        padding: 30px;
        border-radius: 4px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        border-top: 4px solid {SIA_GOLD};
        margin-bottom: 20px;
    }}
    
    /* Primary Action Buttons */
    .stButton>button {{ 
        background-color: {SIA_NAVY} !important; 
        color: white !important; 
        border-radius: 4px; 
        border: none;
        padding: 12px 24px;
        font-weight: bold;
        text-transform: uppercase;
    }}
    
    /* Google Button - High Contrast */
    .google-btn {{
        display: block; text-align: center; background-color: #FFF; 
        color: {SIA_NAVY} !important; padding: 12px; border-radius: 4px; 
        text-decoration: none !important; font-weight: bold;
        margin: 20px 0; border: 2px solid {SIA_NAVY};
    }}
    
    /* Tabs styling to match screenshot */
    .stTabs [data-baseweb="tab-list"] {{ gap: 2px; }}
    .stTabs [data-baseweb="tab"] {{ 
        background-color: {SIA_LIGHT_GRAY};
        padding: 10px 20px;
        color: #666 !important;
    }}
    .stTabs [aria-selected="true"] {{ 
        background-color: white !important;
        border-top: 3px solid {SIA_GOLD} !important;
        color: {SIA_NAVY} !important;
        font-weight: bold;
    }}
    </style>
    """, unsafe_allow_html=True)

# --- 3. SIDEBAR AUTH ---
# Your logo should stay white/gold in the Navy sidebar
try:
    st.sidebar.image("singapore-airlines-1-logo-png-transparent.png", width=220)
except:
    st.sidebar.title("Singapore Airlines")

if "user" not in st.session_state:
    st.sidebar.subheader("Member Access")
    
    # PROMPT FIX for 403: Forces Google to let you pick an account
    # IMPORTANT: Update your-app-name.streamlit.app to your actual URL
    res = supabase.auth.sign_in_with_oauth({
        "provider": "google",
        "options": {
            "redirect_to": "https://your-app-name.streamlit.app/",
            "query_params": {"prompt": "select_account"}
        }
    })
    
    st.sidebar.markdown(f'<a href="{res.url}" target="_self" class="google-btn">🏨 Sign in with Google</a>', unsafe_allow_html=True)
    
    st.sidebar.write("--- OR ---")
    email = st.sidebar.text_input("Email")
    pw = st.sidebar.text_input("Password", type="password")
    
    if st.sidebar.button("Login"):
        try:
            resp = supabase.auth.sign_in_with_password({"email": email, "password": pw})
            st.session_state["user"] = resp.user
            st.rerun()
        except:
            st.sidebar.error("Invalid credentials.")
    st.stop()
else:
    user = st.session_state["user"]
    st.sidebar.success(f"Welcome, {user.email}")
    if st.sidebar.button("Logout"):
        supabase.auth.sign_out()
        del st.session_state["user"]
        st.rerun()

# --- 4. MAIN CONTENT (SIA DESIGN) ---
st.title("Flight status")
st.caption("Flight status information will only be available 48 hours before flight departure or arrival.")

# Layout Tabs
t1, t2 = st.tabs(["ROUTE", "FLIGHT NUMBER"])

with t2:
    st.markdown('<div class="search-card">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        f_num = st.text_input("Flight Number", value="SQ638").upper()
    with col2:
        d_date = st.date_input("Departure Date")
    with col3:
        st.write(" ") # Padding
        track_btn = st.button("SEARCH")
    st.markdown('</div>', unsafe_allow_html=True)

    if track_btn:
        with st.spinner("Loading..."):
            # Insert your existing get_sia_headers() logic and API call here
            st.info(f"Searching for {f_num} on {d_date}...")

with t1:
    st.info("Route search coming soon to match the SIA interface.")
