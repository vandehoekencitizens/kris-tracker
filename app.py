import streamlit as st
import requests, uuid, folium, math, time, pandas as pd
from streamlit_folium import st_folium
from supabase import create_client
from datetime import datetime, timedelta

# --- 1. INITIALIZATION ---
st.set_page_config(page_title="KrisTracker Master", page_icon="✈️", layout="wide")

@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
supabase = init_supabase()

# --- 2. EXECUTIVE UI STYLES ---
SIA_NAVY, SIA_GOLD = "#00266B", "#BD9B60"
st.markdown(f"""<style>
    .stApp {{ background-color: white; color: {SIA_NAVY}; }}
    [data-testid="stSidebar"] {{ background-color: {SIA_NAVY} !important; }}
    [data-testid="stSidebar"] * {{ color: white !important; }}
    .flight-box {{ background: {SIA_NAVY}; color: white; padding: 25px; border-radius: 12px; border-left: 10px solid {SIA_GOLD}; margin-bottom: 20px; }}
    .status-badge {{ background: {SIA_GOLD}; color: {SIA_NAVY}; padding: 4px 12px; border-radius: 20px; font-weight: bold; font-size: 11px; }}
    .countdown-timer {{ background: rgba(189, 155, 96, 0.15); padding: 12px; border-radius: 8px; margin: 15px 0; border: 1px dashed {SIA_GOLD}; font-family: 'Courier New', monospace; text-align: center; color: {SIA_GOLD}; font-weight: bold; }}
    .telemetry-footer {{ background: rgba(255,255,255,0.05); padding: 10px; border-radius: 0 0 8px 8px; margin-top: 15px; font-family: monospace; font-size: 12px; border-top: 1px solid rgba(255,255,255,0.1); }}
</style>""", unsafe_allow_html=True)

# --- 3. PHYSICS & TIME ENGINES ---
def get_mach(gs_mps, alt_m):
    if not gs_mps or gs_mps < 1: return 0.0
    return round(gs_mps / (20.046 * math.sqrt(288.15 - (0.0065 * alt_m))), 2)

def get_countdown(iso_time_str):
    try:
        target = datetime.fromisoformat(iso_time_str.replace('Z', ''))
        diff = target - datetime.now()
        if diff.total_seconds() < 0: return "🏃 FLIGHT DEPARTED"
        hours, remainder = divmod(int(diff.total_seconds()), 3600)
        minutes, _ = divmod(remainder, 60)
        return f"⏳ {hours}h {minutes}m UNTIL DEPARTURE"
    except: return "🕒 TIME PENDING"

# --- 4. DATA API ENGINES ---
def get_airlabs_data(f_num):
    api_key = st.secrets['AIRLABS_API_KEY']
    for mode in ["flight", "schedules"]:
        url = f"https://airlabs.co/api/v9/{mode}?flight_number=SQ{f_num}&api_key={api_key}"
        try:
            res = requests.get(url, timeout=5).json()
            data = res.get("response")
            if data: return data[0] if isinstance(data, list) else data
        except: continue
    return None

def call_sia_gateway(endpoint, payload):
    url = f"https://apigw.singaporeair.com/api/uat/v2/flightstatus/{endpoint}"
    headers = {"api_key": st.secrets["SIA_STATUS_KEY"], "x-csl-client-id": "SPD", "x-csl-client-uuid": str(uuid.uuid4()), "Content-Type": "application/json"}
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=12)
        return res.json() if res.status_code == 200 else None
    except: return None

