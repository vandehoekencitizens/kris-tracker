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
        margin-bottom: 20px; color: {SIA_NAVY};
    }}
    .stButton>button {{ 
        background-color: {SIA_NAVY} !important; color: white !important; 
        font-weight: bold; border-radius: 4px; border: none; height: 45px; width: 100%;
    }}
    .sidebar-logo {{ display: flex; justify-content: center; padding: 20px 0; }}
    .sidebar-logo svg {{ width: 200px; height: auto; }}
    </style>
    """, unsafe_allow_html=True)

# --- 3. AVIATION LOGIC ---
def get_mach(gs_mps, alt_m):
    if not gs_mps or gs_mps < 1 or not alt_m: return 0.0
    temp_k = 288.15 - (0.0065 * alt_m)
    speed_of_sound = 20.046 * math.sqrt(temp_k)
    return gs_mps / speed_of_sound

def get_enhanced_fleet():
    """Pulls live states from OpenSky for SIA fleet"""
    url = "https://opensky-network.org/api/states/all"
    auth = (st.secrets["OPENSKY_CLIENT_ID"], st.secrets["OPENSKY_CLIENT_SECRET"])
    try:
        # Use a timeout and verify the response
        r = requests.get(url, auth=auth, timeout=15)
        r.raise_for_status()
        states = r.json().get("states")
        if not states:
            return []
        # Filter for Singapore Airlines (SIA/SQ)
        return [s for s in states if s[1] and s[1].strip().startswith("SIA")]
    except Exception as e:
        st.error(f"Radar Link Interrupted: {e}")
        return []

def call_sia_api(endpoint, payload):
    url = f"https://apigw.singaporeair.com/api/v1/flightstatus/{endpoint}"
    headers = {
        "Content-Type": "application/json",
        "api_key": st.secrets["SIA_API_KEY"],
        "x-csl-client-uuid": str(uuid.uuid4())
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        return response.json()
    except Exception as e:
        return {"status": "FAILURE", "message": str(e)}

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
        res = supabase.auth.sign_in_with_oauth({"provider": "google", "options": {"redirect_to": "https://kristracker.streamlit.app/"}})
        st.markdown(f'<a href="{res.url}" target="_self" style="text-decoration:none; display:block; text-align:center; padding:10px; border:2px solid {SIA_NAVY}; border-radius:4px; margin-bottom:15px; color:{SIA_NAVY}; font-weight:bold;">🏨 Continue with Google</a>', unsafe_allow_html=True)
        em = st.text_input("Email", key="l_em")
        pw = st.text_input("Password", type="password", key="l_pw")
        if st.button("SIGN IN"):
            try:
                resp = supabase.auth.sign_in_with_password({"email": em, "password": pw})
                st.session_state["user"] = resp.user
                st.rerun()
            except: st.error("Login failed. Check credentials.")
        st.markdown('</div>', unsafe_allow_html=True)
    with t2:
        st.markdown('<div class="search-card">', unsafe_allow_html=True)
        new_em = st.text_input("Email", key="s_em")
        new_pw = st.text_input("Password", type="password", key="s_pw")
        if st.button("REGISTER"):
            supabase.auth.sign_up({"email": new_em, "password": new_pw})
            st.success("Account created! You can now log in.")
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# --- 5. DASHBOARD ---
user = st.session_state["user"]
st.sidebar.write(f"Logged in: **{user.email}**")
if st.sidebar.button("Logout"):
    supabase.auth.sign_out(); del st.session_state["user"]; st.rerun()

st.title("Flight Operations Dashboard")
tab_radar, tab_route, tab_flight = st.tabs(["📡 LIVE RADAR", "✈️ BY ROUTE", "🔎 BY FLIGHT NUMBER"])

with tab_radar:
    col_map, col_stats = st.columns([3, 1])
    
    with st.spinner("Synchronizing with Global Radar..."):
        fleet_data = get_enhanced_fleet()
    
    processed_fleet = []
    for p in fleet_data:
        # p[7] is Altitude (m), p[9] is Velocity (m/s)
        alt_m = p[7] if p[7] else 0
        gs_mps = p[9] if p[9] else 0
        
        alt_ft = int(alt_m * 3.28084)
        gs_kts = int(gs_mps * 1.94384)
        mach = get_mach(gs_mps, alt_m)
        
        processed_fleet.append({
            "Callsign": p[1].strip(), 
            "Reg (ICAO)": p[0].upper(), 
            "Alt (ft)": alt_ft, 
            "GS (kts)": gs_kts, 
            "Mach": round(mach, 2),
            "Lat": p[6], "Lon": p[5]
        })

    with col_map:
        m = folium.Map(location=[1.35, 103.98], zoom_start=3, tiles='CartoDB dark_matter')
        for ac in processed_fleet:
            popup_html = f"<b>SQ {ac['Callsign']}</b><br>Alt: {ac['Alt (ft)']:,} ft<br>GS: {ac['GS (kts)']} kts"
            folium.Marker(
                [ac['Lat'], ac['Lon']], 
                popup=popup_html, 
                icon=folium.Icon(color='orange', icon='plane')
            ).add_to(m)
        st_folium(m, width="100%", height=500, key="radar_v1")
    
    with col_stats:
        st.metric("SIA Airborne", len(processed_fleet))
        if processed_fleet:
            # Create DF and format altitude for display
            df = pd.DataFrame(processed_fleet)
            df_display = df.drop(['Lat', 'Lon'], axis=1)
            st.dataframe(df_display, hide_index=True)
        else:
            st.warning("Satellite link delay. Please refresh in 5s.")

with tab_route:
    st.markdown('<div class="search-card">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([2, 2, 2])
    orig = c1.text_input("Origin", "SIN").upper()
    dest = c2.text_input("Destination", "KUL").upper()
    r_date = c3.date_input("Date", key="route_date")
    if st.button("SEARCH BY ROUTE"):
        res = call_sia_api("getbyroute", {
            "originAirportCode": orig, 
            "destinationAirportCode": dest, 
            "scheduledDepartureDate": str(r_date)
        })
        if res.get("status") == "SUCCESS":
            flights = res.get("data", {}).get("response", {}).get("flights", [])
            for f in flights:
                for leg in f.get("legs", []):
                    st.markdown(f"**SQ {leg['flightNumber']}** | Status: `{leg['flightStatus']}`")
                    st.caption(f"Dep: {leg['scheduledDepartureTime']} | Arr: {leg['scheduledArrivalTime']}")
                    st.divider()
        else: st.error("No flights found.")
    st.markdown('</div>', unsafe_allow_html=True)

with tab_flight:
    st.markdown('<div class="search-card">', unsafe_allow_html=True)
    f1, f2 = st.columns([2, 2])
    f_no = f1.text_input("Flight Number", "638")
    f_date = f2.date_input("Date", key="f_date")
    if st.button("SEARCH BY FLIGHT"):
        res = call_sia_api("get", {"flightNumber": f_no, "scheduledDepartureDate": str(f_date)})
        if res.get("status") == "SUCCESS":
            data = res["data"]["response"]["flights"][0]["legs"][0]
            st.success(f"Flight SQ {f_no}: {data['flightStatus']}")
        else: st.error("Flight status unavailable.")
    st.markdown('</div>', unsafe_allow_html=True)
