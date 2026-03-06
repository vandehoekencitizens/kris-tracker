import streamlit as st
import requests, uuid, folium, base64, json, os, time, random
from streamlit_folium import st_folium
from datetime import datetime, timezone

# --- 1. CORE STYLING & ASSETS ---
st.set_page_config(page_title="KrisTracker Pro", page_icon="✈️", layout="wide")
SIA_NAVY, SIA_GOLD, FR_YELLOW = "#00266B", "#BD9B60", "#ffc107"

st.markdown(f"""<style>
    /* Shrink Sidebar and Mode Selection Area */
    [data-testid="stSidebar"] {{ min-width: 200px !important; max-width: 200px !important; }}
    
    /* Typography & Spacing */
    .spec-label {{ color: #666; font-size: 11px; text-transform: uppercase; font-weight: bold; letter-spacing: 0.8px; margin-bottom: 2px; }}
    .spec-value {{ color: {SIA_NAVY}; font-size: 17px; font-weight: 700; margin-bottom: 15px; font-family: 'Segoe UI', sans-serif; }}
    .time-box {{ background: #ffffff; padding: 12px; border-radius: 6px; border: 1px solid #d1d5db; border-left: 5px solid {SIA_GOLD}; }}
    .status-pill {{ background: {SIA_NAVY}; color: white; padding: 4px 12px; border-radius: 20px; font-size: 13px; font-weight: 600; text-transform: uppercase; }}
    .section-header {{ border-bottom: 2px solid #eee; padding-bottom: 5px; margin-bottom: 15px; color: #444; font-weight: 800; font-size: 14px; text-transform: uppercase; }}
    
    /* FR24 Sidebar/Info Panel Styling */
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

def get_b64(file_path):
    try:
        with open(file_path, "rb") as f:
            return base64.b64encode(f.read()).decode('utf-8')
    except: return ""

def get_ac_image(ac_code):
    code = str(ac_code).upper().strip()
    mapping = {
        "A359": "9V-SMI.jpg", "A388": "9V-SKY.jpg", "B38M": "9V-MBO.jpg",
        "78X": "9V-SCK.avif", "B78X": "9V-SCK.avif", "77W": "9V-SWR.jpg", "B77W": "9V-SWR.jpg"
    }
    return mapping.get(code)

def fmt_t(dt_str): return dt_str[-5:] if dt_str else "---"

def calc_eta_str(est_iso):
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

# --- 3. ADSB A/B TESTING ENGINE ---

def fetch_radar_data():
    log_file = "radar_speed_log.json"
    target_date = datetime(2026, 3, 16)
    now = datetime.now()
    if not os.path.exists(log_file):
        with open(log_file, "w") as f: json.dump({"adsb.fi": [], "adsb.lol": []}, f)
    with open(log_file, "r") as f: logs = json.load(f)

    if now < target_date:
        provider = random.choice(["adsb.fi", "adsb.lol"])
    else:
        avg_fi = sum(logs["adsb.fi"])/len(logs["adsb.fi"]) if logs["adsb.fi"] else 999
        avg_lol = sum(logs["adsb.lol"])/len(logs["adsb.lol"]) if logs["adsb.lol"] else 999
        provider = "adsb.fi" if avg_fi < avg_lol else "adsb.lol"

    url = f"https://api.{provider}/v2/callsign/SIA"
    start = time.time()
    try:
        res = requests.get(url, timeout=8).json()
        elapsed = time.time() - start
        if now < target_date:
            logs[provider].append(elapsed)
            with open(log_file, "w") as f: json.dump(logs, f)
        return res.get("ac", []), provider, elapsed
    except: return [], provider, 0

# --- 4. DATA FUSION (SEARCH & DATE VALIDATION) ---

def fetch_search_data(f_num, date_str):
    unified = {"source": "NONE", "leg": None, "status": "Unknown"}
    iata = f"SQ{f_num}".upper()
    try:
        url = "https://apigw.singaporeair.com/api/uat/v2/flightstatus/getbynumber"
        headers = {"api_key": st.secrets["SIA_STATUS_KEY"], "x-csl-client-id": "SPD", "x-csl-client-uuid": str(uuid.uuid4())}
        sq_res = requests.post(url, json={"airlineCode": "SQ", "flightNumber": f_num, "scheduledDepartureDate": date_str}, headers=headers, timeout=5).json()
        sq_data = sq_res.get("data", {}).get("response", {}).get("flights", [None])[0]
        if sq_data and sq_data.get("legs"):
            # Filter for requested date + Latest Leg Only
            valid_legs = [l for l in sq_data["legs"] if date_str in l.get("scheduledDepartureTime", "")]
            if valid_legs:
                latest = valid_legs[-1]
                unified = {
                    "source": "OFFICIAL SIA GATEWAY", "status": latest.get("flightStatus", "Unknown").upper(),
                    "leg": {
                        "fn": iata, "ac_type": latest.get("aircraftTypeCode"), "dep_iata": latest["origin"]["airportCode"], "arr_iata": latest["destination"]["airportCode"],
                        "dep_term": latest["origin"].get("airportTerminal") or "TBA", "arr_term": latest["destination"].get("airportTerminal") or "TBA",
                        "dep_gate": latest["origin"].get("gate") or "TBA", "arr_gate": latest["destination"].get("gate") or "TBA",
                        "times": {
                            "sch_dep": latest.get("scheduledDepartureTime"), "act_dep": latest.get("actualDepartureTime"),
                            "sch_arr": latest.get("scheduledArrivalTime"), "act_arr": latest.get("actualArrivalTime"), "est_arr": latest.get("estimatedArrivalTime")
                        }
                    }
                }
                return unified
    except: pass
    return unified

# --- 5. UI COMPONENTS ---

def render_fr24_card(flight_iata, telemetry=None):
    f_num = flight_iata.replace("SQ", "").replace("SIA", "").strip()
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
        </div>""", unsafe_allow_html=True)
        
        img = get_ac_image(leg['ac_type'])
        if img: st.image(img, use_container_width=True)
        
        st.markdown(f"""
        <div class="fr-route-box">
            <div style="text-align:left;"><div class="fr-city">{leg['dep_iata']}</div><div class="spec-label">DEPARTURE</div></div>
            <div style="font-size:30px; color:{FR_YELLOW}; transform:rotate(90deg);">✈</div>
            <div style="text-align:right;"><div class="fr-city">{leg['arr_iata']}</div><div class="spec-label">ARRIVAL</div></div>
        </div>""", unsafe_allow_html=True)
        
        eta_str = calc_eta_str(leg['times']['est_arr']) if data['status'] == "EN-ROUTE" else ""
        
        st.markdown(f"""
        <div class="fr-grid">
            <div><span class="spec-label">SCHEDULED DEP</span><br><b>{fmt_t(leg['times']['sch_dep'])}</b></div>
            <div><span class="spec-label">SCHEDULED ARR</span><br><b>{fmt_t(leg['times']['sch_arr'])}</b></div>
            <div><span class="spec-label">ACTUAL DEP</span><br><b>{fmt_t(leg['times']['act_dep'])}</b></div>
            <div><span class="spec-label">ESTIMATED ARR</span><br><b style="color:#28a745;">{fmt_t(leg['times']['act_arr'] or leg['times']['est_arr'])}{eta_str}</b></div>
        </div>""", unsafe_allow_html=True)
        
        if telemetry:
            st.markdown(f"""
            <div class="fr-telemetry">
                <div><span class="spec-label">ALTITUDE</span><br><b>{telemetry.get('alt_baro', 0):,} ft</b></div>
                <div><span class="spec-label">GROUNDSPEED</span><br><b>{telemetry.get('gs', 0)} kts</b></div>
            </div>""", unsafe_allow_html=True)

