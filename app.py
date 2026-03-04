import streamlit as st
import requests
import hashlib
import time
import uuid
import folium
import os
import math
from streamlit_folium import st_folium
from supabase import create_client

# --- 1. INITIALIZATION ---
st.set_page_config(page_title="Singapore Airlines | KrisTracker", page_icon="✈️", layout="wide")

@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# Session Recovery
if "user" not in st.session_state:
    try:
        res = supabase.auth.get_session()
        if res and res.session:
            st.session_state["user"] = res.session.user
    except: pass

# --- 2. BRANDED UI & SVG LOGO ---
SIA_NAVY = "#00266B"
SIA_GOLD = "#BD9B60"

st.markdown(f"""
    <style>
    .stApp {{ background-color: white; color: {SIA_NAVY}; }}
    [data-testid="stSidebar"] {{ background-color: {SIA_NAVY} !important; }}
    [data-testid="stSidebar"] * {{ color: white !important; }}
    .search-card {{
        background-color: white; padding: 30px; border-radius: 4px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1); border-top: 4px solid {SIA_GOLD};
        margin-bottom: 20px;
    }}
    .stButton>button {{ 
        background-color: {SIA_NAVY} !important; color: white !important; 
        font-weight: bold; border-radius: 4px; border: none; height: 45px;
    }}
    .google-btn {{
        display: block; text-align: center; background-color: #FFF; 
        color: {SIA_NAVY} !important; padding: 12px; border-radius: 4px; 
        text-decoration: none !important; font-weight: bold;
        border: 2px solid {SIA_NAVY}; margin-bottom: 20px;
    }}
    .sidebar-logo {{ display: flex; justify-content: center; padding: 20px 0; }}
    .sidebar-logo svg {{ width: 200px; height: auto; }}
    </style>
    """, unsafe_allow_html=True)

# --- 3. DATA CONVERSIONS & LOGIC ---
def get_mach(gs_mps, alt_m):
    """Calculates approximate Mach number based on speed and altitude."""
    if not gs_mps or not alt_m: return 0.0
    # Standard Speed of Sound Approximation: a = a0 * sqrt(T/T0)
    temp_k = 288.15 - (0.0065 * alt_m) # Simple ISA Lapse Rate
    speed_of_sound = 20.046 * math.sqrt(temp_k)
    return gs_mps / speed_of_sound

def get_enhanced_fleet():
    url = "https://opensky-network.org/api/states/all"
    auth = (st.secrets["OPENSKY_CLIENT_ID"], st.secrets["OPENSKY_CLIENT_SECRET"])
    try:
        r = requests.get(url, auth=auth, timeout=10)
        states = r.json().get("states", [])
        return [s for s in states if s[1] and s[1].strip().startswith("SIA")]
    except: return []

# --- 4. SIDEBAR & AUTH ---
logo_path = "singapore-airlines.svg"
if os.path.exists(logo_path):
    with open(logo_path, "r") as f:
        st.sidebar.markdown(f'<div class="sidebar-logo">{f.read()}</div>', unsafe_allow_html=True)

if "user" not in st.session_state:
    st.title("KrisTracker Executive Access")
    t1, t2 = st.tabs(["LOGIN", "CREATE ACCOUNT"])
    with t1:
        st.markdown('<div class="search-card">', unsafe_allow_html=True)
        res = supabase.auth.sign_in_with_oauth({
            "provider": "google", "options": {"redirect_to": "https://kristracker.streamlit.app/", "query_params": {"prompt": "select_account"}}
        })
        st.markdown(f'<a href="{res.url}" target="_self" class="google-btn">🏨 Continue with Google</a>', unsafe_allow_html=True)
        em = st.text_input("Email", key="l_em")
        pw = st.text_input("Password", type="password", key="l_pw")
        if st.button("SIGN IN"):
            resp = supabase.auth.sign_in_with_password({"email": em, "password": pw})
            st.session_state["user"] = resp.user
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    with t2:
        st.markdown('<div class="search-card">', unsafe_allow_html=True)
        new_em = st.text_input("Email Address", key="s_em")
        new_pw = st.text_input("Password", type="password", key="s_pw")
        if st.button("REGISTER"):
            supabase.auth.sign_up({"email": new_em, "password": new_pw})
            st.success("Confirmation sent! If you don't receive it, see the note below.")
        st.warning("⚠️ **Note:** Supabase Free Tier limits emails to 3 per hour. If you signed up once, wait 60 mins for the next attempt.")
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# --- 5. DASHBOARD ---
user = st.session_state["user"]
st.sidebar.write(f"Logged in: {user.email}")
if st.sidebar.button("Logout"):
    supabase.auth.sign_out()
    del st.session_state["user"]
    st.rerun()

st.title("Flight Operations Dashboard")
tab_status, tab_radar = st.tabs(["FLIGHT STATUS", "LIVE NETWORK RADAR"])

with tab_radar:
    if st.button("Sync Global Fleet"):
        fleet = get_enhanced_fleet()
        m = folium.Map(location=[1.35, 103.98], zoom_start=3, tiles='CartoDB dark_matter')
        for p in fleet:
            # Conversion Logic
            alt_ft = int(p[7] * 3.28084) if p[7] else 0
            gs_kts = int(p[9] * 1.94384) if p[9] else 0
            mach = get_mach(p[9], p[7])
            icao24 = p[0].upper()
            
            popup_html = f"""
            <div style="font-family: Arial; min-width: 150px;">
                <b style="color:{SIA_NAVY};">SQ {p[1].strip()}</b><br>
                <small>Reg (ICAO24): {icao24}</small><hr>
                <b>Alt:</b> {alt_ft:,} ft MSL<br>
                <b>Speed:</b> {gs_kts} kts<br>
                <b>Mach:</b> {mach:.2f}
            </div>
            """
            folium.Marker(
                [p[6], p[5]], popup=popup_html, icon=folium.Icon(color='orange', icon='plane')
            ).add_to(m)
        st_folium(m, width="100%", height=600)
