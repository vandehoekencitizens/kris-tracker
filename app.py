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

# Session Recovery logic
if "user" not in st.session_state:
    try:
        res = supabase.auth.get_session()
        if res and res.session:
            st.session_state["user"] = res.session.user
    except: pass

# --- 2. BRANDED UI (SIA Official) ---
SIA_NAVY, SIA_GOLD = "#00266B", "#BD9B60"

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

# --- 3. AVIATION CALCULATIONS ---
def get_mach(gs_mps, alt_m):
    if not gs_mps or not alt_m: return 0.0
    temp_k = 288.15 - (0.0065 * alt_m) # ISA Standard Lapse
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

# --- 4. SIDEBAR & LOGO ---
logo_path = "singapore-airlines.svg"
if os.path.exists(logo_path):
    with open(logo_path, "r") as f:
        st.sidebar.markdown(f'<div class="sidebar-logo">{f.read()}</div>', unsafe_allow_html=True)

if "user" not in st.session_state:
    st.title("KrisTracker Executive Portal")
    t1, t2 = st.tabs(["LOGIN", "CREATE ACCOUNT"])
    
    with t1:
        st.markdown('<div class="search-card">', unsafe_allow_html=True)
        # OAuth Link
        oauth_res = supabase.auth.sign_in_with_oauth({
            "provider": "google", 
            "options": {"redirect_to": "https://kristracker.streamlit.app/", "query_params": {"prompt": "select_account"}}
        })
        st.markdown(f'<a href="{oauth_res.url}" target="_self" class="google-btn">🏨 Continue with Google</a>', unsafe_allow_html=True)
        
        em = st.text_input("Email", key="l_em")
        pw = st.text_input("Password", type="password", key="l_pw")
        if st.button("SIGN IN"):
            try:
                resp = supabase.auth.sign_in_with_password({"email": em, "password": pw})
                st.session_state["user"] = resp.user
                st.rerun()
            except Exception as e:
                st.error("Login failed. Ensure your email is confirmed in Supabase or that 'Confirm Email' is disabled in Auth settings.")
        st.markdown('</div>', unsafe_allow_html=True)

    with t2:
        st.markdown('<div class="search-card">', unsafe_allow_html=True)
        new_em = st.text_input("Email Address", key="s_em")
        new_pw = st.text_input("Create Password", type="password", key="s_pw")
        if st.button("REGISTER"):
            try:
                supabase.auth.sign_up({"email": new_em, "password": new_pw})
                st.success("✅ Registration sent! Check your inbox.")
                st.info("Note: If no email arrives, Supabase might be at its 3-per-hour limit.")
            except Exception as e: st.error(f"Error: {e}")
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# --- 5. LOGGED IN DASHBOARD ---
user = st.session_state["user"]
st.sidebar.write(f"Logged in: **{user.email}**")
if st.sidebar.button("Logout"):
    supabase.auth.sign_out(); del st.session_state["user"]; st.rerun()

st.title("Flight Operations Dashboard")
tab_status, tab_radar = st.tabs(["FLIGHT STATUS", "LIVE NETWORK RADAR"])

with tab_radar:
    if st.button("Sync Global Fleet"):
        fleet = get_enhanced_fleet()
        m = folium.Map(location=[1.35, 103.98], zoom_start=3, tiles='CartoDB dark_matter')
        for p in fleet:
            # Conv: meters -> ft, m/s -> kts
            alt_ft = int(p[7] * 3.28084) if p[7] else 0
            gs_kts = int(p[9] * 1.94384) if p[9] else 0
            mach = get_mach(p[9], p[7])
            icao24 = p[0].upper() # Unique registration proxy
            
            popup_html = f"""
            <div style="font-family: sans-serif; min-width: 160px;">
                <b style="color:{SIA_NAVY}; font-size: 14px;">SQ {p[1].strip()}</b><br>
                <span style="color:#666;">Reg ID (ICAO): {icao24}</span><hr>
                <b>ALT:</b> {alt_ft:,} ft MSL<br>
                <b>GS:</b> {gs_kts} kts<br>
                <b>MACH:</b> {mach:.2f}
            </div>
            """
            folium.Marker([p[6], p[5]], popup=popup_html, icon=folium.Icon(color='orange', icon='plane')).add_to(m)
        st_folium(m, width="100%", height=600)

with tab_status:
    st.info("SIA Flight Search Interface Ready. Enter your API key in secrets to enable live tracking.")
