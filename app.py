import streamlit as st
import requests, uuid, math, folium
from streamlit_folium import st_folium
from datetime import datetime

# --- 1. SETTINGS & CSS ---
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

# --- 2. PHYSICS & DATA ENGINES (ALL RETAINED) ---
def calculate_mach(gs_kts, alt_ft):
    if not gs_kts or gs_kts < 100: return 0.0
    temp_k = 288.15 - (0.0065 * (alt_ft * 0.3048))
    speed_sound = 20.046 * math.sqrt(temp_k)
    return round((gs_kts * 0.51444) / speed_sound, 2)

def get_fastest_adsb(f_num):
    callsign = f"SIA{f_num}".upper()
    for url in ["https://opendata.adsb.fi/api/v2/callsign/", "https://api.adsb.lol/v2/callsign/"]:
        try:
            r = requests.get(f"{url}{callsign}", timeout=1.2).json()
            if r.get("aircraft"): return r["aircraft"][0]
        except: continue
    return None

def get_sia_data(f_num, date_str):
    url = "https://apigw.singaporeair.com/api/uat/v2/flightstatus/getbynumber"
    headers = {"api_key": st.secrets["SIA_STATUS_KEY"], "x-csl-client-id": "SPD", "x-csl-client-uuid": str(uuid.uuid4())}
    try:
        res = requests.post(url, json={"airlineCode": "SQ", "flightNumber": f_num, "scheduledDepartureDate": date_str}, headers=headers, timeout=5).json()
        return res.get("data", {}).get("response", {}).get("flights", [None])[0]
    except: return None

def get_adsb_global_sia():
    try:
        r = requests.get("https://api.adsb.lol/v2/callsign/SIA", timeout=3).json()
        return r.get("aircraft", [])
    except: return []

# --- 3. FORMATTERS ---
def fmt_time(dt_str):
    if not dt_str: return None
    try: return datetime.fromisoformat(dt_str.replace("Z", "")).strftime("%H:%M")
    except: return dt_str[-5:]

def fmt_date(dt_str):
    if not dt_str: return None
    try: return datetime.fromisoformat(dt_str.replace("Z", "")).strftime("%a %-d %b")
    except: return dt_str[:10]

# --- 4. THE REVAMPED MULTI-LEG UI RENDERER ---
def render_flight_card(sia_data):
    legs = sia_data.get("legs", [])
    if not legs: return
    
    f_num = str(sia_data.get('flightNumber', '')).lstrip('0')
    first_origin = legs[0].get("origin", {})
    final_dest = legs[-1].get("destination", {})

    # Main Header
    st.markdown(f"<div class='sq-title'>SQ {f_num} - {first_origin.get('cityName', first_origin.get('airportCode'))} to {final_dest.get('cityName', final_dest.get('airportCode'))}</div>", unsafe_allow_html=True)
    st.markdown("<div class='sq-subtitle'>Schedules show the local time at each airport.</div>", unsafe_allow_html=True)

    with st.container(border=True):
        col1, col2 = st.columns([1, 6])
        
        with col1:
            st.markdown(f"<div class='flight-num-box'>SQ {f_num}</div>", unsafe_allow_html=True)
            
        with col2:
            # Loop through each leg to support layovers (like SQ 11 via NRT)
            for i, leg in enumerate(legs):
                origin, dest = leg.get("origin", {}), leg.get("destination", {})
                
                s_dep, a_dep = leg.get("scheduledDepartureTime"), leg.get("actualDepartureTime")
                s_arr, a_arr, e_arr = leg.get("scheduledArrivalTime"), leg.get("actualArrivalTime"), leg.get("estimatedArrivalTime")
                status_raw = leg.get("flightStatus", "Scheduled")
                is_landed = "Arrived" in status_raw or "LANDED" in status_raw.upper()
                is_departed = a_dep is not None

                # Terminals
                dep_term = origin.get("airportTerminal", "1")
                if origin.get("airportCode") == "KUL" and dep_term == "M": dep_term = "1"
                arr_term = dest.get("airportTerminal", "2")
                if dest.get("airportCode") == "SIN" and (not arr_term or arr_term == "TBA" or arr_term == "NIL"): arr_term = "2"

                t_col1, t_col2, t_col3 = st.columns([1.5, 2, 1.5])
                
                # Origin Stack
                with t_col1:
                    st.markdown(f"<p class='text-sm' style='margin-bottom:0;'>Scheduled {fmt_time(s_dep)}</p>", unsafe_allow_html=True)
                    if is_departed: st.markdown("<p class='text-tiny-blue'>Actual</p>", unsafe_allow_html=True)
                    st.markdown(f"<div class='time-large'>{origin.get('airportCode')} {fmt_time(a_dep) if is_departed else fmt_time(s_dep)}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='text-bold'>{origin.get('cityName', 'Origin')}</div>", unsafe_allow_html=True)
                    st.markdown(f"<p class='text-sm'>{fmt_date(s_dep)}</p>", unsafe_allow_html=True)
                    st.markdown(f"<p class='text-sm'>{origin.get('airportName', '')}</p>", unsafe_allow_html=True)
                    st.markdown(f"<p class='text-sm'>Terminal {dep_term}</p>", unsafe_allow_html=True)

                # Center Line
                with t_col2:
                    st.markdown("<br><br>", unsafe_allow_html=True)
                    st.markdown("<div class='status-line'><div class='plane-icon'>✈</div></div>", unsafe_allow_html=True)
                    st.markdown(f"<br><div class='status-green'>{'✅ Arrived' if is_landed else f'✅ {status_raw}'}</div>", unsafe_allow_html=True)

                # Destination Stack
                with t_col3:
                    st.markdown(f"<p class='text-sm' style='margin-bottom:0;'>Scheduled {fmt_time(s_arr)}</p>", unsafe_allow_html=True)
                    if is_landed: st.markdown("<p class='text-tiny-blue'>Actual</p>", unsafe_allow_html=True)
                    elif e_arr and not is_landed: st.markdown("<p class='text-tiny-blue'>Estimated</p>", unsafe_allow_html=True)
                    display_arr_time = a_arr if is_landed else (e_arr if e_arr else s_arr)
                    st.markdown(f"<div class='time-large'>{dest.get('airportCode')} {fmt_time(display_arr_time)}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='text-bold'>{dest.get('cityName', 'Destination')}</div>", unsafe_allow_html=True)
                    st.markdown(f"<p class='text-sm'>{fmt_date(s_arr)}</p>", unsafe_allow_html=True)
                    st.markdown(f"<p class='text-sm'>{dest.get('airportName', '')}</p>", unsafe_allow_html=True)
                    st.markdown(f"<p class='text-sm'>Terminal {arr_term}</p>", unsafe_allow_html=True)

                # If there is another leg after this one, add the Layover divider
                if i < len(legs) - 1:
                    layover_city = dest.get('cityName', dest.get('airportCode'))
                    st.markdown(f"<div class='layover-divider'>🕒 Layover at {layover_city}</div>", unsafe_allow_html=True)

