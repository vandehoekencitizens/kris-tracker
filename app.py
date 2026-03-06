import streamlit as st
import requests, uuid, math, folium, base64
from streamlit_folium import st_folium
from datetime import datetime, timezone

# --- 1. CORE STYLING & ASSETS ---
st.set_page_config(page_title="KrisTracker Pro", page_icon="✈️", layout="wide")
SIA_NAVY, SIA_GOLD = "#00266B", "#BD9B60"
FR_YELLOW = "#ffc107"

st.markdown(f"""<style>
    .spec-label {{ color: #666; font-size: 11px; text-transform: uppercase; font-weight: bold; letter-spacing: 0.8px; margin-bottom: 2px; }}
    .spec-value {{ color: {SIA_NAVY}; font-size: 17px; font-weight: 700; margin-bottom: 15px; font-family: 'Segoe UI', sans-serif; }}
    .time-box {{ background: #ffffff; padding: 12px; border-radius: 6px; border: 1px solid #d1d5db; border-left: 5px solid {SIA_GOLD}; }}
    .status-pill {{ background: {SIA_NAVY}; color: white; padding: 4px 12px; border-radius: 20px; font-size: 13px; font-weight: 600; text-transform: uppercase; }}
    .section-header {{ border-bottom: 2px solid #eee; padding-bottom: 5px; margin-bottom: 15px; color: #444; font-weight: 800; font-size: 14px; text-transform: uppercase; }}
    
    /* FR24 Sidebar Styling */
    .fr-header {{ display: flex; align-items: baseline; gap: 10px; padding: 10px 0; border-bottom: 1px solid #444; }}
    .fr-callsign {{ color: {FR_YELLOW}; font-size: 26px; font-weight: 900; }}
    .fr-iata {{ background: #ddd; color: #333; padding: 2px 6px; border-radius: 4px; font-size: 14px; font-weight: bold; }}
    .fr-type {{ background: #4a6491; color: white; padding: 2px 6px; border-radius: 4px; font-size: 14px; font-weight: bold; }}
    .fr-route-box {{ display: flex; justify-content: space-between; align-items: center; margin: 15px 0; }}
    .fr-city {{ font-size: 40px; font-weight: 300; line-height: 1; }}
    .fr-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; background: #f4f4f4; padding: 15px; border-radius: 8px; }}
    .fr-telemetry {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-top: 15px; padding-top: 15px; border-top: 1px solid #ddd; }}
</style>""", unsafe_allow_html=True)

# --- 2. HELPER FUNCTIONS ---

def get_ac_image(ac_code):
    """Strict mapping of ICAO codes to your specific uploaded files."""
    code = str(ac_code).upper().strip()
    if code in ["A359"]: return "9V-SMI.jpg"
    if code in ["A388"]: return "9V-SKY.jpg"
    if code in ["B38M"]: return "9V-MBO.jpg"
    if code in ["78X", "B78X"]: return "9V-SCK.avif"
    if code in ["77W", "B77W"]: return "9V-SWR.jpg"
    return None # 747 dropped as requested

