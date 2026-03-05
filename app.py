import streamlit as st
import requests, uuid, folium, math, time, pandas as pd
from streamlit_folium import st_folium
from supabase import create_client

# --- 1. INITIALIZATION ---
st.set_page_config(page_title="KrisTracker Executive", page_icon="✈️", layout="wide")

@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
supabase = init_supabase()

# --- 2. THEME & GLOBAL STYLE ---
SIA_NAVY, SIA_GOLD = "#00266B", "#BD9B60"
st.markdown(f"""
    <style>
    .stApp {{ background-color: white; }}
    [data-testid="stSidebar"] {{ background-color: {SIA_NAVY} !important; }}
    [data-testid="stSidebar"] * {{ color: white !important; }}
    .stTabs [data-baseweb="tab-list"] {{ gap: 24px; }}
    .stTabs [data-baseweb="tab"] {{ height: 50px; white-space: pre-wrap; background-color: #f0f2f6; border-radius: 4px 4px 0 0; padding: 10px 20px; }}
    .stTabs [aria-selected="true"] {{ background-color: {SIA_GOLD} !important; color: {SIA_NAVY} !important; }}
    </style>
    """, unsafe_allow_html=True)

# --- 3. OP-CENTER (SIDEBAR) ---
st.sidebar.title("🛠 OP-CENTER")
api_source = st.sidebar.radio("Data Intelligence Source", ["SIA Official", "AirLabs Enhanced"])
debug_enabled = st.sidebar.toggle("Enable Debug Mode", value=False)

def log_debug(title, content):
    if debug_enabled:
        with st.sidebar.expander(f"DEBUG: {title}"): st.write(content)

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
                    "Callsign": s[1].strip(), "Reg": s[0].upper(), "Lat": s[6], "Lon": s[5],
                    "Alt (ft)": int(alt * 3.28), "GS (kts)": int(gs * 1.94), "Mach": round(get_mach(gs, alt), 2)
                })
        return sia
    except: return "OFFLINE"

# --- 5. DATA FALLBACKS ---
def get_airlabs_data(f_num):
    try:
        url = f"https://airlabs.co/api/v9/flight?flight_icao=SQ{f_num}&api_key={st.secrets['AIRLABS_API_KEY']}"
        res = requests.get(url, timeout=5).json().get('response', {})
        return {"reg": res.get("reg_number", "9V-TBA"), "model": res.get("model", "SIA Aircraft"), "delay": res.get("dep_delayed")}
    except: return None

