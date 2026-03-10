import streamlit as st
import requests, uuid, math, folium, base64, json, os, time
from streamlit_folium import st_folium
from datetime import datetime, timezone

# --- 1. CORE STYLING & ASSETS ---
# Configures the wide layout and custom SIA color palette for a pro tracking feel
st.set_page_config(page_title="KrisTracker Pro v2.0", page_icon="✈️", layout="wide")
SIA_NAVY, SIA_GOLD, FR_YELLOW = "#00266B", "#BD9B60", "#ffc107"

st.markdown(f"""<style>
    /* UI Structure Constraints */
    [data-testid="stSidebar"] {{ min-width: 210px !important; max-width: 210px !important; }}
    
    /* Search Manifest & Typography */
    .spec-label {{ color: #666; font-size: 11px; text-transform: uppercase; font-weight: bold; letter-spacing: 0.8px; margin-bottom: 2px; }}
    .spec-value {{ color: {SIA_NAVY}; font-size: 17px; font-weight: 700; margin-bottom: 15px; font-family: 'Segoe UI', sans-serif; }}
    .time-box {{ background: #ffffff; padding: 12px; border-radius: 6px; border: 1px solid #d1d5db; border-left: 5px solid {SIA_GOLD}; }}
    .status-pill {{ background: {SIA_NAVY}; color: white; padding: 4px 12px; border-radius: 20px; font-size: 13px; font-weight: 600; text-transform: uppercase; }}
    .section-header {{ border-bottom: 2px solid #eee; padding-bottom: 5px; margin-bottom: 15px; color: #444; font-weight: 800; font-size: 14px; text-transform: uppercase; }}
    
    /* Radar Sidebar Card Styling (FlightRadar24 Inspired) */
    .fr-header {{ display: flex; align-items: baseline; gap: 10px; padding: 10px 0; border-bottom: 1px solid #444; }}
    .fr-callsign {{ color: {FR_YELLOW}; font-size: 26px; font-weight: 900; }}
    .fr-iata {{ background: #ddd; color: #333; padding: 2px 6px; border-radius: 4px; font-size: 14px; font-weight: bold; }}
    .fr-type {{ background: #4a6491; color: white; padding: 2px 6px; border-radius: 4px; font-size: 14px; font-weight: bold; }}
    .fr-route-box {{ display: flex; justify-content: space-between; align-items: center; margin: 15px 0; }}
    .fr-city {{ font-size: 40px; font-weight: 300; line-height: 1; }}
    .fr-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; background: #f4f4f4; padding: 15px; border-radius: 8px; }}
    .fr-telemetry {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-top: 15px; padding-top: 15px; border-top: 1px solid #ddd; }}
    
    /* Refresh Timer UI */
    .timer-text {{ font-size: 12px; color: {SIA_NAVY}; font-weight: bold; text-align: right; margin-bottom: 5px; }}
</style>""", unsafe_allow_html=True)

# --- 2. HELPER FUNCTIONS ---

def get_b64(file_path):
    """Retrieves local files for PDF, Radar Icons, and Loading Video."""
    try:
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                return base64.b64encode(f.read()).decode('utf-8')
    except: pass
    return ""

def get_ac_image(ac_code):
    """Maps ICAO codes to local aircraft photography."""
    code = str(ac_code).upper().strip()
    mapping = {
        "A359": "9V-SMI.jpg", "A388": "9V-SKY.jpg", "B38M": "9V-MBO.jpg",
        "78X": "9V-SCK.avif", "B78X": "9V-SCK.avif", "77W": "9V-SWR.jpg", "B77W": "9V-SWR.jpg"
    }
    return mapping.get(code)

def fmt_t(dt_str): 
    """Formats ISO time to HH:MM."""
    return dt_str[-5:] if dt_str and len(dt_str) >= 5 else "---"

def calc_eta_str(est_iso):
    """Calculates live countdown based on estimated arrival."""
    try:
        if not est_iso: return ""
        est = datetime.fromisoformat(est_iso.replace("Z", "+00:00"))
        delta = (est - datetime.now(timezone.utc)).total_seconds()
        if delta > 0:
            h, rem = divmod(int(delta), 3600)
            m, _ = divmod(rem, 60)
            return f" (In {h}h {m}m)"
        return " (Arriving shortly)"
    except: return ""

# --- 3. DATA FUSION ENGINE ---

