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

# --- 2. THEME (NAVY & GOLD) ---
SIA_NAVY, SIA_GOLD = "#00266B", "#BD9B60"
st.markdown(f"""
    <style>
    .stApp {{ background-color: white; color: {SIA_NAVY}; }}
    [data-testid="stSidebar"] {{ background-color: {SIA_NAVY} !important; }}
    [data-testid="stSidebar"] * {{ color: white !important; }}
    .search-card {{
        background-color: white; padding: 25px; border-radius: 4px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1); border-top: 4px solid {SIA_GOLD};
        margin-bottom: 20px;
    }}
    .flight-box {{
        background: {SIA_NAVY}; color: white; padding: 25px; border-radius: 8px;
        border-left: 10px solid {SIA_GOLD}; margin-top: 20px;
    }}
    .status-badge {{ background: {SIA_GOLD}; color: {SIA_NAVY}; padding: 4px 12px; border-radius: 20px; font-weight: bold; }}
    .airport-code {{ font-size: 3.5em; font-weight: bold; line-height: 1; }}
    </style>
    """, unsafe_allow_html=True)

# --- 3. OP-CENTER (DEBUG MODE) ---
st.sidebar.title("🛠 OP-CENTER")
debug_enabled = st.sidebar.toggle("Enable Debug Mode", value=False)

def log_debug(title, content):
    if debug_enabled:
        with st.sidebar.expander(f"DEBUG: {title}"):
            st.write(content)

# --- 4. RESILIENT RADAR LOGIC ---
def get_mach(gs_mps, alt_m):
    if not gs_mps or gs_mps < 1 or not alt_m: return 0.0
    return gs_mps / (20.046 * math.sqrt(288.15 - (0.0065 * alt_m)))

@st.cache_data(ttl=60)
def get_fleet_safe():
    """Handles OpenSky timeouts gracefully."""
    auth = (st.secrets["OPENSKY_CLIENT_ID"], st.secrets["OPENSKY_CLIENT_SECRET"])
    try:
        # Reduced timeout to 5s to keep the app snappy during glitches
        r = requests.get("https://opensky-network.org/api/states/all", auth=auth, timeout=5)
        if r.status_code != 200: return []
        
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
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
        # This is where we catch your HTTPSConnectionPool error
        return "OFFLINE"
    except Exception as e:
        log_debug("Radar Error", str(e))
        return []

# --- 5. SIA API LOGIC ---
def render_flight_status(data):
    flights = data.get("response", {}).get("flights", [])
    if not flights:
        st.warning("No flight data found in response.")
        return
    for f in flights:
        for leg in f.get("legs", []):
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
                        <small>AIRCRAFT</small><br>
                        <b>{leg.get('aircraft', {}).get('displayName', 'SIA Long-Haul')}</b>
                    </div>
                </div>
                <div style="display: flex; justify-content: space-between; text-align: center; margin-top:20px;">
                    <div style="flex:1;"><div class="airport-code">{leg['origin']['airportCode']}</div><div>{leg['scheduledDepartureTime'].split('T')[1]}</div></div>
                    <div style="flex:1; font-size:3em; opacity:0.2;">✈️</div>
                    <div style="flex:1;"><div class="airport-code">{leg['destination']['airportCode']}</div><div>{leg['scheduledArrivalTime'].split('T')[1]}</div></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

def call_sia_api(endpoint, payload):
    time.sleep(1.8) # Throttling for QPS
    url = f"https://apigw.singaporeair.com/api/uat/v2/flightstatus/{endpoint}"
    headers = {
        "api_key": st.secrets["SIA_STATUS_KEY"], "x-csl-client-id": "SPD",
        "x-csl-client-uuid": str(uuid.uuid4()), "Content-Type": "application/json"
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        if res.status_code == 200: return res.json()
        return None
    except: return None

# --- 6. AUTH & MAIN DASHBOARD ---
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
            except: st.error("Auth failed.")
    st.stop()

t_radar, t_search = st.tabs(["📡 LIVE RADAR", "🔎 FLIGHT SEARCH"])

with t_radar:
    fleet = get_fleet_safe()
    if fleet == "OFFLINE":
        st.error("📡 **Telemetry Server Timeout**: OpenSky is currently unresponsive. Live radar markers are temporarily unavailable, but Search remains active.")
        m = folium.Map(location=[1.35, 103.98], zoom_start=3, tiles='CartoDB dark_matter')
        st_folium(m, width="100%", height=500)
    else:
        col_m, col_l = st.columns([3, 1])
        with col_m:
            m = folium.Map(location=[1.35, 103.98], zoom_start=3, tiles='CartoDB dark_matter')
            for ac in fleet:
                folium.Marker([ac['Lat'], ac['Lon']], popup=f"SQ {ac['Callsign']}", icon=folium.Icon(color='orange')).add_to(m)
            st_folium(m, width="100%", height=500, key="radar_resilient")
        with col_l:
            st.metric("SIA Airborne", len(fleet))
            if fleet:
                df = pd.DataFrame(fleet)
                st.dataframe(df.drop(columns=[c for c in ['Lat', 'Lon'] if c in df.columns]), hide_index=True)

with t_search:
    st.markdown('<div class="search-card">', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    f_num = c1.text_input("Flight Number", "317")
    f_date = c2.date_input("Date")
    if st.button("FETCH STATUS"):
        res = call_sia_api("getbynumber", {"airlineCode": "SQ", "flightNumber": f_num, "scheduledDepartureDate": str(f_date)})
        if res and res.get("status") == "SUCCESS":
            render_flight_status(res.get("data"))
        else: st.warning("No flight data found.")
    st.markdown('</div>', unsafe_allow_html=True)