# --- 6. RENDERER (FIXED: NO BLANK CARDS) ---
def render_flight_status(data):
    flights = data.get("response", {}).get("flights", [])
    if not flights:
        st.warning("No live flight data found.")
        return
    
    for f in flights:
        for leg in f.get("legs", []):
            f_num = leg.get('flightNumber', '0')
            ac_type = leg.get('aircraft', {}).get('displayName', "Singapore Airlines")
            reg = leg.get('aircraft', {}).get('registrationNumber', "TRACKING")
            delay_info = ""

            if api_source == "AirLabs Enhanced":
                backup = get_airlabs_data(f_num)
                if backup:
                    ac_type, reg = backup['model'], backup['reg']
                    if backup['delay']: 
                        delay_info = f"<div style='color:#FF4B4B; font-weight:bold;'>Delayed: {backup['delay']}m</div>"

            # THE CARD (Using inline-block and fixed colors to ensure visibility)
            st.write(f"""
                <div style="background-color:{SIA_NAVY}; color:white; padding:30px; border-radius:12px; border-left:10px solid {SIA_GOLD}; margin-bottom:25px; font-family:sans-serif;">
                    <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                        <div>
                            <span style="background-color:{SIA_GOLD}; color:{SIA_NAVY}; padding:5px 15px; border-radius:20px; font-weight:bold; font-size:12px;">{leg.get('flightStatus', 'SCHEDULED')}</span>
                            <h1 style="margin:15px 0 5px 0; font-size:42px; color:white;">SQ {f_num}</h1>
                            <div style="opacity:0.8;">{leg.get('operatingAirlineName', 'Singapore Airlines')}</div>
                        </div>
                        <div style="text-align:right;">
                            <div style="color:{SIA_GOLD}; font-size:14px; text-transform:uppercase;">Aircraft Details</div>
                            <div style="font-size:20px; font-weight:bold; margin:5px 0;">{ac_type}</div>
                            <div style="font-size:16px; opacity:0.9;">Tail: {reg}</div>
                            {delay_info}
                        </div>
                    </div>
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-top:40px; background-color:rgba(255,255,255,0.05); padding:20px; border-radius:8px;">
                        <div style="text-align:center; flex:1;">
                            <div style="font-size:48px; font-weight:bold; color:white;">{leg['origin']['airportCode']}</div>
                            <div style="font-size:18px; color:{SIA_GOLD}; font-weight:bold;">{leg['scheduledDepartureTime'].split('T')[1][:5]}</div>
                        </div>
                        <div style="font-size:40px; flex:1; text-align:center; opacity:0.3;">✈️</div>
                        <div style="text-align:center; flex:1;">
                            <div style="font-size:48px; font-weight:bold; color:white;">{leg['destination']['airportCode']}</div>
                            <div style="font-size:18px; color:{SIA_GOLD}; font-weight:bold;">{leg['scheduledArrivalTime'].split('T')[1][:5]}</div>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

# --- 7. SIA GATEWAY ---
def call_sia_gateway(endpoint, payload):
    time.sleep(1.2)
    url = f"https://apigw.singaporeair.com/api/uat/v2/flightstatus/{endpoint}"
    headers = {"api_key": st.secrets["SIA_STATUS_KEY"], "x-csl-client-id": "SPD", "x-csl-client-uuid": str(uuid.uuid4()), "Content-Type": "application/json"}
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=12)
        log_debug(f"API {endpoint}", res.json())
        return res.json() if res.status_code == 200 else None
    except: return None

# --- 8. AUTH ---
if "user" not in st.session_state:
    with st.container():
        st.title("KrisTracker Executive Portal")
        with st.form("login_form"):
            em, pw = st.text_input("Email"), st.text_input("Password", type="password")
            if st.form_submit_button("LOGIN"):
                try:
                    res = supabase.auth.sign_in_with_password({"email": em.lower(), "password": pw})
                    st.session_state.user = res.user
                    st.rerun()
                except: st.error("Authentication Failed")
    st.stop()

# --- 9. MAIN INTERFACE ---
t_radar, t_num, t_route = st.tabs(["📡 LIVE RADAR", "🔎 FLIGHT NUMBER", "✈️ ROUTE SEARCH"])

with t_radar:
    fleet = get_fleet_radar()
    if fleet == "OFFLINE":
        st.error("Radar Data Offline. Search Functions Active.")
    else:
        c_m, c_l = st.columns([3, 1])
        with c_m:
            m = folium.Map(location=[1.35, 103.98], zoom_start=3, tiles='CartoDB dark_matter')
            for ac in (fleet or []):
                folium.Marker([ac['Lat'], ac['Lon']], popup=f"SQ {ac['Callsign']} | Mach {ac['Mach']}", icon=folium.Icon(color='orange')).add_to(m)
            st_folium(m, width="100%", height=500, key="radar_fixed_final")
        with c_l:
            st.metric("SIA Airborne", len(fleet) if isinstance(fleet, list) else 0)
            if isinstance(fleet, list) and fleet:
                st.dataframe(pd.DataFrame(fleet).drop(columns=['Lat', 'Lon']), hide_index=True)

with t_num:
    with st.container(border=True):
        c1, c2 = st.columns(2)
        f_in = c1.text_input("Flight Number", "317")
        d_in = c2.date_input("Departure Date")
        if st.button("TRACK FLIGHT"):
            res = call_sia_gateway("getbynumber", {"airlineCode": "SQ", "flightNumber": f_in, "scheduledDepartureDate": str(d_in)})
            if res: render_flight_status(res.get("data"))

with t_route:
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        o, d = c1.text_input("From", "SIN"), c2.text_input("To", "LHR")
        dr = c3.date_input("Date", key="dr_route")
        if st.button("TRACK ROUTE"):
            res = call_sia_gateway("getbyroute", {"originAirportCode": o.upper(), "destinationAirportCode": d.upper(), "scheduledDepartureDate": str(dr)})
            if res: render_flight_status(res.get("data"))