def show_interactive_radar():
    col_info, col_map = st.columns([1.5, 2])
    
    load_placeholder = st.empty()
    with load_placeholder.container():
        vid_data = get_b64("SQ loading screen.mp4")
        st.markdown(f"""<div style="text-align:center;padding:40px;">
            <video width="280" autoplay loop muted><source src="data:video/mp4;base64,{vid_data}" type="video/mp4"></video>
            <p style="color:{SIA_NAVY};font-weight:bold;margin-top:10px;">Syncing with Global ADSB Network...</p>
        </div>""", unsafe_allow_html=True)
        planes, provider, l_time = fetch_radar_data()
    load_placeholder.empty()

    m = folium.Map(location=[1.35, 103.8], zoom_start=4, tiles="CartoDB dark_matter")
    plane_icon_b64 = get_b64("f5c530aa-d922-4920-9313-63a11c7f2921.png")
    
    for p in planes:
        lat, lon = p.get('lat'), p.get('lon')
        if lat and lon:
            heading = p.get('track', 0)
            f_iata = p.get('flight', 'SQ---').strip()
            html = f'<div style="transform: rotate({heading}deg);"><img src="data:image/png;base64,{plane_icon_b64}" width="28" height="28"></div>'
            folium.Marker([lat, lon], tooltip=f_iata, icon=folium.DivIcon(html=html, icon_size=(28,28))).add_to(m)

    with col_map:
        st.caption(f"⚡ Live provider: {provider} | Latency: {l_time:.2f}s")
        map_data = st_folium(m, width="100%", height=750, key="radar_main")
    
    clicked = map_data.get("last_object_clicked_tooltip")
    with col_info:
        if clicked:
            # Find raw telemetry for the clicked plane
            p_data = next((x for x in planes if x.get('flight', '').strip() == clicked), {})
            render_fr24_card(clicked, telemetry=p_data)
        else:
            st.info("👈 Select an aircraft on the map to view full telemetry.")
            with st.container(height=500):
                for p in planes:
                    st.markdown(f"**{p.get('flight','SQ')}** | Alt: {p.get('alt_baro',0)}ft | {p.get('gs',0)}kts")
                    st.divider()

# --- 6. NAVIGATION ---

menu = st.sidebar.radio("MODE", ["📡 Radar", "🔍 Search", "🗺️ Wayfinding"])

if menu == "📡 Radar":
    show_interactive_radar()
elif menu == "🔍 Search":
    c1, c2 = st.columns(2)
    f_num = c1.text_input("SQ Number", "11")
    f_date = c2.date_input("Departure Date")
    if st.button("EXECUTE SEARCH"):
        data = fetch_search_data(f_num, str(f_date))
        if data["leg"]:
            st.markdown("<div class='section-header'>Manifest Results</div>", unsafe_allow_html=True)
            render_fr24_card(f"SQ{f_num}") # Reuse the card for consistency
        else:
            st.error("Flight not found for this departure date.")
elif menu == "Changi Aiport Wayfinding":
    pdf_b64 = get_b64("Singapore-Changi-Airport-Transit-Area-Wayfinding.pdf")
    st.markdown(f'<iframe src="data:application/pdf;base64,{pdf_b64}" width="100%" height="900"></iframe>', unsafe_allow_html=True)
