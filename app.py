import streamlit as st
import requests
import uuid
import folium
import os
import math
import pandas as pd
from streamlit_folium import st_folium
from supabase import create_client

# --- 1. INITIALIZATION ---
st.set_page_config(page_title="KrisTracker | SIA Command", page_icon="✈️", layout="wide")

@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- 2. EXECUTIVE THEME & LOGO (PERSISTENT) ---
SIA_NAVY, SIA_GOLD = "#00266B", "#BD9B60"
st.markdown(f"""
    <style>
    .stApp {{ background-color: white; color: {SIA_NAVY}; }}
    [data-testid="stSidebar"] {{ background-color: {SIA_NAVY} !important; }}
    [data-testid="stSidebar"] * {{ color: white !important; }}
    .search-card {{
        background-color: white; padding: 25px; border-radius: 4px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1); border-top: 4px solid {SIA_GOLD};
        margin-bottom: 20px; color: {SIA_NAVY};
    }}
    .stButton>button {{ 
        background-color: {SIA_NAVY} !important; color: white !important; 
        font-weight: bold; border-radius: 4px; height: 45px; width: 100%;
    }}
    .sidebar-logo {{ display: flex; justify-content: center; padding: 20px 0; }}
    .sidebar-logo svg {{ width: 200px; height: auto; fill: white; }}
    </style>
    """, unsafe_allow_html=True)

# --- 3. OP-CENTER & DEBUG (PERSISTENT) ---
st.sidebar.title("🛠 OP-CENTER")
debug_mode = st.sidebar.toggle("Enable Debug Mode", value=True)

def log_debug(title, content):
    if debug_mode:
        with st.sidebar.expander(f"DEBUG: {title}", expanded=False):
            st.code(content)

# --- 4. OPENSKY OAUTH2 LOGIC (NEW FOR 2026) ---
def get_opensky_token():
    """Retrieves OAuth2 token for OpenSky accounts created after March 2025."""
    auth_url = "https://opensky-network.org/auth/realms/opensky/protocol/openid-connect/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": st.secrets["OPENSKY_CLIENT_ID"],
        "client_secret": st.secrets["OPENSKY_CLIENT_SECRET"]
    }
    try:
        r = requests.post(auth_url, data=data, timeout=10)
        return r.json().get("access_token")
    except:
        return None

# --- 5. AVIATION LOGIC (RESTORED UNITS & MACH) ---
def get_mach(gs_mps, alt_m):
    if not gs_mps or gs_mps < 1 or not alt_m: return 0.0
    temp_k = 288.15 - (0.0065 * alt_m)
    return gs_mps / (20.046 * math.sqrt(temp_k))

@st.cache_data(ttl=60)
def get_fleet_cached():
    token = get_opensky_token()
    url = "https://opensky-network.org/api/states/all"
    
    # Header-based Auth (2026 Standard)
    headers = {"Authorization": f"Bearer {token}"} if token else None
    
    try:
        r = requests.get(url, headers=headers, timeout=12)
        log_debug("OpenSky Status", f"Code: {r.status_code}")
        
        states = r.json().get("states", [])
        sia_flights = []
        for s in (states or []):
            callsign = str(s[1]).strip() if s[1] else ""
            if callsign.startswith("SIA") or callsign.startswith("SQ"):
                alt_m = s[7] if s[7] else 0
                gs_mps = s[9] if s[9] else 0
                sia_flights.append({
                    "Callsign": callsign,
                    "Registration": s[0].upper(),
                    "Lat": s[6], "Lon": s[5],
                    "Alt (ft)": int(alt_m * 3.28084),
                    "GS (kts)": int(gs_mps * 1.94384),
                    "Mach": round(get_mach(gs_mps, alt_m), 2)
                })
        return sia_flights
    except Exception as e:
        log_debug("OpenSky Error", str(e))
        return []

# --- 6. SIA API (UAT vs PROD Switcher) ---
def call_sia_api(endpoint_path, payload):
    # Try the most common production-ready path first
    url = f"https://apigw.singaporeair.com/api/v1/flightstatus/{endpoint_path}"
    headers = {
        "Content-Type": "application/json",
        "api_key": st.secrets["SIA_STATUS_KEY"],
        "x-csl-client-uuid": str(uuid.uuid4())
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=15)
        return res.json()
    except:
        return {"status": "FAILURE", "message": "API Connection Error"}

# --- 7. AUTH & SIDEBAR ---
logo_path = "singapore-airlines.svg"
if os.path.exists(logo_path):
    with open(logo_path, "r") as f:
        st.sidebar.markdown(f'<div class="sidebar-logo">{f.read()}</div>', unsafe_allow_html=True)

if "user" not in st.session_state:
    st.title("KrisTracker Executive Portal")
    with st.container(border=True):
        em = st.text_input("Email")
        pw = st.text_input("Password", type="password")
        if st.button("SIGN IN"):
            try:
                resp = supabase.auth.sign_in_with_password({"email": em.lower().strip(), "password": pw})
                st.session_state["user"] = resp.user
                st.rerun()
            except: st.error("Login Error.")
    st.stop()

# --- 8. DASHBOARD (FULL FEATURE SET) ---
st.sidebar.write(f"Active User: **{st.session_state.user.email}**")
if st.sidebar.button("Logout"):
    supabase.auth.sign_out(); del st.session_state["user"]; st.rerun()

t_radar, t_route, t_flight = st.tabs(["📡 LIVE RADAR", "✈️ ROUTE SEARCH", "🔎 FLIGHT NUMBER"])

with t_radar:
    fleet = get_fleet_cached()
    col_map, col_list = st.columns([3, 1])
    with col_map:
        m = folium.Map(location=[1.35, 103.98], zoom_start=3, tiles='CartoDB dark_matter')
        for ac in fleet:
            if ac['Lat']:
                popup = f"<b>SQ {ac['Callsign']}</b><br>Reg: {ac['Registration']}<br>Alt: {ac['Alt (ft)']:,} ft<br>Mach: {ac['Mach']}"
                folium.Marker([ac['Lat'], ac['Lon']], popup=popup, icon=folium.Icon(color='orange', icon='plane')).add_to(m)
        st_folium(m, width="100%", height=500, key="radar_2026")
    with col_list:
        st.metric("SIA Global Fleet", len(fleet))
        if fleet:
            st.dataframe(pd.DataFrame(fleet).drop(['Lat', 'Lon'], axis=1), hide_index=True)
        else: st.warning("Satellite Link Delay. Use Debug Mode to check Token.")

with t_route:
    st.markdown('<div class="search-card">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    orig, dest = c1.text_input("Origin", "SIN"), c2.text_input("Destination", "LHR")
    date = c3.date_input("Date")
    if st.button("SEARCH BY ROUTE"):
        res = call_sia_api("getbyroute", {"originAirportCode": orig.upper(), "destinationAirportCode": dest.upper(), "scheduledDepartureDate": str(date)})
        st.write(res)
    st.markdown('</div>', unsafe_allow_html=True)

with t_flight:
    st.markdown('<div class="search-card">', unsafe_allow_html=True)
    f1, f2 = st.columns(2)
    f_no = f1.text_input("Flight Number", "308")
    f_date = f2.date_input("Date", key="f_date")
    if st.button("SEARCH BY FLIGHT NUMBER"):
        res = call_sia_api("get", {"flightNumber": f_no, "scheduledDepartureDate": str(f_date)})
        st.write(res)
    st.markdown('</div>', unsafe_allow_html=True)
