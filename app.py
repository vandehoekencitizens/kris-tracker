import streamlit as st
import requests
import hashlib
import time
import uuid
import folium
import os
import math
import pandas as pd
from streamlit_folium import st_folium
from supabase import create_client

# --- 1. INITIALIZATION ---
st.set_page_config(page_title="Singapore Airlines | KrisTracker", page_icon="✈️", layout="wide")

@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

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
        margin-bottom: 20px; color: {SIA_NAVY};
    }}
    .stButton>button {{ 
        background-color: {SIA_NAVY} !important; color: white !important; 
        font-weight: bold; border-radius: 4px; border: none; height: 45px; width: 100%;
    }}
    .sidebar-logo {{ display: flex; justify-content: center; padding: 20px 0; }}
    .sidebar-logo svg {{ width: 200px; height: auto; fill: white; }}
    </style>
    """, unsafe_allow_html=True)

# --- 3. AVIATION & API LOGIC ---
def get_mach(gs_mps, alt_m):
    if not gs_mps or gs_mps < 1 or not alt_m: return 0.0
    temp_k = 288.15 - (0.0065 * alt_m) # ISA Lapse
    speed_of_sound = 20.046 * math.sqrt(temp_k)
    return gs_mps / speed_of_sound

@st.cache_data(ttl=120)
def get_fleet_cached():
    url = "https://opensky-network.org/api/states/all"
    auth = (st.secrets["OPENSKY_CLIENT_ID"], st.secrets["OPENSKY_CLIENT_SECRET"])
    try:
        r = requests.get(url, auth=auth, timeout=12)
        states = r.json().get("states", [])
        return [s for s in states if s[1] and s[1].strip().startswith("SIA")]
    except: return []

def call_sia_api(endpoint, payload):
    # CRITICAL: Using your specific Secret name SIA_STATUS_KEY
    url = f"https://apigw.singaporeair.com/api/v1/flightstatus/{endpoint}"
    headers = {
        "Content-Type": "application/json",
        "api_key": st.secrets["SIA_STATUS_KEY"],
        "x-csl-client-uuid": str(uuid.uuid4())
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=15)
        return res.json()
    except Exception as e:
        return {"status": "FAILURE", "message": str(e)}

# --- 4. AUTH & SIDEBAR ---
logo_path = "singapore-airlines.svg"
if os.path.exists(logo_path):
    with open(logo_path, "r") as f:
        st.sidebar.markdown(f'<div class="sidebar-logo">{f.read()}</div>', unsafe_allow_html=True)

if "user" not in st.session_state:
    st.title("KrisTracker Executive Portal")
    t1, t2 = st.tabs(["LOGIN", "CREATE ACCOUNT"])
    with t1:
        st.markdown('<div class="search-card">', unsafe_allow_html=True)
        em = st.text_input("Email", key="l_em")
        pw = st.text_input("Password", type="password", key="l_pw")
        if st.button("SIGN IN"):
            try:
                # FIX: Strip and lower to prevent credential mismatch
                resp = supabase.auth.sign_in_with_password({"email": em.lower().strip(), "password": pw})
                st.session_state["user"] = resp.user
                st.rerun()
            except: st.error("Credential Error. Check your password or re-register.")
        st.markdown('</div>', unsafe_allow_html=True)
    with t2:
        st.markdown('<div class="search-card">', unsafe_allow_html=True)
        new_em = st.text_input("Email", key="s_em")
        new_pw = st.text_input("Password", type="password", key="s_pw")
        if st.button("REGISTER"):
            supabase.auth.sign_up({"email": new_em, "password": new_pw})
            st.success("Account created! Login to continue.")
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# --- 5. LOGGED IN DASHBOARD ---
user = st.session_state["user"]
st.sidebar.write(f"Logged in: **{user.email}**")
if st.sidebar.button("Logout"):
    supabase.auth.sign_out(); del st.session_state["user"]; st.rerun()

st.title("Flight Operations Dashboard")
tab_radar, tab_route, tab_flight = st.tabs(["📡 LIVE RADAR", "✈️ BY ROUTE", "🔎 BY FLIGHT NUMBER"])

with tab_radar:
    col_map, col_stats = st.columns([3, 1])
    with st.spinner("Fetching Satellite Data..."):
        fleet_data = get_fleet_cached()
    
    processed_fleet = []
    for p in fleet_data:
        alt_ft = int(p[7] * 3.28084) if p[7] else 0
        gs_kts = int(p[9] * 1.94384) if p[9] else 0
        mach = get_mach(p[9], p[7])
        processed_fleet.append({
            "Callsign": p[1].strip(), "Reg (ICAO)": p[0].upper(), 
            "Alt (ft)": alt_ft, "GS (kts)": gs_kts, "Mach": round(mach, 2),
            "Lat": p[6], "Lon": p[5]
        })

    with col_map:
        m = folium.Map(location=[1.35, 103.98], zoom_start=3, tiles='CartoDB dark_matter')
        for ac in processed_fleet:
            popup_html = f"<b>SQ {ac['Callsign']}</b><br>Alt: {ac['Alt (ft)']:,} ft<br>GS: {ac['GS (kts)']} kts<br>Mach: {ac['Mach']}"
            folium.Marker([ac['Lat'], ac['Lon']], popup=popup_html, icon=folium.Icon(color='orange', icon='plane')).add_to(m)
        st_folium(m, width="100%", height=500, key="radar_v2")
    
    with col_stats:
        st.metric("SIA Airborne", len(processed_fleet))
        if processed_fleet:
            df = pd.DataFrame(processed_fleet).drop(['Lat', 'Lon'], axis=1)
            st.dataframe(df, hide_index=True)

with tab_route:
    st.markdown('<div class="search-card">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    orig = c1.text_input("Origin", "SIN").upper()
    dest = c2.text_input("Destination", "LHR").upper()
    r_date = c3.date_input("Date")
    if st.button("SEARCH ROUTE"):
        res = call_sia_api("getbyroute", {
            "originAirportCode": orig, "destinationAirportCode": dest, "scheduledDepartureDate": str(r_date)
        })
        if res and res.get("status") == "SUCCESS":
            flights = res.get("data", {}).get("response", {}).get("flights", [])
            for f in flights:
                for leg in f.get("legs", []):
                    st.write(f"**SQ {leg['flightNumber']}** | Status: `{leg['flightStatus']}`")
                    st.caption(f"Dep: {leg['scheduledDepartureTime']} | Arr: {leg['scheduledArrivalTime']}")
        else: st.error("No flights found or API key mismatch.")
    st.markdown('</div>', unsafe_allow_html=True)
