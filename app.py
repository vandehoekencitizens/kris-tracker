import streamlit as st
import requests, uuid, math, folium, base64
from streamlit_folium import st_folium
from datetime import datetime

# --- 1. SETTINGS & HIGH-FIDELITY CSS ---
st.set_page_config(page_title="KrisTracker Pro", page_icon="✈️", layout="wide")
SIA_NAVY = "#00266B"

st.markdown(f"""<style>
    .stApp {{ background-color: #f4f6f8; }}
    .sq-title {{ color: {SIA_NAVY}; font-size: 24px; font-weight: 500; font-family: serif; margin-bottom: -10px; }}
    .sq-subtitle {{ color: #333; font-size: 14px; margin-bottom: 20px; }}
    .flight-num-box {{ font-size: 24px; font-weight: 800; display: flex; align-items: center; justify-content: center; height: 100%; }}
    .time-large {{ font-size: 32px; font-weight: 500; color: {SIA_NAVY}; font-family: serif; line-height: 1; margin: 5px 0px; }}
    .text-sm {{ font-size: 13px; color: #666; margin: 2px 0px; }}
    .text-bold {{ font-size: 14px; font-weight: 700; color: #000; margin-bottom: 10px; }}
    .text-tiny-blue {{ font-size: 12px; font-weight: 700; color: {SIA_NAVY}; margin-bottom: -5px; }}
    .status-green {{ color: #1e8b2b; font-weight: 700; font-size: 14px; text-align: center; }}
    .status-line {{ border-top: 1px solid #ccc; position: relative; top: 15px; margin: 0px 20px; }}
    .plane-icon {{ position: absolute; right: -10px; top: -12px; font-size: 20px; color: {SIA_NAVY}; background: white; padding-left: 5px; }}
    .layover-divider {{ text-align: center; color: #666; font-size: 14px; margin: 20px 0; display: flex; align-items: center; }}
    .layover-divider::before, .layover-divider::after {{ content: ""; flex: 1; border-bottom: 1px solid #e0e0e0; margin: 0 15px; }}
</style>""", unsafe_allow_html=True)

# --- 2. THE TRIPLE-FUSION ENGINE (SQ > AirLabs > ADS-B) ---

def fetch_unified_data(f_num, date_str):
    unified = {"source": "NONE", "legs": [], "telemetry": {}, "raw": {}}
    callsign = f"SIA{f_num}".upper()
    iata = f"SQ{f_num}".upper()

    # 1. SIA OFFICIAL
    try:
        url = "https://apigw.singaporeair.com/api/uat/v2/flightstatus/getbynumber"
        headers = {"api_key": st.secrets["SIA_STATUS_KEY"], "x-csl-client-id": "SPD", "x-csl-client-uuid": str(uuid.uuid4())}
        sq_res = requests.post(url, json={"airlineCode": "SQ", "flightNumber": f_num, "scheduledDepartureDate": date_str}, headers=headers, timeout=3).json()
        sq_data = sq_res.get("data", {}).get("response", {}).get("flights", [None])[0]
        if sq_data:
            unified["legs"] = sq_data.get("legs", [])
            unified["source"] = "OFFICIAL (SQ)"
            unified["raw"]["sia"] = sq_data
    except: pass

    # 2. AIRLABS FALLBACK
    if not unified["legs"]:
        try:
            al_res = requests.get(f"https://airlabs.co/api/v9/flight?api_key={st.secrets['AIRLABS_API_KEY']}&flight_iata={iata}", timeout=3).json()
            al_data = al_res.get("response")
            if al_data:
                unified["source"] = "AGGREGATOR (AirLabs)"
                unified["legs"] = [{
                    "flightStatus": al_data.get("status", "Scheduled"),
                    "origin": {"airportCode": al_data.get("dep_iata"), "cityName": al_data.get("dep_city", "Origin")},
                    "destination": {"airportCode": al_data.get("arr_iata"), "cityName": al_data.get("arr_city", "Destination")},
                    "scheduledDepartureTime": al_data.get("dep_time"),
                    "actualDepartureTime": al_data.get("dep_time_actual"),
                    "scheduledArrivalTime": al_data.get("arr_time"),
                    "estimatedArrivalTime": al_data.get("arr_estimated")
                }]
                unified["raw"]["airlabs"] = al_data
        except: pass

    # 3. ADS-B TELEMETRY (Physics & Live Signal)
    try:
        adsb_res = requests.get(f"https://api.adsb.lol/v2/callsign/{callsign}", timeout=2).json()
        ac = adsb_res.get("ac", [None])[0]
        if ac:
            unified["telemetry"] = ac
            if unified["source"] == "NONE":
                unified["source"] = "RAW TELEMETRY (ADS-B)"
    except: pass

    return unified

def calculate_mach(gs_kts, alt_ft):
    if not gs_kts or gs_kts < 100: return 0.0
    temp_k = 288.15 - (0.0065 * (alt_ft * 0.3048))
    speed_sound = 20.046 * math.sqrt(temp_k)
    return round((gs_kts * 0.51444) / speed_sound, 2)

def fmt_time(dt_str):
    if not dt_str: return "N/A"
    return dt_str[-5:]

