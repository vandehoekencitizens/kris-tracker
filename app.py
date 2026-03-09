import streamlit as st
import requests, uuid, folium, base64, os
from streamlit_folium import st_folium
from datetime import datetime, timezone, timedelta
from math import radians, cos, sin, asin, sqrt

# --- 1. SETTINGS & CSS ---
st.set_page_config(page_title="KrisTracker Pro", page_icon="✈️", layout="wide")
SIA_NAVY, SIA_GOLD, FR_YELLOW = "#00266B", "#BD9B60", "#ffc107"

st.markdown(f"""<style>
    [data-testid="stSidebar"] {{ min-width: 300px !important; }}
    .fr-header {{ display: flex; align-items: baseline; gap: 10px; padding: 10px 0; border-bottom: 1px solid #444; }}
    .fr-callsign {{ color: {FR_YELLOW}; font-size: 28px; font-weight: 900; }}
    .fr-type {{ background: #4a6491; color: white; padding: 2px 8px; border-radius: 4px; font-size: 14px; font-weight: bold; }}
    .fr-city {{ font-size: 36px; font-weight: 600; line-height: 1; color: {SIA_NAVY}; }}
    .utc-offset {{ font-size: 11px; color: #888; margin-top: -2px; font-family: monospace; }}
    .dist-text {{ font-size: 12px; color: #555; font-weight: 600; margin-bottom: 2px; }}
    .spec-label {{ color: #888; font-size: 10px; text-transform: uppercase; font-weight: bold; letter-spacing: 0.5px; }}
    .fr-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; background: #f8f9fa; padding: 12px; border-radius: 8px; border: 1px solid #eee; }}
    .section-header {{ border-bottom: 1px solid #ddd; padding-bottom: 5px; margin: 20px 0 10px 0; color: #444; font-weight: bold; font-size: 12px; text-transform: uppercase; }}
    .progress-bar-bg {{ width:100%; height:8px; background:#e0e0e0; border-radius:4px; margin: 8px 0; position: relative; }}
    .progress-bar-fill {{ height:100%; background:{SIA_GOLD}; border-radius:4px; }}
</style>""", unsafe_allow_html=True)

# --- 2. CORE HELPERS & DATA ---

def haversine(lat1, lon1, lat2, lon2):
    R = 6371 
    dLat, dLon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dLat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dLon/2)**2
    return 2 * R * asin(sqrt(a))

def get_b64(file_path):
    try:
        if os.path.exists(file_path):
            with open(file_path, "rb") as f: return base64.b64encode(f.read()).decode('utf-8')
    except: pass
    return ""

def get_ac_image(ac_code):
    mapping = {
        "A359": "9V-SMI.jpg", "A388": "9V-SKY.jpg", "B38M": "9V-MBO.jpg",
        "78X": "9V-SCK.avif", "B78X": "9V-SCK.avif", "77W": "9V-SWR.jpg"
    }
    return mapping.get(str(ac_code).upper().strip())

def fmt_t(dt_str): 
    if not dt_str: return "---"
    return dt_str[11:16] if "T" in dt_str else dt_str[-8:-3]

def fetch_sia_official(f_num, date_str):
    try:
        url = "https://apigw.singaporeair.com/api/uat/v2/flightstatus/getbynumber"
        headers = {"api_key": st.secrets["SIA_STATUS_KEY"], "x-csl-client-id": "SPD", "x-csl-client-uuid": str(uuid.uuid4())}
        res = requests.post(url, json={"airlineCode": "SQ", "flightNumber": f_num, "scheduledDepartureDate": date_str}, headers=headers, timeout=5).json()
        return res.get("data", {}).get("response", {}).get("flights", [None])[0]
    except: return None

def get_airlabs_live(flight_iata):
    try:
        url = f"https://airlabs.co/api/v9/flight?api_key={st.secrets['AIRLABS_API_KEY']}&flight_iata={flight_iata}"
        return requests.get(url, timeout=5).json().get("response", {})
    except: return {}

def get_flight_trail(flight_iata):
    try:
        url = f"https://airlabs.co/api/v9/track?api_key={st.secrets['AIRLABS_API_KEY']}&flight_iata={flight_iata}"
        history = requests.get(url, timeout=5).json().get("response", [])
        return [[p['lat'], p['lng']] for p in history if 'lat' in p]
    except: return []

# --- 3. UI SECTIONS ---

