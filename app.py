import streamlit as st
import requests, uuid, folium, math, time, pandas as pd
from streamlit_folium import st_folium
from supabase import create_client
from datetime import datetime, timedelta

# --- 1. INITIALIZATION ---
st.set_page_config(page_title="KrisTracker | Master Command", page_icon="✈️", layout="wide")

@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
supabase = init_supabase()

# --- 2. EXECUTIVE STYLING ---
SIA_NAVY, SIA_GOLD = "#00266B", "#BD9B60"
st.markdown(f"""<style>
    .stApp {{ background-color: white; color: {SIA_NAVY}; }}
    [data-testid="stSidebar"] {{ background-color: {SIA_NAVY} !important; }}
    [data-testid="stSidebar"] * {{ color: white !important; font-weight: 500; }}
    .flight-box {{ background: {SIA_NAVY}; color: white; padding: 25px; border-radius: 12px; border-left: 10px solid {SIA_GOLD}; margin-bottom: 20px; }}
    .status-badge {{ background: {SIA_GOLD}; color: {SIA_NAVY}; padding: 4px 12px; border-radius: 20px; font-weight: bold; font-size: 11px; }}
    .telemetry-footer {{ background: rgba(255,255,255,0.1); padding: 10px; border-radius: 0 0 8px 8px; margin-top: 15px; font-family: monospace; font-size: 12px; border-top: 1px solid rgba(255,255,255,0.2); }}
</style>""", unsafe_allow_html=True)

# --- 3. OP-CENTER (DEBUG & SOURCE CONTROLS) ---
st.sidebar.title("🛠 OP-CENTER")
api_source = st.sidebar.radio("Primary Intel Source", ["SIA Official", "AirLabs Enhanced"])
debug_enabled = st.sidebar.toggle("Enable Debug Mode", value=True)

def log_debug(title, content):
    if debug_enabled:
        with st.sidebar.expander(f"DEBUG: {title}"):
            st.write(content)

# --- 4. PHYSICS & PREDICTION ENGINES ---
def get_mach(gs_mps, alt_m):
    if not gs_mps or gs_mps < 1 or not alt_m: return 0.0
    return round(gs_mps / (20.046 * math.sqrt(288.15 - (0.0065 * alt_m))), 2)

def estimate_landing(speed_kph, dist_km):
    if not speed_kph or speed_kph < 100: return "N/A"
    eta_mins = (dist_km / speed_kph) * 60
    arrival = datetime.now() + timedelta(minutes=eta_mins)
    return arrival.strftime("%H:%M")

# --- 5. MULTI-SOURCE DATA ENGINE ---
def get_airlabs_live(f_num):
    try:
        url = f"https://airlabs.co/api/v9/flight?flight_icao=SQ{f_num}&api_key={st.secrets['AIRLABS_API_KEY']}"
        res = requests.get(url, timeout=5).json()
        log_debug("AirLabs API Response", res)
        return res.get("response")
    except: return None

def call_sia_gateway(endpoint, payload):
    url = f"https://apigw.singaporeair.com/api/uat/v2/flightstatus/{endpoint}"
    headers = {"api_key": st.secrets["SIA_STATUS_KEY"], "x-csl-client-id": "SPD", "x-csl-client-uuid": str(uuid.uuid4()), "Content-Type": "application/json"}
    try:
        time.sleep(1.2)
        res = requests.post(url, json=payload, headers=headers, timeout=12)
        log_debug(f"SIA {endpoint} Response", res.json())
        return res.json() if res.status_code == 200 else None
    except: return None

