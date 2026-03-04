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
st.set_page_config(page_title="KrisTracker | Full Command", page_icon="✈️", layout="wide")

@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
supabase = init_supabase()

# --- 2. EXECUTIVE THEME ---
SIA_NAVY, SIA_GOLD = "#00266B", "#BD9B60"
st.markdown(f"""<style>
    .stApp {{ background-color: white; color: {SIA_NAVY}; }}
    [data-testid="stSidebar"] {{ background-color: {SIA_NAVY} !important; }}
    [data-testid="stSidebar"] * {{ color: white !important; font-weight: 500; }}
    .flight-box {{
        background: {SIA_NAVY}; color: white; padding: 25px; border-radius: 8px;
        border-left: 10px solid {SIA_GOLD}; margin-bottom: 20px;
    }}
    .status-badge {{ background: {SIA_GOLD}; color: {SIA_NAVY}; padding: 4px 12px; border-radius: 20px; font-weight: bold; }}
    .airport-code {{ font-size: 3.2em; font-weight: bold; line-height: 1; }}
</style>""", unsafe_allow_html=True)

# --- 3. OP-CENTER & SWITCHER ---
st.sidebar.title("🛠 OP-CENTER")
api_source = st.sidebar.radio("Intelligence Source", ["SIA Official", "AirLabs Enhanced"])
debug_enabled = st.sidebar.toggle("Enable Debug Mode", value=False)

def log_debug(title, content):
    if debug_enabled:
        with st.sidebar.expander(f"DEBUG: {title}"):
            st.write(content)

# --- 4. PHYSICS & RADAR ENGINES ---
def get_mach(gs_mps, alt_m):
    if not gs_mps or gs_mps < 1 or not alt_m: return 0.0
    return gs_mps / (20.046 * math.sqrt(288.15 - (0.0065 * alt_m)))

@st.cache_data(ttl=60)
def get_fleet_radar():
    auth = (st.secrets["OPENSKY_CLIENT_ID"], st.secrets["OPENSKY_CLIENT_SECRET"])
    try:
        r = requests.get("https://opensky-network.org/api/states/all", auth=auth, timeout=5)
        states = r.json().get("states", [])
        sia = []
        for s in (states or []):
            if str(s[1]).strip().startswith(("SIA", "SQ")):
                alt, gs = s[7] or 0, s[9] or 0
                sia.append({
                    "Callsign": s[1].strip(), "Reg": s[0].upper(),
                    "Lat": s[6], "Lon": s[5], "Alt (ft)": int(alt * 3.28),
                    "GS (kts)": int(gs * 1.94), "Mach": round(get_mach(gs, alt), 2)
                })
        return sia
    except: return "TIMEOUT"

# --- 5. AIRLABS BACKUP ---
def get_airlabs_data(f_num):
    try:
        url = f"https://airlabs.co/api/v9/flight?flight_icao=SQ{f_num}&api_key={st.secrets['AIRLABS_API_KEY']}"
        res = requests.get(url, timeout=5).json().get('response', {})
        return {"reg": res.get("reg_number", "9V-TBA"), "model": res.get("model", "SIA Aircraft"), "delay": res.get("dep_delayed")}
    except: return None

