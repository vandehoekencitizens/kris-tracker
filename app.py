import streamlit as st
import requests
import uuid
import folium
import pandas as pd
import os
from streamlit_folium import st_folium
from supabase import create_client

# --- 1. INITIALIZATION ---
st.set_page_config(page_title="KrisTracker | Singapore Airlines", page_icon="✈️", layout="wide")

@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- 2. THEME & LOGO ---
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
        font-weight: bold; border-radius: 4px; border: none; height: 45px; width: 100%;
    }}
    .sidebar-logo {{ display: flex; justify-content: center; padding: 20px 0; }}
    .sidebar-logo svg {{ width: 200px; height: auto; fill: white; }}
    </style>
    """, unsafe_allow_html=True)

# --- 3. RADAR LOGIC (Using OpenSky Secrets) ---
@st.cache_data(ttl=120)
def get_fleet_cached():
    url = "https://opensky-network.org/api/states/all"
    auth = (st.secrets["OPENSKY_CLIENT_ID"], st.secrets["OPENSKY_CLIENT_SECRET"])
    try:
        r = requests.get(url, auth=auth, timeout=10)
        data = r.json().get("states", [])
        sia_flights = []
        for s in data:
            callsign = str(s[1]).strip() if s[1] else ""
            if callsign.startswith("SIA"):
                sia_flights.append({
                    "Callsign": callsign,
                    "Reg": s[0].upper(),
                    "Lat": s[6], "Lon": s[5],
                    "Alt (ft)": int(s[7] * 3.28) if s[7] else 0,
                    "GS (kts)": int(s[9] * 1.94) if s[9] else 0
                })
        return sia_flights
    except:
        return []

# --- 4. SIA API CALLER (Using SIA_STATUS_KEY) ---
def call_sia_status(endpoint, payload):
    # Mapping to your specific secret name
    api_key = st.secrets.get("SIA_STATUS_KEY")
    if not api_key:
        st.error("Missing SIA_STATUS_KEY in secrets!")
        return None

    url = f"https://apigw.singaporeair.com/api/v1/flightstatus/{endpoint}"
    headers = {
        "Content-Type": "application/json",
        "api_key": api_key,
        "x-csl-client-uuid": str(uuid.uuid4())
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)
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
        if st.button("LOGIN"):
            try:
                resp = supabase.auth.sign_in_with_password({"email": em.lower().strip(), "password": pw})
                st.session_state["user"] = resp.user
                st.rerun()
            except:
                st.error("Login failed. Check credentials.")
    st.stop()

# --- 6. DASHBOARD ---
st.sidebar.write(f"Active Session: **{st.session_state.user.email}**")
if st.sidebar.button("Logout"):
    supabase.auth.sign_out(); del st.session_state["user"]; st.rerun()

t_radar, t_status = st.tabs(["📡 LIVE NETWORK RADAR", "🔎 FLIGHT SEARCH"])

with t_radar:
    col_map, col_list = st.columns([2, 1])
    fleet = get_fleet_cached()
    
    with col_map:
        m = folium.Map(location=[1.35, 103.98], zoom_start=3, tiles='CartoDB dark_matter')
        for ac in fleet:
            if ac['Lat'] and ac['Lon']:
                folium.Marker(
                    [ac['Lat'], ac['Lon']], 
                    popup=f"SQ {ac['Callsign']}<br>Reg: {ac['Reg']}", 
                    icon=folium.Icon(color='orange', icon='plane')
                ).add_to(m)
        st_folium(m, width="100%", height=500, key="radar")

    with col_list:
        st.metric("SIA Airborne", len(fleet))
        if fleet:
            df = pd.DataFrame(fleet).drop(['Lat', 'Lon'], axis=1)
            st.dataframe(df, hide_index=True)

with t_status:
    st.markdown('<div class="search-card">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    orig = c1.text_input("Origin", "SIN")
    dest = c2.text_input("Destination", "KUL")
    date = c3.date_input("Date")
    if st.button("SEARCH FLIGHT STATUS"):
        res = call_sia_status("getbyroute", {
            "originAirportCode": orig.upper(),
            "destinationAirportCode": dest.upper(),
            "scheduledDepartureDate": str(date)
        })
        if res and res.get("status") == "SUCCESS":
            st.success("Flights Found")
            st.write(res.get("data"))
        else:
            st.error("API Error: Verify your SIA_STATUS_KEY and Route.")
    st.markdown('</div>', unsafe_allow_html=True)
