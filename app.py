import streamlit as st
import requests, uuid, folium, math, time, pandas as pd
from streamlit_folium import st_folium
from supabase import create_client
from datetime import datetime, timedelta

# --- 1. INITIALIZATION & AUTH ---
st.set_page_config(page_title="KrisTracker Master", page_icon="✈️", layout="wide")

@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
supabase = init_supabase()

# --- 2. THEME & SCREENSHOT-ACCURATE CSS ---
SIA_NAVY, SIA_GOLD = "#00266B", "#BD9B60"
st.markdown(f"""<style>
    .stApp {{ background-color: #f9f9f9; color: {SIA_NAVY}; }}
    [data-testid="stSidebar"] {{ background-color: {SIA_NAVY} !important; }}
    [data-testid="stSidebar"] * {{ color: white !important; }}
    .layover-divider {{ border-top: 1px solid #ddd; margin: 25px 0; position: relative; }}
    .layover-text {{ background: #f9f9f9; padding: 0 15px; position: absolute; top: -12px; left: 50px; font-size: 14px; color: #666; display: flex; align-items: center; }}
    .search-card {{ background: white; padding: 25px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); border-top: 4px solid {SIA_GOLD}; margin-bottom: 25px; }}
</style>""", unsafe_allow_html=True)

# --- 3. RETAINED CORE ENGINES (Physics & Data) ---
def get_mach(gs_mps, alt_m):
    """Retained: Original Mach Logic"""
    if not gs_mps or gs_mps < 1: return 0.0
    return round(gs_mps / (20.046 * math.sqrt(288.15 - (0.0065 * alt_m))), 2)

def get_airlabs_data(f_num):
    """Retained: AirLabs Failover"""
    api_key = st.secrets['AIRLABS_API_KEY']
    url = f"https://airlabs.co/api/v9/schedules?flight_number=SQ{f_num}&api_key={api_key}"
    try:
        res = requests.get(url, timeout=5).json()
        return res.get("response") if res.get("response") else None
    except: return None

def call_sia_gateway(endpoint, payload):
    """Retained: Documentation-compliant SIA Caller"""
    url = f"https://apigw.singaporeair.com/api/uat/v2/flightstatus/{endpoint}"
    headers = {
        "api_key": st.secrets["SIA_STATUS_KEY"], 
        "x-csl-client-id": "SPD", 
        "x-csl-client-uuid": str(uuid.uuid4()), 
        "Content-Type": "application/json"
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=12)
        return res.json() if res.status_code == 200 else None
    except: return None

