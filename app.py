import streamlit as st
import requests, uuid, folium, base64, json, os, time, random
from streamlit_folium import st_folium
from datetime import datetime, timezone, timedelta
from math import radians, cos, sin, asin, sqrt

# --- 1. CORE STYLING & ASSETS ---
st.set_page_config(page_title="KrisTracker Pro", page_icon="✈️", layout="wide")
SIA_NAVY, SIA_GOLD, FR_YELLOW = "#00266B", "#BD9B60", "#ffc107"

st.markdown(f"""<style>
    [data-testid="stSidebar"] {{ min-width: 200px !important; max-width: 200px !important; }}
    .spec-label {{ color: #666; font-size: 11px; text-transform: uppercase; font-weight: bold; letter-spacing: 0.8px; margin-bottom: 2px; }}
    .spec-value {{ color: {SIA_NAVY}; font-size: 17px; font-weight: 700; margin-bottom: 15px; font-family: 'Segoe UI', sans-serif; }}
    .time-box {{ background: #ffffff; padding: 12px; border-radius: 6px; border: 1px solid #d1d5db; border-left: 5px solid {SIA_GOLD}; }}
    .status-pill {{ background: {SIA_NAVY}; color: white; padding: 4px 12px; border-radius: 20px; font-size: 13px; font-weight: 600; text-transform: uppercase; }}
    .section-header {{ border-bottom: 2px solid #eee; padding-bottom: 5px; margin-bottom: 15px; color: #444; font-weight: 800; font-size: 14px; text-transform: uppercase; }}
    .fr-header {{ display: flex; align-items: baseline; gap: 10px; padding: 10px 0; border-bottom: 1px solid #444; }}
    .fr-callsign {{ color: {FR_YELLOW}; font-size: 26px; font-weight: 900; }}
    .fr-iata {{ background: #ddd; color: #333; padding: 2px 6px; border-radius: 4px; font-size: 14px; font-weight: bold; }}
    .fr-type {{ background: #4a6491; color: white; padding: 2px 6px; border-radius: 4px; font-size: 14px; font-weight: bold; }}
    .fr-route-box {{ display: flex; justify-content: space-between; align-items: center; margin: 15px 0; }}
    .fr-city {{ font-size: 40px; font-weight: 300; line-height: 1; }}
    .utc-offset {{ font-size: 11px; color: #888; margin-top: -2px; font-family: monospace; }}
    .fr-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; background: #f4f4f4; padding: 15px; border-radius: 8px; }}
    .fr-telemetry {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-top: 15px; padding-top: 15px; border-top: 1px solid #ddd; }}
    .progress-bar-bg {{ width:100%; height:8px; background:#e0e0e0; border-radius:4px; margin: 8px 0; position: relative; }}
    .progress-bar-fill {{ height:100%; background:{SIA_GOLD}; border-radius:4px; }}
</style>""", unsafe_allow_html=True)

# --- 2. HELPER FUNCTIONS ---

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dLat, dLon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dLat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dLon/2)**2
    return 2 * R * asin(sqrt(a))

def get_b64(file_path):
    try:
        with open(file_path, "rb") as f: return base64.b64encode(f.read()).decode('utf-8')
    except: return ""

def get_ac_image(ac_code):
    mapping = {"A359": "9V-SMI.jpg", "A388": "9V-SKY.jpg", "B38M": "9V-MBO.jpg", "78X": "9V-SCK.avif", "B78X": "9V-SCK.avif", "77W": "9V-SWR.jpg", "B77W": "9V-SWR.jpg"}
    return mapping.get(str(ac_code).upper().strip())

def fmt_t(dt_str): 
    if not dt_str: return "---"
    return dt_str[11:16] if "T" in dt_str else dt_str[-5:]

def calc_eta_str(est_iso):
    try:
        est = datetime.fromisoformat(est_iso.replace("Z", "+00:00"))
        delta = (est - datetime.now(timezone.utc)).total_seconds()
        if delta > 0:
            h, rem = divmod(int(delta), 3600)
            return f" (In {h}h {divmod(rem, 60)[0]}m)"
        return " (Arriving shortly)"
    except: return ""

# --- 3. DATA ENGINES ---