def display_pdf(file_path):
    with open(file_path, "rb") as f:
        base64_pdf = base64.b64encode(f.read()).decode('utf-8')
    st.markdown(f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="1000" type="application/pdf"></iframe>', unsafe_allow_html=True)

# --- 3. UI RENDERER (Multi-Leg & Physics) ---

def render_flight_card(data, f_num):
    legs = data["legs"]
    if not legs: return
    
    st.markdown(f"<div class='sq-title'>SQ {f_num} - {data['source']}</div>", unsafe_allow_html=True)
    st.markdown("<div class='sq-subtitle'>Schedule local times at each airport.</div>", unsafe_allow_html=True)

    with st.container(border=True):
        col_icon, col_content = st.columns([1, 6])
        col_icon.markdown(f"<div class='flight-num-box'>SQ {f_num}</div>", unsafe_allow_html=True)
        
        with col_content:
            for i, leg in enumerate(legs):
                orig, dest = leg.get("origin", {}), leg.get("destination", {})
                
                t1, t2, t3 = st.columns([2, 2, 2])
                with t1:
                    st.markdown(f"<p class='text-sm'>Scheduled {fmt_time(leg.get('scheduledDepartureTime'))}</p>", unsafe_allow_html=True)
                    st.markdown(f"<div class='time-large'>{orig.get('airportCode')} {fmt_time(leg.get('actualDepartureTime') or leg.get('scheduledDepartureTime'))}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='text-bold'>{orig.get('cityName')}</div>", unsafe_allow_html=True)

                with t2:
                    st.markdown("<br><div class='status-line'><div class='plane-icon'>✈</div></div>", unsafe_allow_html=True)
                    st.markdown(f"<br><div class='status-green'>✅ {leg.get('flightStatus', 'Active')}</div>", unsafe_allow_html=True)

                with t3:
                    st.markdown(f"<p class='text-sm'>Scheduled {fmt_time(leg.get('scheduledArrivalTime'))}</p>", unsafe_allow_html=True)
                    arr_time = leg.get('actualArrivalTime') or leg.get('estimatedArrivalTime') or leg.get('scheduledArrivalTime')
                    st.markdown(f"<div class='time-large'>{dest.get('airportCode')} {fmt_time(arr_time)}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='text-bold'>{dest.get('cityName')}</div>", unsafe_allow_html=True)

                if i < len(legs) - 1:
                    st.markdown(f"<div class='layover-divider'>🕒 Layover at {dest.get('cityName')}</div>", unsafe_allow_html=True)

    # Physics Bar (Mach Engine)
    if data["telemetry"]:
        ac = data["telemetry"]
        mach = calculate_mach(ac.get("gs", 0), ac.get("alt_baro", 0))
        st.info(f"📡 **Live Telemetry:** Reg: {ac.get('r')} | Alt: {ac.get('alt_baro'):,} ft | GS: {ac.get('gs')} kts | **Mach {mach}**")

# --- 4. NAVIGATION ---

st.sidebar.title("🛠️ KrisTracker Pro")
mode = st.sidebar.radio("Navigation", ["Flight Search", "Route Search", "Network Radar", "Changi Wayfinding"])
debug_mode = st.sidebar.toggle("Enable Debug Mode", False)

if mode == "Flight Search":
    c1, c2 = st.columns(2)
    f_num = c1.text_input("SQ Flight Number", "115")
    f_date = c2.date_input("Date")
    
    if st.button("Execute Search"):
        with st.spinner("Fusing Data Sources..."):
            data = fetch_unified_data(f_num, str(f_date))
            if data["legs"] or data["telemetry"]:
                render_flight_card(data, f_num)
                if debug_mode: st.json(data)
            else: st.error("No flight found across SQ, AirLabs, or ADS-B networks.")

elif mode == "Route Search":
    st.markdown("<div class='sq-title'>Route Search Engine</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    orig_in = c1.text_input("Origin (e.g., SIN)")
    dest_in = c2.text_input("Destination (e.g., LHR)")
    if st.button("Scan Route"):
        st.warning(f"Feature active: Scanning network for active SQ flights from {orig_in} to {dest_in}...")

elif mode == "Network Radar":
    st.markdown("<div class='sq-title'>SIA Global Network Radar</div>", unsafe_allow_html=True)
    m = folium.Map(location=[1.35, 103.98], zoom_start=3, tiles="CartoDB dark_matter")
    try:
        r = requests.get("https://api.adsb.lol/v2/callsign/SIA", timeout=5).json()
        for ac in r.get("ac", []):
            if ac.get("lat"):
                folium.Marker([ac['lat'], ac['lon']], popup=f"SQ{ac.get('flight')}", icon=folium.Icon(color="blue", icon="plane", prefix="fa")).add_to(m)
        st_folium(m, width="100%", height=600)
    except: st.error("Radar data unavailable.")

elif mode == "Changi Wayfinding":
    st.markdown("<div class='sq-title'>Changi T3 Wayfinding</div>", unsafe_allow_html=True)
    display_pdf("Singapore-Changi-Airport-Transit-Area-Wayfinding.pdf")