# --- 4. RENDERER (Screenshot Accurate + Layover Logic) ---
def render_flight_status(sia_data, force_fnum=None):
    flights = sia_data.get("data", {}).get("response", {}).get("flights", []) if sia_data else []
    
    if not flights:
        st.error(f"🛑 No live data for SQ{force_fnum}.")
        return

    for f in flights:
        origin_city = f.get("origin", {}).get("cityName", "Unknown")
        dest_city = f.get("destination", {}).get("cityName", "Unknown")
        
        # Screenshot Style Header
        st.markdown(f"<h2 style='color:{SIA_NAVY}; margin-bottom:0;'>SQ {force_fnum} - {origin_city} to {dest_city}</h2>", unsafe_allow_html=True)
        st.markdown("<p style='color:#666; font-size:14px; margin-bottom:20px;'>Schedules show the local time at each airport.</p>", unsafe_allow_html=True)
        
        # Main Card Container
        st.markdown('<div style="background:white; border:1px solid #eee; border-radius:4px; display:flex; box-shadow:0 2px 4px rgba(0,0,0,0.05);">', unsafe_allow_html=True)
        
        # Left Sidebar (Flight Number)
        st.markdown(f'<div style="flex:0 0 120px; border-right:1px solid #eee; display:flex; align-items:center; justify-content:center; padding:40px 0;"><h2 style="margin:0;">SQ {force_fnum}</h2></div>', unsafe_allow_html=True)
        
        # Right Content Area
        st.markdown('<div style="flex:1; padding:30px;">', unsafe_allow_html=True)
        
        legs = f.get("legs", [])
        for idx, leg in enumerate(legs):
            # Layover Logic (Screenshot #3)
            if idx > 0:
                layover_city = leg.get("origin", {}).get("cityName")
                st.markdown(f'<div class="layover-divider"><div class="layover-text">🕒 Layover at {layover_city}</div></div><br>', unsafe_allow_html=True)

            # Extract Times & Terminal Translation (KUL correction)
            dep_time = leg.get("scheduledDepartureTime")[-5:]
            arr_time = leg.get("scheduledArrivalTime")[-5:]
            dep_date = datetime.fromisoformat(leg.get("scheduledDepartureTime")).strftime("%a %d %b")
            
            dep_term = leg.get("origin", {}).get("airportTerminal", "1")
            if leg.get("origin", {}).get("airportCode") == "KUL" and dep_term == "M": dep_term = "1"

            # Leg HTML
            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:10px;">
                <div style="flex:1;">
                    <div style="color:{SIA_NAVY}; font-size:12px; font-weight:bold;">Scheduled</div>
                    <div style="display:flex; align-items:baseline; color:{SIA_NAVY};">
                        <span style="font-size:32px; font-weight:bold; margin-right:10px;">{leg.get('origin', {}).get('airportCode')}</span>
                        <span style="font-size:32px;">{dep_time}</span>
                    </div>
                    <div style="font-weight:bold; font-size:14px;">{leg.get('origin', {}).get('cityName')}</div>
                    <div style="font-size:13px; color:#666; margin-top:10px;">{dep_date}</div>
                    <div style="font-size:13px; color:#666;">{leg.get('origin', {}).get('airportName')}</div>
                    <div style="font-size:13px; color:#666;">Terminal {dep_term}</div>
                </div>
                <div style="flex:1; display:flex; flex-direction:column; align-items:center; padding-top:25px;">
                    <div style="width:100%; height:1px; background:#ddd; position:relative;"><span style="position:absolute; right:0; top:-12px; font-size:18px;">✈️</span></div>
                    <div style="margin-top:20px; color:#28a745; font-weight:bold; font-size:14px;">✔ {leg.get('flightStatus')}</div>
                </div>
                <div style="flex:1; padding-left:40px;">
                    <div style="color:{SIA_NAVY}; font-size:12px; font-weight:bold;">Scheduled</div>
                    <div style="display:flex; align-items:baseline; color:{SIA_NAVY};">
                        <span style="font-size:32px; font-weight:bold; margin-right:10px;">{leg.get('destination', {}).get('airportCode')}</span>
                        <span style="font-size:32px;">{arr_time}</span>
                    </div>
                    <div style="font-weight:bold; font-size:14px;">{leg.get('destination', {}).get('cityName')}</div>
                    <div style="font-size:13px; color:#666; margin-top:40px;">{leg.get('destination', {}).get('airportName')}</div>
                    <div style="font-size:13px; color:#666;">Terminal {leg.get('destination', {}).get('airportTerminal', '2')}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown('</div></div>', unsafe_allow_html=True)

# --- 5. AUTH & TABS ---
if "user" not in st.session_state:
    st.title("KrisTracker Executive Portal")
    with st.form("auth"):
        u, p = st.text_input("Email"), st.text_input("Password", type="password")
        if st.form_submit_button("LOGIN"):
            try:
                res = supabase.auth.sign_in_with_password({"email": u, "password": p})
                st.session_state.user = res.user
                st.rerun()
            except: st.error("Failed")
    st.stop()

t_radar, t_num, t_route = st.tabs(["📡 RADAR", "🔎 FLIGHT #", "✈️ ROUTE"])

with t_radar:
    m = folium.Map(location=[1.35, 103.98], zoom_start=3, tiles='CartoDB dark_matter')
    st_folium(m, width="100%", height=500)

with t_num:
    st.markdown('<div class="search-card">', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    f_in, d_in = c1.text_input("Flight #", "11"), c2.date_input("Date")
    if st.button("TRACK FLIGHT"):
        res = call_sia_gateway("getbynumber", {"airlineCode": "SQ", "flightNumber": f_in, "scheduledDepartureDate": str(d_in)})
        render_flight_status(res, force_fnum=f_in)
    st.markdown('</div>', unsafe_allow_html=True)

with t_route:
    st.markdown('<div class="search-card">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    o, d, dt = c1.text_input("From", "SIN"), c2.text_input("To", "LHR"), c3.date_input("Date", key="rt_date")
    if st.button("SEARCH ROUTE"):
        res = call_sia_gateway("getbyroute", {"originAirportCode": o.upper(), "destinationAirportCode": d.upper(), "scheduledDepartureDate": str(dt)})
        render_flight_status(res)
    st.markdown('</div>', unsafe_allow_html=True)