def fetch_radar_data():
    log_file = "radar_speed_log.json"
    if not os.path.exists(log_file):
        with open(log_file, "w") as f: json.dump({"adsb.fi": [], "adsb.lol": []}, f)
    with open(log_file, "r") as f: logs = json.load(f)
    provider = random.choice(["adsb.fi", "adsb.lol"])
    url = f"https://api.{provider}/v2/callsign/SIA"
    start = time.time()
    try:
        res = requests.get(url, timeout=8).json()
        elapsed = time.time() - start
        logs[provider].append(elapsed)
        with open(log_file, "w") as f: json.dump(logs, f)
        return res.get("ac", []), provider, elapsed
    except: return [], provider, 0

def fetch_search_data(f_num, date_str):
    try:
        url = "https://apigw.singaporeair.com/api/uat/v2/flightstatus/getbynumber"
        headers = {"api_key": st.secrets["SIA_STATUS_KEY"], "x-csl-client-id": "SPD", "x-csl-client-uuid": str(uuid.uuid4())}
        sq_res = requests.post(url, json={"airlineCode": "SQ", "flightNumber": f_num, "scheduledDepartureDate": date_str}, headers=headers, timeout=5).json()
        sq_data = sq_res.get("data", {}).get("response", {}).get("flights", [None])[0]
        if sq_data and sq_data.get("legs"):
            valid_legs = [l for l in sq_data["legs"] if date_str in l.get("scheduledDepartureTime", "")]
            if valid_legs:
                l = valid_legs[-1]
                return {"source": "SIA", "status": l.get("flightStatus", "Unknown").upper(), "leg": {
                    "fn": f"SQ{f_num}", "ac_type": l.get("aircraftTypeCode"), "dep_iata": l["origin"]["airportCode"], "arr_iata": l["destination"]["airportCode"],
                    "dep_term": l["origin"].get("terminal") or "TBA", "arr_term": l["destination"].get("terminal") or "TBA",
                    "times": {"sch_dep": l.get("scheduledDepartureTime"), "act_dep": l.get("actualDepartureTime"), "sch_arr": l.get("scheduledArrivalTime"), "act_arr": l.get("actualArrivalTime"), "est_arr": l.get("estimatedArrivalTime")}
                }}
    except: pass
    return {"source": "NONE", "leg": None}

def get_flight_trail(flight_iata):
    try:
        url = f"https://airlabs.co/api/v9/track?api_key={st.secrets['AIRLABS_API_KEY']}&flight_iata={flight_iata}"
        res = requests.get(url, timeout=5).json().get("response", [])
        return [[p['lat'], p['lng']] for p in res if 'lat' in p]
    except: return []

# --- 4. UI COMPONENTS ---