# --- 6. RENDERER (ALL FEATURES RETAINED) ---
def render_flight_status(data):
    flights = data.get("response", {}).get("flights", [])
    if not flights:
        st.warning("No live flight data found.")
        return
    for f in flights:
        for leg in f.get("legs", []):
            f_num = leg.get('flightNumber', '0')
            ac_type = leg.get('aircraft', {}).get('displayName', "SIA Fleet")
            reg = leg.get('aircraft', {}).get('registrationNumber', "TRACKING")
            delay_info = ""

            if api_source == "AirLabs Enhanced":
                backup = get_airlabs_data(f_num)
                if backup:
                    ac_type, reg = backup['model'], backup['reg']
                    if backup['delay']: delay_info = f"<br><span style='color:#FF4B4B;'>Delay: {backup['delay']}m</span>"

            # Minified HTML for stable rendering
            st.markdown(f"""<div class="flight-box">
                <div style="display:flex; justify-content:space-between;">
                    <div><span class="status-badge">{leg.get('flightStatus', 'LIVE')}</span><h2 style="color:white;margin:10px 0;">SQ {f_num}</h2><p style="opacity:0.7;">Singapore Airlines</p></div>
                    <div style="text-align:right;"><small>AIRCRAFT / TAIL</small><br><b style="color:{SIA_GOLD};">{ac_type}</b><br><b>{reg}</b>{delay_info}</div>
                </div>
                <div style="display:flex; justify-content:space-between; text-align:center; margin-top:30px; background:white; color:{SIA_NAVY}; padding:20px; border-radius:4px;">
                    <div style="flex:1;"><div class="airport-code">{leg['origin']['airportCode']}</div><div>{leg['scheduledDepartureTime'].split('T')[1][:5]}</div></div>
                    <div style="flex:1; font-size:3em; opacity:0.3; align-self:center;">✈️</div>
                    <div style="flex:1;"><div class="airport-code">{leg['destination']['airportCode']}</div><div>{leg['scheduledArrivalTime'].split('T')[1][:5]}</div></div>
                </div>
            </div>""", unsafe_allow_html=True)

def call_sia_gateway(endpoint, payload):
    time.sleep(1.5)
    url = f"https://apigw.singaporeair.com/api/uat/v2/flightstatus/{endpoint}"
    headers = {"api_key": st.secrets["SIA_STATUS_KEY"], "x-csl-client-id": "SPD", "x-csl-client-uuid": str(uuid.uuid4()), "Content-Type": "application/json"}
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=12)
        log_debug(f"API {endpoint}", res.json())
        return res.json() if res.status_code == 200 else None
    except: return None

# --- 7. AUTH GATE ---
if "user" not in st.session_state:
    with st.container(border=True):
        st.title("KrisTracker Executive Portal")
        em, pw = st.text_input("Email"), st.text_input("Password", type="password")
        if st.button("SIGN IN"):
            try:
                res = supabase.auth.sign_in_with_password({"email": em, "password": pw})
                st.session_state.user = res.user
                st.rerun()
            except: st.error("Access Denied.")
    st.stop()

# --- 8. DASHBOARD ---
t_radar, t_num, t_route = st.tabs(["📡 LIVE RADAR", "🔎 BY FLIGHT", "✈️ BY ROUTE"])

with t_radar:
    fleet = get_fleet_radar()
    if fleet == "TIMEOUT":
        st.error("Radar Telemetry Offline.")
    else:
        c_m, c_l = st.columns([3, 1])
        with c_m:
            m = folium.Map(location=[1.35, 103.98], zoom_start=3, tiles='CartoDB dark_matter')
            for ac in (fleet or []):
                folium.Marker([ac['Lat'], ac['Lon']], popup=f"SQ {ac['Callsign']} | Mach {ac['Mach']}", icon=folium.Icon(color='orange')).add_to(m)
            st_folium(m, width="100%", height=500, key="radar_vFinal")
        with c_l:
            st.metric("SIA Airborne", len(fleet) if isinstance(fleet, list) else 0)
            if isinstance(fleet, list) and fleet:
                st.dataframe(pd.DataFrame(fleet).drop(columns=['Lat', 'Lon']), hide_index=True)

with t_num:
    with st.container(border=True):
        c1, c2 = st.columns(2)
        f_in = c1.text_input("Flight #", "317")
        d_in = c2.date_input("Date", key="d_n")
        if st.button("TRACK BY NUMBER"):
            res = call_sia_gateway("getbynumber", {"airlineCode": "SQ", "flightNumber": f_in, "scheduledDepartureDate": str(d_in)})
            if res: render_flight_status(res.get("data"))

with t_route:
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        o, d = c1.text_input("From", "SIN"), c2.text_input("To", "LHR")
        dr = c3.date_input("Date", key="d_r")
        if st.button("TRACK BY ROUTE"):
            res = call_sia_gateway("getbyroute", {"originAirportCode": o.upper(), "destinationAirportCode": d.upper(), "scheduledDepartureDate": str(dr)})
            if res: render_flight_status(res.get("data"))
