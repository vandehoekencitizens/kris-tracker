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
st.set_page_config(page_title="KrisTracker | Debug Mode", page_icon="✈️", layout="wide")

@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- 2. EXECUTIVE THEME ---
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
    .stButton>button {{ background-color: {SIA_NAVY} !important; color: white !important; font-weight: bold; border-radius: 4px; }}
    .debug-box {{ background-color: #f0f2f6; padding: 10px; border-radius: 5px; font-family: monospace; font-size: 12px; color: black; }}
    </style>
    """, unsafe_allow_html=True)

# --- 3. DEBUG & LOGGING ---
st.sidebar.title("🛠 OP-CENTER")
debug_mode = st.sidebar.toggle("Enable Debug Mode", value=False)

def log_debug(title, content):
    if debug_mode:
        with st.expander(f"DEBUG: {title}", expanded=True):
            st.code(content)

# --- 4. AVIATION & RADAR ---
def get_mach(gs_mps, alt_m):
    if not gs_mps or gs_mps < 1 or not alt_m: return 0.0
    temp_k = 288.15 - (0.0065 * alt_m)
    return gs_mps / (20.046 * math.sqrt(temp_k))

@st.cache_data(ttl=60)
def get_fleet_cached():
    url = "https://opensky-network.org/api/states/all"
    auth = (st.secrets["OPENSKY_CLIENT_ID"], st.secrets["OPENSKY_CLIENT_SECRET"])
    try:
        r = requests.get(url, auth=auth, timeout=10)
        log_debug("OpenSky Raw Status", f"Status Code: {r.status_code}")
        states = r.json().get("states", [])
        sia_flights = []
        for s in states:
            callsign = str(s[1]).strip() if s[1] else ""
            if callsign.startswith("SIA") or callsign.startswith("SQ"):
                sia_flights.append({
                    "Callsign": callsign, "Reg": s[0].upper(), "Lat": s[6], "Lon": s[5],
                    "Alt (ft)": int(s[7] * 3.28) if s[7] else 0,
                    "GS (kts)": int(s[9] * 1.94) if s[9] else 0,
                    "Mach": round(get_mach(s[9], s[7]), 2)
                })
        return sia_flights
    except Exception as e:
        log_debug("OpenSky Error", str(e))
        return []

# --- 5. SIA API (With Dynamic Path Testing) ---
def call_sia_api(endpoint_suffix, payload):
    # Testing the path from your provided Postman collection: /api/uat/v2/
    url = f"https://apigw.singaporeair.com/api/uat/v2/flightstatus/{endpoint_suffix}"
    headers = {
        "Content-Type": "application/json",
        "api_key": st.secrets["SIA_STATUS_KEY"],
        "x-csl-client-uuid": str(uuid.uuid4())
    }
    
    log_debug("SIA API Request", f"URL: {url}\nPayload: {payload}")
    
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        log_debug("SIA API Response Header", f"Status: {res.status_code}\nContent-Type: {res.headers.get('Content-Type')}")
        
        if "application/json" in res.headers.get("Content-Type", ""):
            return res.json()
        else:
            return {"status": "FAILURE", "message": "Server returned HTML (Likely 404 or 596)", "raw": res.text[:500]}
    except Exception as e:
        return {"status": "FAILURE", "message": str(e)}

# --- 6. AUTH GATE ---
if "user" not in st.session_state:
    st.title("KrisTracker Executive Login")
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

# --- 7. MAIN INTERFACE ---
st.title("Flight Operations Command")
tab_radar, tab_route = st.tabs(["📡 LIVE RADAR", "✈️ STATUS SEARCH"])

with tab_radar:
    fleet = get_fleet_cached()
    col_m, col_s = st.columns([3, 1])
    with col_m:
        m = folium.Map(location=[1.35, 103.98], zoom_start=3, tiles='CartoDB dark_matter')
        for ac in fleet:
            if ac['Lat']:
                folium.Marker([ac['Lat'], ac['Lon']], popup=f"SQ {ac['Callsign']}", icon=folium.Icon(color='orange')).add_to(m)
        st_folium(m, width="100%", height=500, key="radar_final")
    with col_s:
        st.metric("Airborne SIA", len(fleet))
        if fleet:
            st.dataframe(pd.DataFrame(fleet).drop(['Lat', 'Lon'], axis=1), hide_index=True)
        else:
            st.warning("No Telemetry Found")

with tab_route:
    st.markdown('<div class="search-card">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    orig, dest = c1.text_input("Origin", "SIN"), c2.text_input("Destination", "LHR")
    date = c3.date_input("Date")
    if st.button("SEARCH FLIGHTS"):
        res = call_sia_api("getbyroute", {
            "originAirportCode": orig.upper(), 
            "destinationAirportCode": dest.upper(), 
            "scheduledDepartureDate": str(date)
        })
        if res.get("status") == "SUCCESS":
            st.success("Results Received")
            st.json(res.get("data"))
        else:
            st.error(f"Search failed: {res.get('message')}")
            if debug_mode: st.write(res)
    st.markdown('</div>', unsafe_allow_html=True)