def fetch_search_data(f_num, date_str):
    """Combines Official SIA API with AirLabs feed for the Search Mode."""
    unified = {"source": "NONE", "leg": None, "status": "Unknown"}
    iata = f"SQ{f_num}".upper()
    
    sq_leg, sq_status = {}, "Unknown"
    try:
        url = "https://apigw.singaporeair.com/api/uat/v2/flightstatus/getbynumber"
        headers = {
            "api_key": st.secrets["SIA_STATUS_KEY"], 
            "x-csl-client-id": "SPD", 
            "x-csl-client-uuid": str(uuid.uuid4())
        }
        sq_res = requests.post(url, json={"airlineCode": "SQ", "flightNumber": f_num, "scheduledDepartureDate": date_str}, headers=headers, timeout=5).json()
        sq_data = sq_res.get("data", {}).get("response", {}).get("flights", [None])[0]
        if sq_data and sq_data.get("legs"):
            valid_legs = [l for l in sq_data["legs"] if date_str in l.get("scheduledDepartureTime", "")]
            if valid_legs:
                sq_leg = valid_legs[-1]
                sq_status = sq_leg.get("flightStatus", "Unknown").upper()
    except: pass

    al_data = {}
    try:
        # Search AirLabs for specific flight details
        url = f"https://airlabs.co/api/v9/flight?api_key={st.secrets['AIRLABS_API_KEY']}&flight_iata={iata}"
        al = requests.get(url, timeout=5).json().get("response")
        if al and date_str in al.get("dep_time", ""): al_data = al
    except: pass

    if al_data or sq_leg:
        unified["source"] = "AIRLABS OPERATIONS" if al_data else "OFFICIAL SIA GATEWAY"
        unified["status"] = al_data.get("status", sq_status).upper()
        unified["leg"] = {
            "fn": iata, 
            "ac_type": al_data.get("aircraft_icao") or sq_leg.get("aircraftTypeCode", "N/A"),
            "dep_iata": al_data.get("dep_iata") or sq_leg.get("origin", {}).get("airportCode", "---"),
            "arr_iata": al_data.get("arr_iata") or sq_leg.get("destination", {}).get("airportCode", "---"),
            "dep_term": al_data.get("dep_terminal") or sq_leg.get("origin", {}).get("airportTerminal", "TBA"),
            "arr_term": al_data.get("arr_terminal") or sq_leg.get("destination", {}).get("airportTerminal", "TBA"),
            "dep_gate": al_data.get("dep_gate") or sq_leg.get("origin", {}).get("gate", "TBA"),
            "arr_gate": al_data.get("arr_gate") or sq_leg.get("destination", {}).get("gate", "TBA"),
            "times": {
                "sch_dep": al_data.get("dep_time") or sq_leg.get("scheduledDepartureTime"),
                "act_dep": al_data.get("dep_actual") or sq_leg.get("actualDepartureTime"),
                "sch_arr": al_data.get("arr_time") or sq_leg.get("scheduledArrivalTime"),
                "act_arr": al_data.get("arr_actual") or sq_leg.get("actualArrivalTime"),
                "est_arr": al_data.get("arr_estimated") or sq_leg.get("estimatedArrivalTime")
            }
        }
    return unified

# --- 4. UI COMPONENTS ---

def render_search_manifest(data):
    """The Flight Search Card featuring grids and terminal info."""
    leg = data["leg"]
    arr_terminal = "Terminal 2/3" if (leg['arr_iata'] == "SIN" and leg['arr_term'] == "TBA") else leg['arr_term']
    
    st.markdown(f"**Data Source:** {data['source']}")
    st.markdown(f"### <span class='status-pill'>{data['status']}</span>", unsafe_allow_html=True)
    
    st.markdown("<div class='section-header'>Flight & Aircraft Information</div>", unsafe_allow_html=True)
    r1_c1, r1_c2, r1_c3, r1_c4 = st.columns(4)
    r1_c1.markdown(f"<div class='spec-label'>Flight</div><div class='spec-value'>{leg['fn']}</div>", unsafe_allow_html=True)
    r1_c2.markdown(f"<div class='spec-label'>Aircraft</div><div class='spec-value'>{leg['ac_type']}</div>", unsafe_allow_html=True)
    r1_c3.markdown(f"<div class='spec-label'>Departure</div><div class='spec-value'>{leg['dep_iata']}</div>", unsafe_allow_html=True)
    r1_c4.markdown(f"<div class='spec-label'>Arrival</div><div class='spec-value'>{leg['arr_iata']}</div>", unsafe_allow_html=True)

    st.markdown("<div class='section-header'>Terminal & Gate Assignments</div>", unsafe_allow_html=True)
    r2_c1, r2_c2, r2_c3, r2_c4 = st.columns(4)
    r2_c1.markdown(f"<div class='spec-label'>Dep Terminal</div><div class='spec-value'>{leg['dep_term']}</div>", unsafe_allow_html=True)
    r2_c2.markdown(f"<div class='spec-label'>Arr Terminal</div><div class='spec-value'>{arr_terminal}</div>", unsafe_allow_html=True)
    r2_c3.markdown(f"<div class='spec-label'>Dep Gate</div><div class='spec-value'>{leg['dep_gate']}</div>", unsafe_allow_html=True)
    r2_c4.markdown(f"<div class='spec-label'>Arr Gate</div><div class='spec-value'>{leg['arr_gate']}</div>", unsafe_allow_html=True)

    st.markdown("<div class='section-header'>Schedule Details</div>", unsafe_allow_html=True)
    d1, d2, d3 = st.columns(3)
    d1.markdown(f"<div class='spec-label'>Scheduled Dep</div><div class='time-box'>{leg['times']['sch_dep']}</div>", unsafe_allow_html=True)
    d2.markdown(f"<div class='spec-label'>Scheduled Arr</div><div class='time-box'>{leg['times']['sch_arr']}</div>", unsafe_allow_html=True)
    d3.markdown(f"<div class='spec-label'>Estimated Arr</div><div class='time-box'>{leg['times']['est_arr'] or '---'}</div>", unsafe_allow_html=True)

