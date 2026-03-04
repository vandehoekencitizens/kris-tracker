import streamlit as st
import requests
import uuid
import folium
import os
import math
import time
import pandas as pd
from streamlit_folium import st_folium
from supabase import create_client

# --- 1. INITIALIZATION & SUPABASE ---
st.set_page_config(page_title="KrisTracker | Executive Command", page_icon="✈️", layout="wide")

@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- 2. RESTORED EXECUTIVE THEME & LOGO ---
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
    .flight-box {{
        background: {SIA_NAVY}; color: white; padding: 25px; border-radius: 8px;
        border-left: 10px solid {SIA_GOLD}; margin-top: 20px;
    }}
    .status-badge {{
        background: {SIA_GOLD}; color: {SIA_NAVY}; padding: 4px 12px;
        border-radius: 20px; font-weight: bold; font-size: 0.85em;
    }}
    .airport-code {{ font-size: 3em; font-weight: bold; line-height: 1; }}
    .sidebar-logo {{ display: flex; justify-content: center; padding: 20px 0; }}
    .sidebar-logo svg {{ width: 180px; height: auto; fill: white; }}
    </style>
    """, unsafe_allow_html=True)

# --- 3. RESTORED AVIATION LOGIC (MACH/FT/KTS) ---
def get_mach(gs_mps, alt_m):
    if not gs_mps or gs_mps < 1 or not alt_m: return 0.0
    temp_k = 288.15 - (0.0065 * alt_m)
    return gs_mps / (20.046 * math.sqrt(temp_k))

@st.cache_data(ttl=60)
def get_fleet_cached():
    url = "https://opensky-network.org/api/states/all"
    auth = (st.secrets["OPENSKY_CLIENT_ID"], st.secrets["OPENSKY_CLIENT_SECRET"])
    try:
        r = requests.get(url, auth=auth, timeout=12)
        states = r.json().get("states", [])
        sia_flights = []
        for s in (states or []):
            callsign = str(s[1]).strip() if s[1] else ""
            if callsign.startswith(("SIA", "SQ")):
                alt_m = s[7] if s[7] else 0
                gs_mps = s[9] if s[9] else 0
                sia_flights.append({
                    "Callsign": callsign, "Registration": s[0].upper(),
                    "Lat": s[6], "Lon": s[5],
                    "Alt (ft)": int(alt_m * 3.28084),
                    "GS (kts)": int(gs_mps * 1.94384),
                    "Mach": round(get_mach(gs_mps, alt_m), 2)
                })
        return sia_flights
    except: return []

# --- 4. API THROTTLING & VISUALIZER ---
def call_sia_api_safe(endpoint, payload):
    # Visual throttle to prevent 403 Over QPS
    with st.status("Establishing Satellite Link...", expanded=False) as status:
        time.sleep(1.5)
        url = f"https://apigw.singaporeair.com/api/uat/v2/flightstatus/{endpoint}"
        headers = {
            "accept": "*/*", "Content-Type": "application/json",
            "api_key": st.secrets["SIA_STATUS_KEY"],
            "x-csl-client-id": "SPD", "x-csl-client-uuid": str(uuid.uuid4())
        }
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=15)
            if res.status_code == 403:
                status.update(label="Rate Limit Hit!", state="error")
                return {"status": "LIMIT"}
            status.update(label="Data Synchronized", state="complete")
            return res.json()
        except: return None

def render_flight_card(data):
    for f in data.get("response", {}).get("flights", []):
        for leg in f.get("legs", []):
            st.markdown(f"""
            <div class="flight-box">
                <div style="display: flex; justify-content: space-between;">
                    <div><span class="status-badge">{leg['flightStatus'].upper()}</span><h3>SQ {leg['flightNumber']}</h3></div>
                    <div style="text-align:right;"><p>Fleet Type</p><strong>B777 / A350</strong></div>
                </div>
                <div style="display: flex; justify-content: space-between; margin-top:20px; text-align:center;">
                    <div style="flex:1;"><div class="airport-code">{leg['origin']['airportCode']}</div><div>{leg['origin']['airportName']}</div></div>
                    <div style="flex:1; font-size:3em;">✈️</div>
                    <div style="flex:1;"><div class="airport-code">{leg['destination']['airportCode']}</div><div>{leg['destination']['airportName']}</div></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

# --- 5. AUTH GATE & SIDEBAR LOGO ---
logo_path = "singapore-airlines.svg"
if os.path.exists(logo_path):
    with open(logo_path, "r") as f:
        st.sidebar.markdown(f'<div class="sidebar-logo">{f.read()}</div>', unsafe_allow_html=True)

if "user" not in st.session_state:
    st.title("KrisTracker Login")
    with st.container(border=True):
        em = st.text_input("Email")
        pw = st.text_input("Password", type="password")
        if st.button("SIGN IN"):
            try:
                resp = supabase.auth.sign_in_with_password({"email": em.lower().strip(), "password": pw})
                st.session_state["user"] = resp.user
                st.rerun()
            except: st.error("Login Error")
    st.stop()

# --- 6. MAIN DASHBOARD ---
st.sidebar.write(f"Logged in: **{st.session_state.user.email}**")
if st.sidebar.button("Logout"):
    supabase.auth.sign_out(); del st.session_state["user"]; st.rerun()

t_radar, t_route, t_flight = st.tabs(["📡 LIVE RADAR", "✈️ BY ROUTE", "🔎 BY FLIGHT NUMBER"])

with t_radar:
    fleet = get_fleet_cached()
    col_m, col_s = st.columns([3, 1])
    with col_m:
        m = folium.Map(location=[1.35, 103.98], zoom_start=3, tiles='CartoDB dark_matter')
        for ac in fleet:
            popup = f"SQ {ac['Callsign']} | {ac['Registration']}<br>{ac['Alt (ft)']:,} ft | Mach {ac['Mach']}"
            folium.Marker([ac['Lat'], ac['Lon']], popup=popup, icon=folium.Icon(color='orange', icon='plane')).add_to(m)
        st_folium(m, width="100%", height=500, key="radar_fixed")
    with col_s:
        st.metric("Airborne", len(fleet))
        if fleet:
            st.dataframe(pd.DataFrame(fleet).drop(['Lat', 'Lon'], axis=1), hide_index=True)

with t_route:
    st.markdown('<div class="search-card">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    orig, dest = c1.text_input("From", "SIN"), c2.text_input("To", "KUL")
    date = c3.date_input("Date", key="d1")
    if st.button("SEARCH ROUTE"):
        res = call_sia_api_safe("getbyroute", {"originAirportCode": orig.upper(), "destinationAirportCode": dest.upper(), "scheduledDepartureDate": str(date)})
        if res and res.get("status") == "SUCCESS": render_flight_card(res.get("data"))
    st.markdown('</div>', unsafe_allow_html=True)

with t_flight:
    st.markdown('<div class="search-card">', unsafe_allow_html=True)
    f1, f2 = st.columns(2)
    f_num, f_date = f1.text_input("Flight #", "317"), f2.date_input("Date", key="d2")
    if st.button("SEARCH FLIGHT"):
        res = call_sia_api_safe("getbynumber", {"airlineCode": "SQ", "flightNumber": f_num, "scheduledDepartureDate": str(f_date)})
        if res and res.get("status") == "SUCCESS": render_flight_card(res.get("data"))
    st.markdown('</div>', unsafe_allow_html=True)