# --- 5. INTERFACE & NAVIGATION ---
st.sidebar.title("🛠️ KrisTracker Pro")
mode = st.sidebar.radio("Navigation", ["Flight Search", "Route Search", "Global Radar"])
st.sidebar.divider()
debug_mode = st.sidebar.toggle("🛠️ Enable Debug Mode", False)

if mode == "Flight Search":
    c1, c2 = st.columns([1, 1])
    with c1: f_num = st.text_input("SQ Flight Number", "115")
    with c2: f_date = st.date_input("Date")
    
    if st.button("Search Flight"):
        with st.spinner("Connecting to SIA Gateway..."):
            sia = get_sia_data(f_num, str(f_date))
            adsb = get_fastest_adsb(f_num)
            
            if sia:
                render_flight_card(sia)
                
                # Mach Physics Integration
                if adsb:
                    st.divider()
                    alt, gs = adsb.get("alt_baro", 0), adsb.get("gs", 0)
                    mach = calculate_mach(gs, alt)
                    st.info(f"📡 **Live Telemetry (ADS-B):** Altitude: {alt:,} ft | Ground Speed: {gs} kts | **Mach {mach}**")
                
                if debug_mode: 
                    st.divider()
                    st.subheader("🛠️ Raw API JSON Dump")
                    st.json(sia)
            else: st.error("Flight Data Not Found. Check Flight Number and Date.")

elif mode == "Route Search":
    st.markdown("<div class='sq-title'>Route Search Engine</div><br>", unsafe_allow_html=True)
    c1, c2 = st.columns([1, 1])
    with c1: origin_inp = st.text_input("Origin Airport (e.g. KUL)")
    with c2: dest_inp = st.text_input("Destination Airport (e.g. SIN)")
    f_date_route = st.date_input("Departure Date")
    
    if st.button("Search Routes"):
        st.warning(f"Looking up flights from **{origin_inp.upper()}** to **{dest_inp.upper()}** on {f_date_route}...")
        st.info("💡 Once the specific SIA Route endpoint (e.g., /getbyroute) is hooked up, the list of matching SQ flights will populate here.")

elif mode == "Global Radar":
    st.markdown("<div class='sq-title'>Live SIA Network Radar</div><br>", unsafe_allow_html=True)
    with st.spinner("Connecting to ADS-B Exchange..."):
        m = folium.Map(location=[1.35, 103.98], zoom_start=4, tiles="CartoDB positron")
        active_flights = get_adsb_global_sia()
        
        if active_flights:
            for ac in active_flights:
                lat, lon = ac.get("lat"), ac.get("lon")
                if lat and lon:
                    flight_id = ac.get("flight", "SQ---").strip()
                    folium.Marker(
                        [lat, lon],
                        popup=f"<b>{flight_id}</b><br>Alt: {ac.get('alt_baro', 0):,} ft<br>Speed: {ac.get('gs', 0)} kts<br>Reg: {ac.get('r', 'N/A')}",
                        icon=folium.Icon(icon="plane", prefix="fa", color="blue")
                    ).add_to(m)
            st.success(f"Tracking {len(active_flights)} active SIA aircraft.")
        else:
            st.warning("No active SIA flights found.")
            
        st_folium(m, width="100%", height=600)
