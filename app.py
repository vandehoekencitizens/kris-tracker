import streamlit as st
import requests, uuid, folium, math, time, pandas as pd
from streamlit_folium import st_folium
from supabase import create_client

# --- 1. INITIALIZATION & AUTH ---
st.set_page_config(page_title="KrisTracker Pro", page_icon="✈️", layout="wide")

@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
supabase = init_supabase()

# --- 2. EXECUTIVE THEME ---
SIA_NAVY, SIA_GOLD = "#00266B", "#BD9B60"
st.markdown(f"""<style>
    .stApp {{ background-color: white; }}
    [data-testid="stSidebar"] {{ background-color: {SIA_NAVY} !important; }}
    [data-testid="stSidebar"] * {{ color: white !important; }}
    .error-box {{ padding: 25px; background: #FFF5F5; border: 2px solid #FF4B4B; border-radius: 8px; color: #FF4B4B; text-align: center; font-weight: bold; margin: 20px 0; }}
</style>""", unsafe_allow_html=True)

# --- 3. SIDEBAR OP-CENTER (OLD FEATURES RETAINED) ---
st.sidebar.title("🛠 OP-CENTER")
api_source = st.sidebar.radio("Data Intelligence Source", ["SIA Official", "AirLabs Enhanced"])
debug_enabled = st.sidebar.toggle("Enable Debug Mode", value=False)

def log_debug(title, content):
    if debug_enabled:
        with st.sidebar.expander(f"DEBUG: {title}"): st.write(content)

# --- 4. PHYSICS & RADAR ENGINES (OLD FEATURES RETAINED) ---
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
    except: return []

# --- 5. AIRLABS BACKUP ---
def get_airlabs_data(f_num):
    try:
        url = f"https://airlabs.co/api/v9/flight?flight_icao=SQ{f_num}&api_key={st.secrets['AIRLABS_API_KEY']}"
        res = requests.get(url, timeout=5).json()
        if "response" in res and res["response"]:
            d = res["response"]
            return {"reg": d.get("reg_number", "9V-???"), "model": d.get("model", "SIA Aircraft"), "delay": d.get("dep_delayed", 0)}
    except: return None

# --- 6. CLEAN RENDERER (FIXED RENDER BUG) ---
def render_flight_status(data):
    # Check if data or flights list is missing
    flights = data.get("response", {}).get("flights", []) if data else []
    if not flights:
        st.markdown('<div class="error-box">⚠️ FLIGHT NOT FOUND<br><small>This flight is not active in the SIA system for the selected date.</small></div>', unsafe_allow_html=True)
        return
    
    for f in flights:
        for leg in f.get("legs", []):
            f_num = leg.get('flightNumber', '---')
            ac_type = leg.get('aircraft', {}).get('displayName', "Singapore Airlines")
            reg = leg.get('aircraft', {}).get('registrationNumber', "TRACKING")
            delay_html = ""

            # Fetch AirLabs Data if Switch is On
            if api_source == "AirLabs Enhanced":
                with st.spinner("Sourcing satellite metadata..."):
                    backup = get_airlabs_data(f_num)
                    if backup:
                        ac_type, reg = backup['model'], backup['reg']
                        if backup['delay']: delay_html = f"<div style='color:#FF4B4B;font-weight:bold;'>Delayed: {backup['delay']}m</div>"

            # Constructing HTML as a flat string to avoid Streamlit's "Raw Code" glitch
            card_html = (
                f"<div style='background:{SIA_NAVY}; color:white; padding:30px; border-radius:12px; border-left:10px solid {SIA_GOLD}; margin-bottom:20px;'>"
                f"<div style='display:flex; justify-content:space-between;'>"
                f"<div><span style='background:{SIA_GOLD}; color:{SIA_NAVY}; padding:4px 12px; border-radius:20px; font-weight:bold; font-size:12px;'>{leg.get('flightStatus', 'LIVE')}</span>"
                f"<h1 style='color:white; margin:15px 0 5px 0; font-size:40px;'>SQ {f_num}</h1></div>"
                f"<div style='text-align:right;'><small>AIRCRAFT / TAIL</small><br><b style='color:{SIA_GOLD}; font-size:18px;'>{ac_type}</b><br><b>{reg}</b>{delay_html}</div>"
                f"</div><div style='display:flex; justify-content:space-between; align-items:center; margin-top:30px; background:white; color:{SIA_NAVY}; padding:20px; border-radius:6px;'>"
                f"<div style='text-align:center; flex:1;'><div style='font-size:35px; font-weight:bold;'>{leg['origin']['airportCode']}</div><div>{leg['scheduledDepartureTime'].split('T')[1][:5]}</div></div>"
                f"<div style='flex:1; text-align:center; font-size:30px; opacity:0.2;'>✈️</div>"
                f"<div style='text-align:center; flex:1;'><div style='font-size:35px; font-weight:bold;'>{leg['destination']['airportCode']}</div><div>{leg['scheduledArrivalTime'].split('T')[1][:5]}</div></div>"
                f"</div></div>"
            )
            st.markdown(card_html, unsafe_allow_html=True)

