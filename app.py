import streamlit as st
import requests, uuid, folium, math, time
from streamlit_folium import st_folium
from supabase import create_client
from datetime import datetime

# --- 1. CONFIG & AUTH ---
st.set_page_config(page_title="KrisTracker Master", page_icon="✈️", layout="wide")

@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
supabase = init_supabase()

# --- 2. EXECUTIVE STYLING (RETAINED) ---
SIA_NAVY, SIA_GOLD = "#00266B", "#BD9B60"
st.markdown(f"""<style>
    .stApp {{ background-color: #f9f9f9; }}
    .flight-card {{ background: white; border-radius: 4px; border: 1px solid #eee; display: flex; box-shadow: 0 2px 8px rgba(0,0,0,0.05); margin-bottom: 25px; }}
    .sidebar-id {{ flex: 0 0 100px; border-right: 1px solid #eee; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 20px; color: {SIA_NAVY}; }}
    .main-body {{ flex: 1; padding: 25px; }}
    .layover-bar {{ background: #f0f2f6; padding: 8px 20px; font-size: 13px; color: #666; border-left: 4px solid {SIA_GOLD}; margin: 15px 0; }}
</style>""", unsafe_allow_html=True)

# --- 3. THE "FASTEST ADS-B" SELECTOR ---
def get_fastest_adsb(flight_num):
    """Pings both providers and returns the fastest successful response."""
    callsign = f"SIA{flight_num}".upper()
    endpoints = ["https://opendata.adsb.fi/api/v2/callsign/", "https://api.adsb.lol/v2/callsign/"]
    
    results = []
    for url in endpoints:
        try:
            start = time.perf_counter()
            resp = requests.get(f"{url}{callsign}", timeout=2)
            latency = time.perf_counter() - start
            if resp.status_code == 200 and resp.json().get("aircraft"):
                results.append({"data": resp.json()["aircraft"][0], "latency": latency})
        except: continue
    
    if not results: return None
    # Sort by latency and return the fastest
    return sorted(results, key=lambda x: x['latency'])[0]['data']

# --- 4. DATA ENGINES (PRIORITY RANKED) ---
def get_sia_data(f_num, date_str):
    url = "https://apigw.singaporeair.com/api/uat/v2/flightstatus/getbynumber"
    headers = {"api_key": st.secrets["SIA_STATUS_KEY"], "x-csl-client-id": "SPD", "x-csl-client-uuid": str(uuid.uuid4())}
    payload = {"airlineCode": "SQ", "flightNumber": f_num, "scheduledDepartureDate": date_str}
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=5).json()
        return res.get("data", {}).get("response", {}).get("flights", [None])[0]
    except: return None

def get_airlabs_data(f_num):
    url = f"https://airlabs.co/api/v9/schedules?flight_number=SQ{f_num}&api_key={st.secrets['AIRLABS_API_KEY']}"
    try:
        res = requests.get(url, timeout=5).json()
        return res.get("response")[0] if res.get("response") else None
    except: return None

# --- 5. THE MASTER RENDERER (TRIPLE-TIER PRIORITY) ---
def render_master_status(f_num, date_obj):
    # 1. Fetch all sources
    sia = get_sia_data(f_num, str(date_obj))
    airlab = get_airlabs_data(f_num)
    adsb = get_fastest_adsb(f_num)
    
    # 2. Determine Primary Info (Priority: SIA -> Airlab -> ADS-B)
    primary = sia if sia else airlab
    if not primary and not adsb:
        st.error("No flight data available across all providers.")
        return

    # 3. UI Construction (Screenshot Logic)
    origin_name = primary.get("origin", {}).get("cityName") if sia else (airlab.get("dep_city") if airlab else "Unknown")
    dest_name = primary.get("destination", {}).get("cityName") if sia else (airlab.get("arr_city") if airlab else "Unknown")
    
    st.markdown(f"<h2>SQ {f_num} - {origin_name} to {dest_name}</h2>", unsafe_allow_html=True)
    st.markdown("<p style='font-size:14px; color:#666;'>Priority-merged data from SIA, AirLabs, and Live ADS-B.</p>", unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="flight-card">', unsafe_allow_html=True)
        st.markdown(f'<div class="sidebar-id">SQ {f_num}</div>', unsafe_allow_html=True)
        st.markdown('<div class="main-body">', unsafe_allow_html=True)
        
        # Leg & Layover Logic
        legs = primary.get("legs", [primary]) if sia else [primary]
        for i, leg in enumerate(legs):
            if i > 0: # Layover detected
                layover_city = leg.get("origin", {}).get("cityName")
                st.markdown(f'<div class="layover-bar">🕒 Layover in {layover_city}</div>', unsafe_allow_html=True)

            # Terminal Translation (KUL logic)
            dep_code = leg.get("origin", {}).get("airportCode") if sia else leg.get("dep_iata")
            raw_term = leg.get("origin", {}).get("airportTerminal") if sia else "1"
            display_term = "Terminal 1" if dep_code == "KUL" and raw_term == "M" else f"Terminal {raw_term}"

            # Horizontal Display
            c_dep, c_mid, c_arr = st.columns([2, 1, 2])
            with c_dep:
                st.caption("Scheduled")
                st.markdown(f"<h1 style='margin:0;'>{dep_code}</h1>", unsafe_allow_html=True)
                st.markdown(f"<b>{display_term}</b>", unsafe_allow_html=True)
            
            with c_mid:
                st.markdown("<div style='text-align:center; padding-top:20px; font-size:24px;'>✈️</div>", unsafe_allow_html=True)
                status = leg.get("flightStatus") if sia else "ACTIVE"
                st.markdown(f"<div style='text-align:center; color:#28a745; font-size:12px;'><b>{status}</b></div>", unsafe_allow_html=True)

            with c_arr:
                arr_code = leg.get("destination", {}).get("airportCode") if sia else leg.get("arr_iata")
                st.caption("Scheduled")
                st.markdown(f"<h1 style='margin:0;'>{arr_code}</h1>", unsafe_allow_html=True)
                st.markdown(f"<b>Gate: {leg.get('arrivalGate', 'TBA')}</b>", unsafe_allow_html=True)

        # 4. Live Telemetry Footer (Always ADS-B)
        if adsb:
            st.markdown("---")
            alt, gs = adsb.get("alt_baro", 0), adsb.get("gs", 0)
            mach = round((gs * 0.514) / (20.04 * math.sqrt(288 - (0.0065 * alt * 0.304))), 2) if gs > 0 else 0
            st.markdown(f"📡 **Live Telemetry:** Altitude: {alt:,} ft | Speed: {gs} kts | **Mach: {mach}** | Reg: {adsb.get('r')}")

        st.markdown('</div></div>', unsafe_allow_html=True)

# --- 6. INTERFACE ---
if "user" not in st.session_state:
    st.title("KrisTracker Sandbox")
    if st.button("ENTER SYSTEM"): st.session_state.user = True
    st.stop()

t1, t2 = st.tabs(["🔎 TRACKER", "🗺️ RADAR"])

with t1:
    c1, c2 = st.columns(2)
    f_in = c1.text_input("Flight Number", "115")
    d_in = c2.date_input("Date")
    if st.button("EXECUTE SEARCH"):
        render_master_status(f_in, d_in)

with t2:
    # Use the fastest ADS-B provider for the map too
    st.subheader("ADS-B Network Map")
    m = folium.Map(location=[1.35, 103.98], zoom_start=4, tiles="CartoDB dark_matter")
    st_folium(m, width="100%", height=500)