# --- 5. RENDERER (WITH TERMINAL TRANSLATION) ---
def render_flight_status(sia_data, force_fnum=None):
    flights = sia_data.get("data", {}).get("response", {}).get("flights", []) if sia_data else []
    live = get_airlabs_data(force_fnum) if force_fnum else None

    if not flights and not live:
        st.error(f"🛑 No live data for SQ{force_fnum}. Check flight number or date.")
        return

    # Failover to AirLabs if SIA Gateway is silent
    if not flights and live:
        flights = [{"legs": [{"flightNumber": force_fnum, "origin": {"airportCode": live.get("dep_iata")}, "destination": {"airportCode": live.get("arr_iata")}}]}]

    for f in flights:
        # Translate 'M' to 'Terminal 1' for KUL
        raw_terminal = f.get("origin", {}).get("airportTerminal", "TBA")
        display_terminal = "Terminal 1" if raw_terminal == "M" else raw_terminal
        
        for leg in f.get("legs", []):
            f_num = leg.get('flightNumber', force_fnum)
            status = (live.get("status") if live else leg.get("flightStatus", "Scheduled")).upper()
            countdown = get_countdown(leg.get("scheduledDepartureTime", ""))

            html = (
                f"<div class='flight-box'>"
                f"<div style='display:flex; justify-content:space-between;'>"
                f"<div><span class='status-badge'>{status}</span><h1 style='color:white; margin:10px 0;'>SQ {f_num}</h1></div>"
                f"<div style='text-align:right;'><b style='color:{SIA_GOLD};'>{live.get('model', 'SIA Jet') if live else 'Boeing 737-800'}</b><br><small>Tail: {live.get('reg_number', '9V-SIA') if live else '9V-SIA'}</small></div>"
                f"</div>"
                f"<div class='countdown-timer'>{countdown}</div>"
                f"<div style='display:flex; justify-content:space-between; align-items:center; margin-top:15px; background:white; color:{SIA_NAVY}; padding:20px; border-radius:8px;'>"
                f"<div style='text-align:center; flex:1;'><div style='font-size:2em; font-weight:bold;'>{leg.get('origin', {}).get('airportCode')}</div><div>{display_terminal}</div></div>"
                f"<div style='flex:1; text-align:center; font-size:2.2em; opacity:0.15;'>✈️</div>"
                f"<div style='text-align:center; flex:1;'><div style='font-size:2em; font-weight:bold;'>{leg.get('destination', {}).get('airportCode')}</div><div>Gate: {live.get('arr_gate', 'TBA') if live else 'TBA'}</div></div>"
                f"</div>"
                f"<div class='telemetry-footer'>📡 Telemetry: Spd {live.get('speed', '0') if live else '---'}km/h | Mach {get_mach(live.get('speed', 0)*0.27, 10000) if live else '---'}</div>"
                f"</div>"
            )
            st.markdown(html, unsafe_allow_html=True)

# --- 6. AUTH & TABS ---
if "user" not in st.session_state:
    st.title("KrisTracker Executive Portal")
    with st.form("Login"):
        if st.form_submit_button("SIGN IN AS AUTHORIZED USER"):
            st.session_state.user = True # Simplified for testing
            st.rerun()
    st.stop()

t_radar, t_num, t_route = st.tabs(["📡 RADAR", "🔎 FLIGHT #", "✈️ ROUTE"])

with t_radar:
    m = folium.Map(location=[2.74, 101.70], zoom_start=8, tiles='CartoDB dark_matter')
    st_folium(m, width="100%", height=500)

with t_num:
    c1, c2 = st.columns(2)
    f_in = c1.text_input("Flight #", "115")
    d_in = c2.date_input("Departure Date")
    if st.button("EXECUTE LIVE TRACK"):
        res = call_sia_gateway("getbynumber", {"airlineCode": "SQ", "flightNumber": f_in, "scheduledDepartureDate": str(d_in)})
        render_flight_status(res, force_fnum=f_in)

with t_route:
    c1, c2, c3 = st.columns(3)
    o, d, dt = c1.text_input("From", "KUL"), c2.text_input("To", "SIN"), c3.date_input("Date", key="rt_date")
    if st.button("SEARCH ROUTE"):
        res = call_sia_gateway("getbyroute", {"originAirportCode": o.upper(), "destinationAirportCode": d.upper(), "scheduledDepartureDate": str(dt)})
        render_flight_status(res)