def render_fr24_card(flight_iata, telemetry=None):
    f_num = flight_iata.replace("SQ", "").replace("SIA", "").strip()
    data = fetch_search_data(f_num, datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    if not data["leg"]: return st.error("Flight details not found.")
    
    leg = data["leg"]
    st.markdown(f'<div class="fr-header"><span class="fr-callsign">SIA{f_num}</span><span class="fr-iata">{leg["fn"]}</span><span class="fr-type">{leg["ac_type"]}</span></div>', unsafe_allow_html=True)
    img = get_ac_image(leg['ac_type'])
    if img: st.image(img, use_container_width=True)

    st.markdown(f"""<div class="fr-route-box">
        <div style="text-align:left;"><div class="fr-city">{leg['dep_iata']}</div><div class="utc-offset">+08 (UTC +08:00)</div></div>
        <div style="font-size:30px; color:{FR_YELLOW};">✈</div>
        <div style="text-align:right;"><div class="fr-city">{leg['arr_iata']}</div><div class="utc-offset">+08 (UTC +08:00)</div></div>
    </div>""", unsafe_allow_html=True)

    # Telemetry Progress Bar
    if telemetry and telemetry.get('lat'):
        # Note: AirLabs/SIA coordinates would be needed for precise haversine; using placeholder progress for UI
        st.markdown(f"""<div style="margin-top:10px;"><div class="spec-label">Flight Progress</div>
            <div class="progress-bar-bg"><div class="progress-bar-fill" style="width:65%;"></div></div></div>""", unsafe_allow_html=True)

    st.markdown(f"""<div class="fr-grid">
        <div><span class="spec-label">SCHED DEP (T{leg['dep_term']})</span><br><b>{fmt_t(leg['times']['sch_dep'])}</b></div>
        <div><span class="spec-label">SCHED ARR (T{leg['arr_term']})</span><br><b>{fmt_t(leg['times']['sch_arr'])}</b></div>
        <div><span class="spec-label">ACTUAL DEP</span><br><b>{fmt_t(leg['times']['act_dep'])}</b></div>
        <div><span class="spec-label">ESTIMATED ARR</span><br><b style="color:#28a745;">{fmt_t(leg['times']['act_arr'] or leg['times']['est_arr'])}{calc_eta_str(leg['times']['est_arr'])}</b></div>
    </div>""", unsafe_allow_html=True)

    if telemetry:
        st.markdown(f"""<div class="fr-telemetry">
            <div><span class="spec-label">ALTITUDE</span><br><b>{telemetry.get('alt_baro', 0):,} ft</b></div>
            <div><span class="spec-label">GROUNDSPEED</span><br><b>{telemetry.get('gs', 0)} kts</b></div>
        </div>""", unsafe_allow_html=True)

# --- 5. MAIN LOGIC ---

def show_interactive_radar():
    if "map_center" not in st.session_state: st.session_state.map_center = [1.35, 103.8]
    if "map_zoom" not in st.session_state: st.session_state.map_zoom = 4

    col_info, col_map = st.columns([1.5, 2])
    load_placeholder = st.empty()
    with load_placeholder.container():
        vid_data = get_b64("SQ loading screen.mp4")
        st.markdown(f'<div style="text-align:center;"><video width="250" autoplay loop muted><source src="data:video/mp4;base64,{vid_data}"></video></div>', unsafe_allow_html=True)
        planes, provider, l_time = fetch_radar_data()
    load_placeholder.empty()

    with col_map:
        st.caption(f"⚡ {provider} | {l_time:.2f}s")
        m = folium.Map(location=st.session_state.map_center, zoom_start=st.session_state.map_zoom, tiles="CartoDB dark_matter")
        icon_b64 = get_b64("f5c530aa-d922-4920-9313-63a11c7f2921.png")
        for p in planes:
            if p.get('lat') and p.get('lon'):
                html = f'<div style="transform: rotate({p.get("track", 0)}deg);"><img src="data:image/png;base64,{icon_b64}" width="28"></div>'
                folium.Marker([p['lat'], p['lon']], tooltip=p.get('flight','').strip(), icon=folium.DivIcon(html=html)).add_to(m)
        
        map_res = st_folium(m, width="100%", height=750, key="radar_v3")
        if map_res.get("center"): st.session_state.map_center = [map_res["center"]["lat"], map_res["center"]["lng"]]
        if map_res.get("zoom"): st.session_state.map_zoom = map_res["zoom"]

    with col_info:
        clicked = map_res.get("last_object_clicked_tooltip")
        if clicked:
            # Draw Path
            trail = get_flight_trail(clicked)
            if trail: folium.PolyLine(trail, color=SIA_GOLD, weight=2).add_to(m)
            p_data = next((x for x in planes if x.get('flight', '').strip() == clicked), {})
            render_fr24_card(clicked, telemetry=p_data)
        else:
            st.info("👈 Select an aircraft on the map.")

menu = st.sidebar.radio("MODE", ["📡 Radar", "🔍 Search", "🗺️ Wayfinding"])
if menu == "📡 Radar": show_interactive_radar()
elif menu == "🔍 Search":
    c1, c2 = st.columns(2)
    f_num = c1.text_input("SQ Number", "11")
    f_date = c2.date_input("Departure Date")
    if st.button("EXECUTE SEARCH"):
        render_fr24_card(f"SQ{f_num}")
elif menu == "🗺️ Wayfinding":
    pdf_b64 = get_b64("Singapore-Changi-Airport-Transit-Area-Wayfinding.pdf")
    st.markdown(f'<iframe src="data:application/pdf;base64,{pdf_b64}" width="100%" height="900"></iframe>', unsafe_allow_html=True)
