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
st.set_page_config(page_title="SIA KrisTracker | Executive", page_icon="✈️", layout="wide")

@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- 2. EXECUTIVE THEME & LOGO ---
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
        font-weight: bold; border-radius: 4px; border: none; height: 45px;
    }}
    .sidebar-logo {{ display: flex; justify-content: center; padding: 20px 0; }}
    .sidebar-logo svg {{ width: 200px; height: auto; fill: white; }}
    </style>
    """, unsafe_allow_html=True)

# --- 3. AVIATION LOGIC (Restored Mach/Units) ---
def get_mach(gs_mps, alt_m):
    if not gs_mps or gs_mps < 1 or not alt_m: return 0.0
    temp_k = 288.15 - (0.0065 * alt_m)
    speed_of_sound = 20.046 * math.sqrt(temp_k)
    return gs_mps / speed_of_sound

@st.cache_data(ttl=120)
def get_fleet_cached():
    url = "https://opensky-network.org/api/states/all"
    auth = (st.secrets["OPENSKY_CLIENT_ID"], st.secrets["OPENSKY_CLIENT_SECRET"])
    try:
        r = requests.get(url, auth=auth, timeout=12)
        states = r.json().get("states", [])
        sia_flights = []
        for s in states:
            callsign = str(s[1]).strip() if s[1] else ""
            if callsign.startswith("SIA") or callsign.startswith("SQ"):
                sia_flights.append({
                    "Callsign": callsign,
                    "Reg": s[0].upper(),
                    "Lat": s[6], "Lon": s[5],
                    "Alt (ft)": int(s[7] * 3.28084) if s[7] else 0,
                    "GS (kts)": int(s[9] * 1.94384) if s[9] else 0,
                    "Mach": round(get_mach(s[9], s[7]), 2)
                })
        return sia_flights
    except: return []

# --- 4. SIA API (Corrected Endpoint from Docs) ---
def call_sia_api(endpoint_suffix, payload):
    # Using the path from your provided docs: /api/uat/v2/flightstatus/
    url = f"https://apigw.singaporeair.com/api/uat/v2/flightstatus/{endpoint_suffix}"
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

# --- 5. AUTH & SIDEBAR ---
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
            except: st.error("Login Error. Use the same credentials you registered with.")
    st.stop()

# --- 6. DASHBOARD TABS ---
st.sidebar.write(f"Logged in: **{st.session_state.user.email}**")
if st.sidebar.button("Logout"):
    supabase.auth.sign_out(); del st.session_state["user"]; st.rerun()

t_radar, t_route, t_flight = st.tabs(["📡 LIVE RADAR", "✈️ BY ROUTE", "🔎 BY FLIGHT NUMBER"])

with t_radar:
    fleet = get_fleet_cached()
    col_map, col_list = st.columns([3, 1])
    with col_map:
        m = folium.Map(location=[1.35, 103.98], zoom_start=3, tiles='CartoDB dark_matter')
        for ac in fleet:
            if ac['Lat'] and ac['Lon']:
                popup = f"SQ {ac['Callsign']}<br>Reg: {ac['Reg']}<br>Alt: {ac['Alt (ft)']:,} ft<br>Mach: {ac['Mach']}"
                folium.Marker([ac['Lat'], ac['Lon']], popup=popup, icon=folium.Icon(color='orange', icon='plane')).add_to(m)
        st_folium(m, width="100%", height=500, key="radar_vFinal")
    with col_list:
        st.metric("SIA Airborne", len(fleet))
        if fleet:
            df = pd.DataFrame(fleet).drop(['Lat', 'Lon'], axis=1)
            st.dataframe(df, hide_index=True)
        else:
            st.warning("Satellite Link Delay. Refresh in 10s.")

with t_route:
    st.markdown('<div class="search-card">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    orig = c1.text_input("Origin", "SIN")
    dest = c2.text_input("Destination", "KUL")
    date = c3.date_input("Departure Date")
    if st.button("EXECUTE ROUTE SEARCH"):
        payload = {"originAirportCode": orig.upper(), "destinationAirportCode": dest.upper(), "scheduledDepartureDate": str(date)}
        res = call_sia_api("getbyroute", payload)
        if res.get("status") == "SUCCESS":
            st.json(res.get("data"))
        else: st.error(f"Search failed: {res}")
    st.markdown('</div>', unsafe_allow_html=True)

with t_flight:
    st.markdown('<div class="search-card">', unsafe_allow_html=True)
    f1, f2 = st.columns(2)
    f_no = f1.text_input("Flight Number (e.g., 638)", "638")
    f_date = f2.date_input("Date", key="f_date_search")
    if st.button("SEARCH BY FLIGHT NUMBER"):
        payload = {"flightNumber": f_no, "scheduledDepartureDate": str(f_date)}
        res = call_sia_api("get", payload) # 'get' is common for flight number status
        if res.get("status") == "SUCCESS":
            st.json(res.get("data"))
        else: st.error("No data found for this flight.")
    st.markdown('</div>', unsafe_allow_html=True)