def render_fr24_card(flight_iata, telemetry=None):
    """The Sidebar Card for the Interactive Radar. Terminology fixed to 'Speed'."""
    f_num = flight_iata.replace("SQ", "").strip()
    data = fetch_search_data(f_num, datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    
    if data["leg"]:
        leg = data["leg"]
        # Documentation: Extracting aircraft_icao for dynamic type loading
        ac_type = telemetry.get('aircraft_icao') or leg['ac_type']
        st.markdown(f"""<div class="fr-header"><span class="fr-callsign">{flight_iata}</span><span class="fr-iata">{leg['fn']}</span><span class="fr-type">{ac_type}</span></div><div style="color:#ccc; font-size:14px; margin-bottom:10px;">Singapore Airlines</div>""", unsafe_allow_html=True)
        
        img = get_ac_image(ac_type)
        if img: st.image(img, use_container_width=True)
        
        st.markdown(f"""<div class="fr-route-box"><div style="text-align:left;"><div class="fr-city">{leg['dep_iata']}</div><div class="spec-label">DEP</div></div><div style="font-size:30px; color:{FR_YELLOW}; transform:rotate(90deg);">✈</div><div style="text-align:right;"><div class="fr-city">{leg['arr_iata']}</div><div class="spec-label">ARR</div></div></div>""", unsafe_allow_html=True)
        
        # Documentation: Priority loading of Estimated Arrival
        eta = calc_eta_str(leg['times']['est_arr']) if data['status'] == "EN-ROUTE" else ""
        st.markdown(f"""<div class="fr-grid"><div><span class="spec-label">SCHED DEP</span><br><b>{fmt_t(leg['times']['sch_dep'])}</b></div><div><span class="spec-label">SCHED ARR</span><br><b>{fmt_t(leg['times']['sch_arr'])}</b></div><div><span class="spec-label">ACTUAL DEP</span><br><b>{fmt_t(leg['times']['act_dep'])}</b></div><div><span class="spec-label">EST/ACT ARR</span><br><b style="color:#28a745;">{fmt_t(leg['times']['act_arr'] or leg['times']['est_arr'])}{eta}</b></div></div>""", unsafe_allow_html=True)
        
        if telemetry:
            # Fixed terminology: Speed instead of Groundspeed
            alt_ft = int(float(telemetry.get('alt', 0)) * 3.28084)
            speed_kts = int(float(telemetry.get('speed', 0)) * 0.539957)
            st.markdown(f"""<div class="fr-telemetry"><div><span class="spec-label">ALTITUDE</span><br><b>{alt_ft:,} ft</b></div><div><span class="spec-label">SPEED</span><br><b>{speed_kts} kts</b></div></div>""", unsafe_allow_html=True)

# --- 5. INTERACTIVE RADAR ---

def show_interactive_radar():
    """Handles 5-min caching, Map persistence, and Radar Logic."""
    if "map_center" not in st.session_state: st.session_state.map_center = [1.35, 103.8]
    if "map_zoom" not in st.session_state: st.session_state.map_zoom = 4
    if "last_radar_fetch" not in st.session_state: st.session_state.last_radar_fetch = 0
    if "radar_data" not in st.session_state: st.session_state.radar_data = []

    col_info, col_map = st.columns([1.5, 2.5])
    
    # 5-minute session state timer logic
    time_elapsed = time.time() - st.session_state.last_radar_fetch
    refresh_needed = time_elapsed > 300
    
    with col_map:
        timer_col, refresh_col = st.columns([4, 1])
        with timer_col:
            remaining = max(0, int(300 - time_elapsed))
            st.markdown(f"<p class='timer-text'>Auto-refresh in: {remaining//60}m {remaining%60}s</p>", unsafe_allow_html=True)
        with refresh_col:
            if st.button("🔄 Sync"):
                st.session_state.last_radar_fetch = 0
                st.rerun()

    if refresh_needed:
        with st.empty().container():
            vid = get_b64("SQ loading screen.mp4")
            st.markdown(f"""<div style="text-align:center; padding:80px;"><video width="300" autoplay loop muted><source src="data:video/mp4;base64,{vid}" type="video/mp4"></video><p style="color:{SIA_NAVY}; font-weight:bold; margin-top:20px;">Syncing AirLabs Global Feed...</p></div>""", unsafe_allow_html=True)
            try:
                url = f"https://airlabs.co/api/v9/flights?airline_iata=SQ&api_key={st.secrets['AIRLABS_API_KEY']}"
                st.session_state.radar_data = requests.get(url, timeout=10).json().get("response", [])
                st.session_state.last_radar_fetch = time.time()
            except: pass
        st.rerun()

    m = folium.Map(location=st.session_state.map_center, zoom_start=st.session_state.map_zoom, 
                   tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', 
                   attr='Google', name='Google Hybrid', zoom_control=False)
    
    icon_b64 = get_b64("f5c530aa-d922-4920-9313-63a11c7f2921.png")
    for p in st.session_state.radar_data:
        lat, lon = p.get('lat'), p.get('lng')
        if lat and lon:
            html = f'<div style="transform: rotate({p.get("dir",0)}deg);"><img src="data:image/png;base64,{icon_b64}" width="28" height="28"></div>'
            folium.Marker([lat, lon], tooltip=p.get('flight_iata','SQ'), icon=folium.DivIcon(html=html, icon_size=(28,28))).add_to(m)

    with col_map:
        res = st_folium(m, width="100%", height=800, key="radar_main", use_container_width=True)
        if res.get("center"): st.session_state.map_center = [res["center"]["lat"], res["center"]["lng"]]
        if res.get("zoom"): st.session_state.map_zoom = res["zoom"]

    clicked = res.get("last_object_clicked_tooltip")
    with col_info:
        if clicked:
            p_data = next((x for x in st.session_state.radar_data if x.get('flight_iata') == clicked), {})
            render_fr24_card(clicked, telemetry=p_data)
        else:
            st.info("👈 Select an aircraft on the map to view detailed manifest.")
            st.markdown("<div class='section-header'>Active Air Manifest</div>", unsafe_allow_html=True)
            with st.container(height=650):
                for p in st.session_state.radar_data:
                    ac_type = p.get('aircraft_icao', 'N/A')
                    speed_kts = int(float(p.get('speed', 0)) * 0.539957)
                    st.markdown(f"**{p.get('flight_iata','SQ')}** ({ac_type})")
                    st.markdown(f"Speed: {speed_kts} kts | {p.get('dep_iata','---')} ➔ {p.get('arr_iata','---')}")
                    st.divider()

# --- 6. NAVIGATION ---

menu = st.sidebar.radio("MODE", ["📡 Radar", "🔍 Search", "🗺️ Wayfinding"])

if menu == "📡 Radar": 
    show_interactive_radar()

elif menu == "🔍 Search":
    st.title("🔍 Flight Search")
    c1, c2 = st.columns(2)
    f_num = c1.text_input("SQ Number", "11")
    f_date = c2.date_input("Departure Date")
    if st.button("EXECUTE SEARCH"):
        data = fetch_search_data(f_num, str(f_date))
        if data["leg"]: render_search_manifest(data)
        else: st.error("No flight found.")

elif menu == "🗺️ Wayfinding":
    st.title("🗺️ Changi Wayfinding")
    pdf = get_b64("Singapore-Changi-Airport-Transit-Area-Wayfinding.pdf")
    if pdf: st.markdown(f'<iframe src="data:application/pdf;base64,{pdf}" width="100%" height="950" style="border:none;"></iframe>', unsafe_allow_html=True)

st.sidebar.markdown("---")
st.sidebar.markdown(f"**KrisTracker Pro** v2.0.4  \n*Telemetry: AirLabs Live Feed*")
