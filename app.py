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
st.set_page_config(page_title="KrisTracker | Command Center", page_icon="✈️", layout="wide")

@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- 2. EXECUTIVE THEME & STYLING ---
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
    .airport-code {{ font-size: 3.5em; font-weight: bold; line-height: 1; }}
    .info-label {{ font-size: 0.8em; opacity: 0.6; text-transform: uppercase; }}
    .info-value {{ font-weight: bold; color: {SIA_GOLD}; }}
    </style>
    """, unsafe_allow_html=True)

# --- 3. THE "FULL DATA" VISUALIZER ---
def render_flight_card(data):
    """Extracts all available flight metadata including Gate, Terminal, and Aircraft."""
    flights = data.get("response", {}).get("flights", [])
    if not flights:
        st.warning("Flight data synchronized but no leg details found.")
        return

    for f in flights:
        # Main origin/destination info
        for leg in f.get("legs", []):
            # Extracting with defaults
            origin_term = leg.get("origin", {}).get("airportTerminal", "TBA")
            dest_term = leg.get("destination", {}).get("airportTerminal", "TBA")
            # Aircraft type is often in a separate object or string in SIA API
            ac_type = leg.get("aircraft", {}).get("displayName", "SIA Long-Haul")
            gate = leg.get("gate", "TBA") # Common field name in Prod vs UAT

            st.markdown(f"""
            <div class="flight-box">
                <div style="display: flex; justify-content: space-between; align-items: start;">
                    <div>
                        <span class="status-badge">{leg['flightStatus'].upper()}</span>
                        <h2 style="margin: 15px 0; color: white;">SQ {leg['flightNumber']}</h2>
                        <p style="margin:0; opacity: 0.7;">{leg['operatingAirlineName']}</p>
                    </div>
                    <div style="text-align: right;">
                        <span class="info-label">Equipment</span><br>
                        <span class="info-value">{ac_type}</span><br><br>
                        <span class="info-label">Gate</span><br>
                        <span class="info-value">{gate}</span>
                    </div>
                </div>
                
                <div style="display: flex; justify-content: space-between; margin-top: 30px; text-align: center;">
                    <div style="flex: 1;">
                        <div class="airport-code">{leg['origin']['airportCode']}</div>
                        <div class="info-label">Terminal {origin_term}</div>
                        <div style="color: {SIA_GOLD}; font-size: 1.5em; font-weight: bold; margin-top:10px;">
                            {leg['scheduledDepartureTime'].split('T')[1]}
                        </div>
                    </div>
                    <div style="flex: 1; font-size: 3em; opacity: 0.3; align-self: center;">✈️</div>
                    <div style="flex: 1;">
                        <div class="airport-code">{leg['destination']['airportCode']}</div>
                        <div class="info-label">Terminal {dest_term}</div>
                        <div style="color: {SIA_GOLD}; font-size: 1.5em; font-weight: bold; margin-top:10px;">
                            {leg['scheduledArrivalTime'].split('T')[1]}
                        </div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

# --- 4. TELEMETRY LOGIC (RETAINED) ---
def get_mach(gs_mps, alt_m):
    if not gs_mps or gs_mps < 1 or not alt_m: return 0.0
    return gs_mps / (20.046 * math.sqrt(288.15 - (0.0065 * alt_m)))

@st.cache_data(ttl=60)
def get_fleet_telemetry():
    auth = (st.secrets["OPENSKY_CLIENT_ID"], st.secrets["OPENSKY_CLIENT_SECRET"])
    try:
        r = requests.get("https://opensky-network.org/api/states/all", auth=auth, timeout=12)
        states = r.json().get("states", [])
        sia = []
        for s in (states or []):
            if str(s[1]).strip().startswith(("SIA", "SQ")):
                alt = s[7] if s[7] else 0
                gs = s[9] if s[9] else 0
                sia.append({
                    "Callsign": s[1].strip(), "Registration": s[0].upper(),
                    "Lat": s[6], "Lon": s[5], "Alt (ft)": int(alt * 3.28),
                    "GS (kts)": int(gs * 1.94), "Mach": round(get_mach(gs, alt), 2)
                })
        return sia
    except: return []

# --- 5. API THROTTLING (RETAINED) ---
def call_sia_throttled(endpoint, payload):
    with st.status("Syncing with Gateway...", expanded=False) as s:
        time.sleep(1.5) # Mandatory QPS Throttle
        url = f"https://apigw.singaporeair.com/api/uat/v2/flightstatus/{endpoint}"
        headers = {
            "accept": "*/*", "Content-Type": "application/json",
            "api_key": st.secrets["SIA_STATUS_KEY"],
            "x-csl-client-id": "SPD", "x-csl-client-uuid": str(uuid.uuid4())
        }
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=15)
            if res.status_code == 403: 
                s.update(label="Rate Limit!", state="error")
                return None
            s.update(label="Data Received", state="complete")
            return res.json()
        except: return None

# --- 6. AUTH & MAIN UI ---
# (Auth code remains identical to previous version)
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
            except: st.error("Login failed")
    st.stop()

t_radar, t_search = st.tabs(["📡 LIVE RADAR", "🔎 FLIGHT SEARCH"])

with t_radar:
    fleet = get_fleet_telemetry()
    c_map, c_data = st.columns([3, 1])
    with c_map:
        m = folium.Map(location=[1.35, 103.98], zoom_start=3, tiles='CartoDB dark_matter')
        for ac in fleet:
            popup = f"SQ {ac['Callsign']} | {ac['Alt (ft)']}ft | Mach {ac['Mach']}"
            folium.Marker([ac['Lat'], ac['Lon']], popup=popup, icon=folium.Icon(color='orange')).add_to(m)
        st_folium(m, width="100%", height=500, key="radar_locked")
    with c_data:
        st.metric("Total SIA Airborne", len(fleet))
        st.dataframe(pd.DataFrame(fleet).drop(['Lat', 'Lon'], axis=1), hide_index=True)

with t_search:
    st.markdown('<div class="search-card">', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    f_num = c1.text_input("Flight Number", "317")
    f_date = c2.date_input("Departure Date")
    if st.button("RETRIEVE STATUS"):
        res = call_sia_throttled("getbynumber", {
            "airlineCode": "SQ", "flightNumber": f_num, 
            "scheduledDepartureDate": f_date.strftime("%Y-%m-%d")
        })
        if res and res.get("status") == "SUCCESS":
            render_flight_card(res.get("data"))
        else: st.error("Flight not found or Rate Limit hit.")
    st.markdown('</div>', unsafe_allow_html=True)