def call_sia_gateway(endpoint, payload):
    url = f"https://apigw.singaporeair.com/api/uat/v2/flightstatus/{endpoint}"
    headers = {"api_key": st.secrets["SIA_STATUS_KEY"], "x-csl-client-id": "SPD", "x-csl-client-uuid": str(uuid.uuid4()), "Content-Type": "application/json"}
    try:
        time.sleep(1.2)
        res = requests.post(url, json=payload, headers=headers, timeout=12)
        log_debug(f"API {endpoint}", res.json())
        return res.json() if res.status_code == 200 else None
    except: return None

# --- 7. LOGIN GATE (OLD FEATURE RETAINED) ---
if "user" not in st.session_state:
    st.title("KrisTracker Executive Portal")
    with st.form("Login"):
        em, pw = st.text_input("Email"), st.text_input("Password", type="password")
        if st.form_submit_button("SIGN IN"):
            try:
                res = supabase.auth.sign_in_with_password({"email": em, "password": pw})
                st.session_state.user = res.user
                st.rerun()
            except: st.error("Access Denied.")
    st.stop()

# --- 8. DASHBOARD TABS ---
t_radar, t_num, t_route = st.tabs(["📡 LIVE RADAR", "🔎 FLIGHT NUMBER", "✈️ ROUTE SEARCH"])

with t_radar:
    fleet = get_fleet_radar()
    if not fleet:
        st.error("📡 Telemetry Offline. Searching enabled via SIA Gateway.")
    else:
        c1, c2 = st.columns([3, 1])
        with c1:
            m = folium.Map(location=[1.35, 103.98], zoom_start=3, tiles='CartoDB dark_matter')
            for ac in fleet:
                folium.Marker([ac['Lat'], ac['Lon']], popup=f"SQ {ac['Callsign']} | Mach {ac['Mach']}", icon=folium.Icon(color='orange')).add_to(m)
            st_folium(m, width="100%", height=500, key="radar_main")
        with c2:
            st.metric("SIA Airborne", len(fleet))
            st.dataframe(pd.DataFrame(fleet).drop(columns=['Lat', 'Lon']), hide_index=True)

with t_num:
    with st.container(border=True):
        c1, c2 = st.columns(2)
        f_in, d_in = c1.text_input("Flight #", "317"), c2.date_input("Departure Date")
        if st.button("TRACK BY NUMBER"):
            res = call_sia_gateway("getbynumber", {"airlineCode": "SQ", "flightNumber": f_in, "scheduledDepartureDate": str(d_in)})
            render_flight_status(res.get("data") if res else None)

with t_route:
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        o, d, dr = c1.text_input("From", "SIN"), c2.text_input("To", "LHR"), c3.date_input("Date", key="rt_date")
        if st.button("TRACK BY ROUTE"):
            res = call_sia_gateway("getbyroute", {"originAirportCode": o.upper(), "destinationAirportCode": d.upper(), "scheduledDepartureDate": str(dr)})
            render_flight_status(res.get("data") if res else None)
