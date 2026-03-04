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

# --- 1. INITIALIZATION ---
st.set_page_config(page_title="KrisTracker | Executive Command", page_icon="✈️", layout="wide")

@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- 2. THEME & BRANDING ---
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
    .status-badge {{ background: {SIA_GOLD}; color: {SIA_NAVY}; padding: 4px 12px; border-radius: 20px; font-weight: bold; }}
    .airport-code {{ font-size: 3.5em; font-weight: bold; line-height: 1; }}
    .sidebar-logo {{ display: flex; justify-content: center; padding: 20px 0; }}
    .sidebar-logo svg {{ width: 160px; fill: white; }}
    </style>
    """, unsafe_allow_html=True)

# --- 3. OP-CENTER (DEBUG MODE) ---
st.sidebar.title("🛠 OP-CENTER")
debug_enabled = st.sidebar.toggle("Enable Debug Mode", value=False)

def log_debug(title, content):
    if debug_enabled:
        with st.sidebar.expander(f"DEBUG: {title}", expanded=False):
            st.write(content)

# --- 4. AVIATION MATH & RADAR (LOCKED) ---
def get_mach(gs_mps, alt_m):
    if not gs_mps or gs_mps < 1 or not alt_m: return 0.0
    temp_k = 288.15 - (0.0065 * alt_m)
    return gs_mps / (20.046 * math.sqrt(temp_k))

@st.cache_data(ttl=60)
def get_fleet():
    auth = (st.secrets["OPENSKY_CLIENT_ID"], st.secrets["OPENSKY_CLIENT_SECRET"])
    try:
        r = requests.get("https://opensky-network.org/api/states/all", auth=auth, timeout=10)
        states = r.json().get("states", [])
        sia = []
        for s in (states or []):
            callsign = str(s[1]).strip() if s[1] else ""
            if callsign.startswith(("SIA", "SQ")):
                alt, gs = s[7] or 0, s[9] or 0
                sia.append({
                    "Callsign": callsign, "Reg": s[0].upper(),
                    "Lat": s[6], "Lon": s[5], "Alt (ft)": int(alt * 3.28084),
                    "GS (kts)": int(gs * 1.94384), "Mach": round(get_mach(gs, alt), 2)
                })
        return sia
    except Exception as e:
        log_debug("OpenSky Error", str(e))
        return []

# --- 5. SIA API & VISUALIZER ---
def render_flight_card(data):
    flights = data.get("response", {}).get("flights", [])
    if not flights:
        st.warning("Flight data synchronized. No specific leg data found.")
        return
    for f in flights:
        for leg in f.get("legs", []):
            # Intelligent aircraft guessing if API is blank
            raw_type = leg.get('aircraft', {}).get('displayName', "")
            if not raw_type or raw_type == "":
                f_num = int(leg.get('flightNumber', '0'))
                raw_type = "Airbus A350-900" if f_num < 500 else "Boeing 737-8 MAX"
            
            st.markdown(f"""
            <div class="flight-box">
                <div style="display: flex; justify-content: space-between;">
                    <div>
                        <span class="status-badge">{leg.get('flightStatus', 'UNKNOWN').upper()}</span>
                        <h2 style="color:white; margin:10px 0;">SQ {leg.get('flightNumber')}</h2>
                    </div>
                    <div style="text-align:right;">
                        <small>TERMINAL / GATE</small><br>
                        <b>{leg.get('origin', {}).get('airportTerminal', 'TBA')} / {leg.get('gate', 'TBA')}</b><br>
                        <small>AIRCRAFT TYPE</small><br>
                        <b>{raw_type}</b>
                    </div>
                </div>
                <div style="display: flex; justify-content: space-between; text-align: center; margin-top:20px;">
                    <div style="flex:1;"><div class="airport-code">{leg['origin']['airportCode']}</div><div>{leg['scheduledDepartureTime'].split('T')[1]}</div></div>
                    <div style="flex:1; font-size:3em; opacity:0.3;">✈️</div>
                    <div style="flex:1;"><div class="airport-code">{leg['destination']['airportCode']}</div><div>{leg['scheduledArrivalTime'].split('T')[1]}</div></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

def call_sia(endpoint, payload):
    time.sleep(1.8) # Critical QPS Throttle
    url = f"https://apigw.singaporeair.com/api/uat/v2/flightstatus/{endpoint}"
    headers = {
        "api_key": st.secrets["SIA_STATUS_KEY"], "x-csl-client-id": "SPD",
        "x-csl-client-uuid": str(uuid.uuid4()), "Content-Type": "application/json"
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=15)
        if res.status_code == 200 and "application/json" in res.headers.get("Content-Type", ""):
            return res.json()
        log_debug("Bad API Response", f"Status: {res.status_code} | Body: {res.text}")
        return None
    except Exception as e:
        st.error(f"Gateway Error: {e}")
        return None

# --- 6. AUTH GATE & LOGO ---
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
            except: st.error("Login failed.")
    st.stop()

# --- 7. MAIN DASHBOARD ---
st.sidebar.write(f"Logged in: **{st.session_state.user.email}**")
t_radar, t_route, t_flight = st.tabs(["📡 LIVE RADAR", "✈️ BY ROUTE", "🔎 BY FLIGHT NUMBER"])

with t_radar:
    fleet = get_fleet()
    c_map, c_list = st.columns([3, 1])
    with c_map:
        m = folium.Map(location=[1.35, 103.98], zoom_start=3, tiles='CartoDB dark_matter')
        for ac in fleet:
            popup = f"SQ {ac['Callsign']} | {ac['Alt (ft)']:,}ft | Mach {ac['Mach']}"
            folium.Marker([ac['Lat'], ac['Lon']], popup=popup, icon=folium.Icon(color='orange')).add_to(m)
        st_folium(m, width="100%", height=500, key="radar_fixed")
    with c_list:
        st.metric("Global Airborne", len(fleet))
        if fleet:
            df = pd.DataFrame(fleet)
            cols = [c for c in ['Lat', 'Lon'] if c in df.columns]
            st.dataframe(df.drop(columns=cols), hide_index=True)

with t_route:
    st.markdown('<div class="search-card">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    orig, dest = c1.text_input("Origin", "SIN"), c2.text_input("Destination", "LHR")
    date = c3.date_input("Date", key="r_date")
    if st.button("SEARCH BY ROUTE"):
        res = call_sia("getbyroute", {"originAirportCode": orig.upper(), "destinationAirportCode": dest.upper(), "scheduledDepartureDate": str(date)})
        if res and res.get("status") == "SUCCESS": render_flight_card(res.get("data"))

with t_flight:
    st.markdown('<div class="search-card">', unsafe_allow_html=True)
    f1, f2 = st.columns(2)
    f_num, f_date = f1.text_input("Flight #", "317"), f2.date_input("Departure Date", key="f_date")
    if st.button("SEARCH BY FLIGHT NUMBER"):
        res = call_sia("getbynumber", {"airlineCode": "SQ", "flightNumber": f_num, "scheduledDepartureDate": str(f_date)})
        if res and res.get("status") == "SUCCESS": render_flight_card(res.get("data"))
