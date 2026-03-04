import streamlit as st
import requests
import hashlib
import time
import uuid
import folium
import os
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

# --- 2. SIA BRANDED UI ---
SIA_NAVY = "#00266B"
SIA_GOLD = "#BD9B60"

st.markdown(f"""
    <style>
    .stApp {{ background-color: white; color: {SIA_NAVY}; }}
    [data-testid="stSidebar"] {{ background-color: {SIA_NAVY} !important; color: white !important; }}
    [data-testid="stSidebar"] label, [data-testid="stSidebar"] .stMarkdown p {{ color: {SIA_GOLD} !important; font-weight: bold !important; }}
    
    /* Search Card Design */
    .search-card {{
        background-color: white; padding: 30px; border-radius: 4px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1); border-top: 4px solid {SIA_GOLD};
        margin-bottom: 20px; color: {SIA_NAVY};
    }}
    
    /* SIA Primary Button */
    .stButton>button {{ 
        background-color: {SIA_NAVY} !important; color: white !important; 
        border-radius: 4px; font-weight: bold; width: 100%; border: none; height: 45px;
    }}
    
    /* Google Login Button */
    .google-btn {{
        display: block; text-align: center; background-color: #FFF; 
        color: {SIA_NAVY} !important; padding: 12px; border-radius: 4px; 
        text-decoration: none !important; font-weight: bold;
        border: 2px solid {SIA_NAVY}; margin-bottom: 20px;
    }}
    
    /* Custom SVG Logo Container */
    .sidebar-logo {{
        display: flex; justify-content: center; padding: 20px 0;
    }}
    .sidebar-logo svg {{ width: 200px; height: auto; }}
    </style>
    """, unsafe_allow_html=True)

# --- 3. DATA & UTILS ---
AIRPORTS = {
    "Singapore (SIN)": "SIN", "London (LHR)": "LHR", "Sydney (SYD)": "SYD", 
    "Tokyo (NRT)": "NRT", "Los Angeles (LAX)": "LAX", "Hong Kong (HKG)": "HKG"
}

def get_enhanced_fleet():
    url = "https://opensky-network.org/api/states/all"
    auth = (st.secrets["OPENSKY_CLIENT_ID"], st.secrets["OPENSKY_CLIENT_SECRET"])
    try:
        r = requests.get(url, auth=auth, timeout=10)
        states = r.json().get("states", [])
        return [s for s in states if s[1] and s[1].strip().startswith("SIA")]
    except: return []

# --- 4. SIDEBAR & LOGO ---
# Logic to display SVG logo in sidebar
logo_path = "singapore-airlines.svg"
if os.path.exists(logo_path):
    with open(logo_path, "r") as f:
        svg_content = f.read()
    st.sidebar.markdown(f'<div class="sidebar-logo">{svg_content}</div>', unsafe_allow_html=True)
else:
    st.sidebar.title("Singapore Airlines")

if "user" not in st.session_state:
    st.title("KrisTracker Executive Access")
    t_login, t_signup = st.tabs(["EXISTING MEMBER LOGIN", "CREATE NEW ACCOUNT"])
    
    with t_login:
        st.markdown('<div class="search-card">', unsafe_allow_html=True)
        # OAuth Setup
        res = supabase.auth.sign_in_with_oauth({
            "provider": "google",
            "options": {
                "redirect_to": "https://kristracker.streamlit.app/",
                "query_params": {"prompt": "select_account"}
            }
        })
        st.markdown(f'<a href="{res.url}" target="_self" class="google-btn">🏨 Continue with Google</a>', unsafe_allow_html=True)
        
        em = st.text_input("Email", key="login_email")
        pw = st.text_input("Password", type="password", key="login_pass")
        if st.button("LOGIN TO PORTAL"):
            try:
                resp = supabase.auth.sign_in_with_password({"email": em, "password": pw})
                st.session_state["user"] = resp.user
                st.rerun()
            except: st.error("Login failed. Please check credentials.")
        st.markdown('</div>', unsafe_allow_html=True)

    with t_signup:
        st.markdown('<div class="search-card">', unsafe_allow_html=True)
        st.subheader("New Membership")
        new_em = st.text_input("Enter Email", key="reg_email")
        new_pw = st.text_input("Create Password", type="password", key="reg_pass")
        if st.button("REGISTER NOW"):
            try:
                supabase.auth.sign_up({"email": new_em, "password": new_pw})
                st.success("Registration initiated! Check your inbox for a confirmation link.")
            except Exception as e: st.error(f"Error: {e}")
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# --- 5. LOGGED IN DASHBOARD ---
user = st.session_state["user"]
st.sidebar.success(f"Welcome, {user.email}")
if st.sidebar.button("Logout"):
    supabase.auth.sign_out()
    del st.session_state["user"]
    st.rerun()

st.title("Flight status")
t_route, t_number, t_radar = st.tabs(["ROUTE", "FLIGHT NUMBER", "LIVE RADAR"])

with t_route:
    st.markdown('<div class="search-card">', unsafe_allow_html=True)
    r1, r2, r3 = st.columns([2, 2, 1])
    origin = r1.selectbox("From", list(AIRPORTS.keys()))
    dest = r2.selectbox("To", list(AIRPORTS.keys()))
    if r3.button("SEARCH ROUTE"):
        st.info(f"Checking routes from {AIRPORTS[origin]} to {AIRPORTS[dest]}...")
    st.markdown('</div>', unsafe_allow_html=True)

with t_number:
    st.markdown('<div class="search-card">', unsafe_allow_html=True)
    n1, n2, n3 = st.columns([2, 2, 1])
    f_num = n1.text_input("Flight Number", value="SQ638").upper()
    d_date = n2.date_input("Departure Date")
    if n3.button("TRACK STATUS"):
        st.info(f"Connecting to SIA Gateway for flight {f_num}...")
    st.markdown('</div>', unsafe_allow_html=True)

with t_radar:
    st.write("Live SIA Fleet Positions (Altitude & Speed in Popup)")
    if st.button("Refresh Global Fleet"):
        fleet = get_enhanced_fleet()
        m = folium.Map(location=[1.35, 103.98], zoom_start=3, tiles='CartoDB dark_matter')
        for p in fleet:
            alt = f"{int(p[7])}m" if p[7] else "N/A"
            spd = f"{int(p[9] * 3.6)}km/h" if p[9] else "N/A"
            folium.Marker(
                [p[6], p[5]], 
                popup=f"<b>SQ {p[1].strip()}</b><br>Alt: {alt}<br>Speed: {spd}", 
                icon=folium.Icon(color='orange', icon='plane')
            ).add_to(m)
        st_folium(m, width="100%", height=550)