# --- 6. RENDERER (NO-LEAK DESIGN) ---
def render_flight_card(f_num, f_date):
    # 1. Try SIA first
    sia_res = call_sia_gateway("getbynumber", {"airlineCode": "SQ", "flightNumber": f_num, "scheduledDepartureDate": str(f_date)})
    flights = sia_res.get("data", {}).get("response", {}).get("flights", []) if sia_res else []
    
    # 2. Get AirLabs (Used for failover OR enrichment)
    live = get_airlabs_live(f_num)

    if not flights and not live:
        st.error(f"🛑 No data found for SQ{f_num}. Flight may not be active.")
        return

    # Data Construction
    leg = flights[0]['legs'][0] if flights else {}
    ac_type = live.get("model", leg.get("aircraft", {}).get("displayName", "SIA Aircraft"))
    reg = live.get("reg_number", leg.get("aircraft", {}).get("registrationNumber", "9V-???"))
    status = live.get("status", leg.get("flightStatus", "Scheduled")).upper()
    
    # Advanced Metrics
    speed = live.get("speed", 0) if live else 0
    eta = estimate_landing(speed, 500) if speed > 0 else "On Schedule"

    # HTML Construction (Minified to prevent code leak)
    html = [
        f"<div class='flight-box'>",
        f"<div style='display:flex; justify-content:space-between; align-items:flex-start;'>",
        f"<div><span class='status-badge'>{status}</span><h1 style='color:white; margin:10px 0;'>SQ {f_num}</h1></div>",
        f"<div style='text-align:right;'><b style='color:{SIA_GOLD};'>{ac_type}</b><br><small>Tail: {reg}</small></div>",
        f"</div>",
        f"<div style='display:flex; justify-content:space-between; align-items:center; margin-top:25px; background:white; color:{SIA_NAVY}; padding:15px; border-radius:6px;'>",
        f"<div style='text-align:center; flex:1;'><div style='font-size:2em; font-weight:bold;'>{leg.get('origin', {}).get('airportCode', 'SIN')}</div><div>Gate: {live.get('dep_gate', 'TBA') if live else 'TBA'}</div></div>",
        f"<div style='flex:1; text-align:center; font-size:2em; opacity:0.2;'>✈️</div>",
        f"<div style='text-align:center; flex:1;'><div style='font-size:2em; font-weight:bold;'>{leg.get('destination', {}).get('airportCode', '---')}</div><div>Gate: {live.get('arr_gate', 'TBA') if live else 'TBA'}</div></div>",
        f"</div>",
        f"<div class='telemetry-footer'>📡 TELEMETRY: Spd: {speed}km/h | Alt: {live.get('alt', '0')}ft | Est. Landing: {eta}</div>",
        f"</div>"
    ]
    st.markdown("".join(html), unsafe_allow_html=True)

# --- 7. AUTH GATE ---
if "user" not in st.session_state:
    st.title("KrisTracker Executive Login")
    with st.form("auth"):
        em, pw = st.text_input("Email"), st.text_input("Password", type="password")
        if st.form_submit_button("LOGIN"):
            try:
                res = supabase.auth.sign_in_with_password({"email": em, "password": pw})
                st.session_state.user = res.user
                st.rerun()
            except: st.error("Authentication Failed")
    st.stop()

# --- 8. TABS (RADAR & SEARCH) ---
t_radar, t_search = st.tabs(["📡 LIVE RADAR", "🔎 FLIGHT TRACKER"])

with t_radar:
    auth = (st.secrets["OPENSKY_CLIENT_ID"], st.secrets["OPENSKY_CLIENT_SECRET"])
    try:
        r = requests.get("https://opensky-network.org/api/states/all", auth=auth, timeout=5)
        states = r.json().get("states", [])
        fleet = []
        for s in states:
            if str(s[1]).strip().startswith("SIA"):
                fleet.append({"Callsign": s[1].strip(), "Reg": s[0].upper(), "Lat": s[6], "Lon": s[5], "Alt": int(s[7]*3.28), "Mach": get_mach(s[9], s[7])})
        
        c1, c2 = st.columns([3, 1])
        with c1:
            m = folium.Map(location=[1.35, 103.98], zoom_start=3, tiles='CartoDB dark_matter')
            for ac in fleet: folium.Marker([ac['Lat'], ac['Lon']], popup=f"{ac['Callsign']} | Mach {ac['Mach']}").add_to(m)
            st_folium(m, width="100%", height=500, key="radar_vFinal")
        with c2:
            st.metric("SIA Airborne", len(fleet))
            st.dataframe(pd.DataFrame(fleet).drop(columns=['Lat', 'Lon']), hide_index=True)
    except: st.error("Radar telemetry offline.")

with t_search:
    with st.container(border=True):
        c1, c2 = st.columns(2)
        f_in = c1.text_input("Flight #", "317")
        d_in = c2.date_input("Date")
        if st.button("TRACK FLIGHT"):
            render_flight_card(f_in, d_in)