def calc_eta_str(est_iso):
    """Calculates live ETA countdown string."""
    try:
        est = datetime.fromisoformat(est_iso.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = (est - now).total_seconds()
        if delta > 0:
            h, rem = divmod(int(delta), 3600)
            m, _ = divmod(rem, 60)
            return f" (In {h}h {m}m)"
        return " (Arriving shortly)"
    except: return ""

def fmt_t(dt_str): return dt_str[-5:] if dt_str else "---"

# --- 3. DATA FUSION ENGINE (Date Validation & Latest Leg Logic) ---

def fetch_search_data(f_num, date_str):
    unified = {"source": "NONE", "leg": None, "status": "Unknown"}
    iata = f"SQ{f_num}".upper()
    
    # Priority 1: SQ API (Best for Historical/Future Date verification)
    try:
        url = "https://apigw.singaporeair.com/api/uat/v2/flightstatus/getbynumber"
        headers = {"api_key": st.secrets["SIA_STATUS_KEY"], "x-csl-client-id": "SPD", "x-csl-client-uuid": str(uuid.uuid4())}
        sq_res = requests.post(url, json={"airlineCode": "SQ", "flightNumber": f_num, "scheduledDepartureDate": date_str}, headers=headers, timeout=5).json()
        sq_data = sq_res.get("data", {}).get("response", {}).get("flights", [None])[0]
        
        if sq_data and sq_data.get("legs"):
            # Filter legs matching the exact departure date requested
            valid_legs = [l for l in sq_data["legs"] if date_str in l.get("scheduledDepartureTime", "")]
            if valid_legs:
                latest_leg = valid_legs[-1] # ONLY grab the latest leg (no layovers)
                unified["source"] = "OFFICIAL SIA GATEWAY"
                unified["status"] = latest_leg.get("flightStatus", "Unknown").upper()
                unified["leg"] = {
                    "fn": iata,
                    "ac_type": latest_leg.get("aircraftTypeCode", "N/A"),
                    "dep_iata": latest_leg["origin"].get("airportCode"),
                    "arr_iata": latest_leg["destination"].get("airportCode"),
                    "dep_term": latest_leg["origin"].get("airportTerminal") or "TBA",
                    "arr_term": latest_leg["destination"].get("airportTerminal") or "TBA",
                    "dep_gate": latest_leg["origin"].get("gate") or "TBA",
                    "arr_gate": latest_leg["destination"].get("gate") or "TBA",
                    "times": {
                        "sch_dep": latest_leg.get("scheduledDepartureTime"),
                        "act_dep": latest_leg.get("actualDepartureTime"),
                        "sch_arr": latest_leg.get("scheduledArrivalTime"),
                        "act_arr": latest_leg.get("actualArrivalTime"),
                        "est_arr": latest_leg.get("estimatedArrivalTime")
                    }
                }
                return unified
    except: pass

    # Fallback to AirLabs if active flight today
    try:
        url = f"https://airlabs.co/api/v9/flight?api_key={st.secrets['AIRLABS_API_KEY']}&flight_iata={iata}"
        al = requests.get(url, timeout=5).json().get("response")
        if al and date_str in al.get("dep_time", ""):
            unified["source"] = "AIRLABS OPERATIONS (FALLBACK)"
            unified["status"] = al.get("status", "Unknown").upper()
            unified["leg"] = {
                "fn": iata,
                "ac_type": al.get("aircraft_icao", "N/A"),
                "dep_iata": al.get("dep_iata"), "arr_iata": al.get("arr_iata"),
                "dep_term": al.get("dep_terminal") or "TBA", "arr_term": al.get("arr_terminal") or "TBA",
                "dep_gate": al.get("dep_gate") or "TBA", "arr_gate": al.get("arr_gate") or "TBA",
                "times": {
                    "sch_dep": al.get("dep_time"), "act_dep": al.get("dep_actual"),
                    "sch_arr": al.get("arr_time"), "act_arr": al.get("arr_actual"), "est_arr": al.get("arr_estimated")
                }
            }
            return unified
    except: pass
    
    return unified

# --- 4. FLIGHT SEARCH UI ---

def render_search_manifest(data):
    st.markdown(f"**Data Source:** {data['source']}")
    leg = data["leg"]
    
    # SIN Terminal Override Logic
    arr_terminal = leg['arr_term']
    if leg['arr_iata'] == "SIN" and arr_terminal == "TBA":
        arr_terminal = "Terminal 2/3"
        
    st.markdown(f"### <span class='status-pill'>{data['status']}</span>", unsafe_allow_html=True)
    
    # Information Row
    st.markdown("<div class='section-header'>Flight & Aircraft Information</div>", unsafe_allow_html=True)
    r1_c1, r1_c2, r1_c3, r1_c4 = st.columns(4)
    with r1_c1: st.markdown(f"<div class='spec-label'>Flight Number</div><div class='spec-value'>{leg['fn']}</div>", unsafe_allow_html=True)
    with r1_c2: st.markdown(f"<div class='spec-label'>Aircraft Type</div><div class='spec-value'>{leg['ac_type']}</div>", unsafe_allow_html=True)
    with r1_c3: st.markdown(f"<div class='spec-label'>Departure Airport</div><div class='spec-value'>{leg['dep_iata']}</div>", unsafe_allow_html=True)
    with r1_c4: st.markdown(f"<div class='spec-label'>Arrival Airport</div><div class='spec-value'>{leg['arr_iata']}</div>", unsafe_allow_html=True)

    # Terminals Row
    st.markdown("<div class='section-header'>Terminal & Gate Assignments</div>", unsafe_allow_html=True)
    r2_c1, r2_c2, r2_c3, r2_c4 = st.columns(4)
    with r2_c1: st.markdown(f"<div class='spec-label'>Departure Terminal</div><div class='spec-value'>{leg['dep_term']}</div>", unsafe_allow_html=True)
    with r2_c2: st.markdown(f"<div class='spec-label'>Arrival Terminal</div><div class='spec-value'>{arr_terminal}</div>", unsafe_allow_html=True)
    with r2_c3: st.markdown(f"<div class='spec-label'>Departure Gate</div><div class='spec-value'>{leg['dep_gate']}</div>", unsafe_allow_html=True)
    with r2_c4: st.markdown(f"<div class='spec-label'>Arrival Gate</div><div class='spec-value'>{leg['arr_gate']}</div>", unsafe_allow_html=True)

    # Schedule Row
    st.markdown("<div class='section-header'>Departure Details</div>", unsafe_allow_html=True)
    d1, d2 = st.columns(2)
    with d1: st.markdown(f"<div class='spec-label'>Scheduled Departure</div><div class='time-box'>{leg['times']['sch_dep']}</div>", unsafe_allow_html=True)
    with d2:
        val = leg['times']['act_dep'] if leg['times']['act_dep'] else "---"
        st.markdown(f"<div class='spec-label'>Actual Departure</div><div class='time-box'>{val}</div>", unsafe_allow_html=True)

    st.markdown("<div class='section-header'>Arrival Details</div>", unsafe_allow_html=True)
    a1, a2, a3 = st.columns(3)
    with a1: st.markdown(f"<div class='spec-label'>Scheduled Arrival</div><div class='time-box'>{leg['times']['sch_arr']}</div>", unsafe_allow_html=True)
    with a2:
        val = leg['times']['est_arr'] if leg['times']['est_arr'] else "---"
        st.markdown(f"<div class='spec-label'>Estimated Arrival</div><div class='time-box'>{val}</div>", unsafe_allow_html=True)
    with a3:
        val = leg['times']['act_arr'] if leg['times']['act_arr'] else "---"
        st.markdown(f"<div class='spec-label'>Actual Arrival</div><div class='time-box'>{val}</div>", unsafe_allow_html=True)

# --- 5. INTERACTIVE RADAR (FR24 STYLE) ---

def render_fr24_card(flight_iata):
    f_num = flight_iata.replace("SQ", "").strip()
    
    # Use today's date to fetch live telemetry
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    data = fetch_search_data(f_num, today_str) 
    
    if data["leg"]:
        leg = data["leg"]
        arr_terminal = "Terminal 2/3" if (leg['arr_iata'] == "SIN" and leg['arr_term'] == "TBA") else leg['arr_term']
        
        st.markdown(f"""
        <div class="fr-header">
            <span class="fr-callsign">SIA{f_num}</span>
            <span class="fr-iata">{leg['fn']}</span>
            <span class="fr-type">{leg['ac_type']}</span>
        </div>
        <div style="color: #ccc; font-size: 14px; margin-bottom: 10px;">Singapore Airlines</div>
        """, unsafe_allow_html=True)
        
        img_file = get_ac_image(leg['ac_type'])
        if img_file:
            try: st.image(img_file, use_container_width=True)
            except: st.caption(f"[Image {img_file} not found]")
        
        st.markdown(f"""
        <div class="fr-route-box">
            <div style="text-align: left;"><div class="fr-city">{leg['dep_iata']}</div><div style="color: #888; font-size: 12px; font-weight:bold;">DEPARTURE</div></div>
            <div style="font-size: 30px; color: {FR_YELLOW}; transform: rotate(90deg);">✈</div>
            <div style="text-align: right;"><div class="fr-city">{leg['arr_iata']}</div><div style="color: #888; font-size: 12px; font-weight:bold;">ARRIVAL</div></div>
        </div>
        """, unsafe_allow_html=True)
        
        eta_str = calc_eta_str(leg['times']['est_arr']) if data['status'] == "EN-ROUTE" else ""
        
        st.markdown(f"""
        <div class="fr-grid">
            <div><span style="color:#888; font-size:12px;">SCHEDULED</span><br><b>{fmt_t(leg['times']['sch_dep'])}</b></div>
            <div><span style="color:#888; font-size:12px;">SCHEDULED</span><br><b>{fmt_t(leg['times']['sch_arr'])}</b></div>
            <div><span style="color:#888; font-size:12px;">ACTUAL</span><br><b>{fmt_t(leg['times']['act_dep'])}</b></div>
            <div><span style="color:#888; font-size:12px;">ESTIMATED/ACTUAL</span><br><b style="color:#28a745;">{fmt_t(leg['times']['act_arr'] or leg['times']['est_arr'])} {eta_str}</b></div>
        </div>
        """, unsafe_allow_html=True)

def show_interactive_radar():
    col_info, col_map = st.columns([1, 2.5])
    
    with st.spinner("Scanning Airspace..."):
        try: planes = requests.get(f"https://airlabs.co/api/v9/flights?airline_iata=SQ&api_key={st.secrets['AIRLABS_API_KEY']}").json().get("response", [])
        except: planes = []

    m = folium.Map(location=[1.35, 103.8], zoom_start=4, tiles="CartoDB dark_matter")
    
    for p in planes:
        if p.get('lat') and p.get('lng'):
            heading = p.get('dir', 0)
            # Direct HTML image tag pointing to the uploaded file, no base64 encoding needed
            html = f'<div style="transform: rotate({heading}deg);"><img src="f5c530aa-d922-4920-9313-63a11c7f2921.png" width="28" height="28"></div>'
            
            folium.Marker(
                [p['lat'], p['lng']], 
                tooltip=p.get('flight_iata', 'SQ---'),
                icon=folium.DivIcon(html=html, icon_size=(28, 28), icon_anchor=(14, 14))
            ).add_to(m)
            
    with col_map:
        map_data = st_folium(m, width="100%", height=800, return_on_hover=False)
        
    clicked_flight = map_data.get("last_object_clicked_tooltip")
    
    with col_info:
        if clicked_flight: render_fr24_card(clicked_flight)
        else:
            st.info("👈 **Select an aircraft on the map** to view telemetry and aircraft type.")
            with st.container(height=650):
                for p in planes:
                    st.markdown(f"**{p.get('flight_iata')}** | {p.get('dep_iata')} ➔ {p.get('arr_iata')} | {p.get('alt',0):,} ft")
                    st.divider()

# --- 6. APP NAVIGATION ---

st.sidebar.title("🛠️ KrisTracker Pro")
menu = st.sidebar.radio("Navigate", ["Interactive Radar", "Flight Search", "Wayfinding PDF"])

if menu == "Interactive Radar":
    show_interactive_radar()

elif menu == "Flight Search":
    c1, c2 = st.columns(2)
    f_num = c1.text_input("SQ Number", "11")
    f_date = c2.date_input("Date of Departure")
    if st.button("EXECUTE SEARCH"):
        data = fetch_search_data(f_num, str(f_date))
        if data["leg"]:
            render_search_manifest(data)
        else:
            st.error("⚠️ Flight not found or departure date does not match API schedule data.")

elif menu == "Wayfinding PDF":
    try:
        with open("Singapore-Changi-Airport-Transit-Area-Wayfinding.pdf", "rb") as f:
            base64_pdf = base64.b64encode(f.read()).decode('utf-8')
        st.markdown(f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800"></iframe>', unsafe_allow_html=True)
    except: st.error("PDF Wayfinding file missing.")