def render_fr24_card(flight_iata):
    """The detailed Sidebar for the Interactive Radar"""
    al = get_airlabs_live(flight_iata)
    if not al:
        st.error("No live data available.")
        return

    st.markdown(f"""
        <div class="fr-header"><span class="fr-callsign">{flight_iata}</span>
        <span class="fr-type">{al.get('aircraft_icao', '---')}</span></div>
        <div style="font-size:15px; margin-bottom:15px; color:#555;">Singapore Airlines</div>
    """, unsafe_allow_html=True)
    
    img = get_ac_image(al.get('aircraft_icao'))
    if img: st.image(img, use_container_width=True)

    # City Pair & UTC
    c1, c2, c3 = st.columns([2,1,2])
    with c1:
        st.markdown(f'<div class="fr-city">{al.get("dep_iata", "---")}</div>', unsafe_allow_html=True)
        st.markdown('<div class="utc-offset">+08 (UTC +08:00)</div>', unsafe_allow_html=True)
    with c2: st.markdown("<h2 style='text-align:center; color:#ddd; margin-top:5px;'>✈</h2>", unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="fr-city" style="text-align:right;">{al.get("arr_iata", "---")}</div>', unsafe_allow_html=True)
        st.markdown('<div class="utc-offset" style="text-align:right;">+08 (UTC +08:00)</div>', unsafe_allow_html=True)

    # Progress & Distance
    if al.get('lat') and al.get('arr_lat'):
        d_total = haversine(al['dep_lat'], al['dep_lng'], al['arr_lat'], al['arr_lng'])
        d_rem = haversine(al['lat'], al['lng'], al['arr_lat'], al['arr_lng'])
        d_cov = d_total - d_rem
        pct = max(0, min(100, (d_cov / d_total) * 100))
        ete_mins = int((d_rem / al.get('speed', 400)) * 60) if al.get('speed', 0) > 0 else 0
        st.markdown(f"""
            <div style="margin-top:15px;">
                <div class="dist-text">{int(d_cov)} km covered</div>
                <div class="progress-bar-bg"><div class="progress-bar-fill" style="width:{pct}%;"></div></div>
                <div class="dist-text" style="text-align:right;">{int(d_rem)} km, in {ete_mins // 60:02d}:{ete_mins % 60:02d}</div>
            </div>
        """, unsafe_allow_html=True)

    # Schedule & Aircraft
    st.markdown(f"""<div class="fr-grid">
        <div><span class="spec-label">Actual Dep</span><br><b>{fmt_t(al.get('dep_actual'))}</b></div>
        <div><span class="spec-label">Est. Arr</span><br><b style="color:green;">{fmt_t(al.get('arr_estimated'))}</b></div>
    </div>""", unsafe_allow_html=True)

    st.markdown("<div class='section-header'>Aircraft Details</div>", unsafe_allow_html=True)
    st.markdown(f"""<div class="fr-grid">
        <div style="grid-column: span 2;"><span class="spec-label">Type</span><br><b>{al.get('model', '---')}</b></div>
        <div><span class="spec-label">Registration</span><br><b>{al.get('reg_number', '---')}</b></div>
        <div><span class="spec-label">Altitude</span><br><b>{al.get('alt', 0):,} ft</b></div>
    </div>""", unsafe_allow_html=True)

def show_flight_status():
    """Restored: Flight Search Feature"""
    st.title("🔍 Flight Status Search")
    f_num = st.text_input("Enter Flight Number (e.g., 103)", "103")
    date_val = st.date_input("Departure Date", datetime.now())
    if st.button("Check Status"):
        res = fetch_sia_official(f_num, date_val.strftime("%Y-%m-%d"))
        if res:
            st.success(f"SQ{f_num} - {res.get('flightStatus', 'Unknown')}")
            st.json(res)
        else:
            st.error("Flight not found.")

def show_wayfinding():
    """Restored: Wayfinding Menu"""
    st.title("📍 Airport Wayfinding")
    st.info("Interactive Terminal Maps & Gate Navigation coming soon.")
    # Add your map code here...

# --- 4. MAIN INTERACTIVE RADAR ---

def show_interactive_radar():
    if "map_center" not in st.session_state: st.session_state.map_center = [1.35, 103.8]
    if "map_zoom" not in st.session_state: st.session_state.map_zoom = 5

    col_info, col_map = st.columns([1.5, 2])

    try: 
        planes = requests.get(f"https://airlabs.co/api/v9/flights?airline_iata=SQ&api_key={st.secrets['AIRLABS_API_KEY']}").json().get("response", [])
    except: planes = []

    with col_map:
        m = folium.Map(location=st.session_state.map_center, zoom_start=st.session_state.map_zoom, tiles="CartoDB dark_matter")
        icon_b64 = get_b64("f5c530aa-d922-4920-9313-63a11c7f2921.png")
        
        for p in planes:
            if p.get('lat'):
                angle = p.get('dir', 0)
                html = f'<div style="transform: rotate({angle}deg);"><img src="data:image/png;base64,{icon_b64}" width="28"></div>'
                folium.Marker([p['lat'], p['lng']], tooltip=p['flight_iata'], icon=folium.DivIcon(html=html)).add_to(m)

        map_res = st_folium(m, width="100%", height=850, key="radar_stable", returned_objects=["last_object_clicked_tooltip", "center", "zoom"])

        # Prevent reset on interaction
        if map_res.get("center"): st.session_state.map_center = [map_res["center"]["lat"], map_res["center"]["lng"]]
        if map_res.get("zoom"): st.session_state.map_zoom = map_res["zoom"]

    with col_info:
        clicked = map_res.get("last_object_clicked_tooltip")
        if clicked:
            render_fr24_card(clicked)
        else:
            st.info("✈️ Click an aircraft on the map.")

# --- 5. NAVIGATION ---
menu = st.sidebar.radio("KrisTracker Menu", ["Interactive Radar", "Flight Status", "Wayfinding"])

if menu == "Interactive Radar":
    show_interactive_radar()
elif menu == "Flight Status":
    show_flight_status()
elif menu == "Wayfinding":
    show_wayfinding()
