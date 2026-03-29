import streamlit as st
import requests, uuid, math, folium, base64, json, os, time
from streamlit_folium import st_folium
from datetime import datetime, timezone

# --- 1. CORE STYLING & ASSETS ---
st.set_page_config(page_title="KrisTracker Pro v2.0", page_icon="✈️", layout="wide")
SIA_NAVY, SIA_GOLD, FR_YELLOW = "#00266B", "#BD9B60", "#ffc107"

st.markdown(f"""<style>
[data-testid="stSidebar"] {{ min-width: 210px !important; max-width: 210px !important; }}

.spec-label {{ color: #666; font-size: 11px; font-weight: bold; }}
.spec-value {{ color: {SIA_NAVY}; font-size: 17px; font-weight: 700; }}
.time-box {{ background: #fff; padding: 12px; border-left: 5px solid {SIA_GOLD}; }}

.status-pill {{ background: {SIA_NAVY}; color: white; padding: 4px 12px; border-radius: 20px; }}

.fr-header {{ display:flex; gap:10px; border-bottom:1px solid #444; }}
.fr-callsign {{ color:{FR_YELLOW}; font-size:26px; font-weight:900; }}
.fr-city {{ font-size:40px; }}

.timer-text {{ font-size:12px; color:{SIA_NAVY}; text-align:right; }}
</style>""", unsafe_allow_html=True)

# --- HELPERS ---

def get_b64(file_path):
    try:
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                return base64.b64encode(f.read()).decode()
    except: pass
    return ""

def fmt_t(dt):
    return dt[-5:] if dt else "---"

def calc_eta_str(est_iso):
    try:
        est = datetime.fromisoformat(est_iso.replace("Z","+00:00"))
        delta = (est - datetime.now(timezone.utc)).total_seconds()
        if delta > 0:
            h = int(delta // 3600)
            m = int((delta % 3600)//60)
            return f" (In {h}h {m}m)"
    except: pass
    return ""

# --- DATA ---

@st.cache_data(ttl=300)
def fetch_search_data(f_num, date_str):
    iata = f"SQ{f_num}"
    unified = {"leg":None,"status":"Unknown","source":"NONE"}

    try:
        url = f"https://airlabs.co/api/v9/flight?api_key={st.secrets['AIRLABS_API_KEY']}&flight_iata={iata}"
        res = requests.get(url, timeout=5).json()
        al = res.get("response")

        if al:
            unified["source"] = "AIRLABS"
            unified["status"] = al.get("status","Unknown").upper()
            unified["leg"] = {
                "fn": iata,
                "ac_type": al.get("aircraft_icao","N/A"),
                "dep_iata": al.get("dep_iata","---"),
                "arr_iata": al.get("arr_iata","---"),
                "dep_gate": al.get("dep_gate","TBA"),
                "arr_gate": al.get("arr_gate","TBA"),
                "times":{
                    "sch_dep": al.get("dep_time"),
                    "sch_arr": al.get("arr_time"),
                    "act_dep": al.get("dep_actual"),
                    "act_arr": al.get("arr_actual"),
                    "est_arr": al.get("arr_estimated")
                }
            }
    except:
        pass

    return unified

# --- UI ---

def render_search_manifest(data):
    leg = data["leg"]
    st.markdown(f"### {leg['fn']} — {data['status']}")

    st.write("Departure:", leg['dep_iata'])
    st.write("Arrival:", leg['arr_iata'])
    st.write("Scheduled Dep:", leg['times']['sch_dep'])
    st.write("Scheduled Arr:", leg['times']['sch_arr'])

def render_fr24_card(flight_iata, telemetry):
    data = fetch_search_data(flight_iata.replace("SQ",""), str(datetime.now().date()))
    if not data["leg"]: return

    leg = data["leg"]
    eta = calc_eta_str(leg["times"]["est_arr"]) if data["status"]=="EN-ROUTE" else ""

    st.markdown(f"## {flight_iata}")
    st.write(f"{leg['dep_iata']} → {leg['arr_iata']}")
    st.write("ETA:", fmt_t(leg["times"]["est_arr"]), eta)

    if telemetry:
        st.write("Altitude:", telemetry.get("alt"))
        st.write("Speed:", telemetry.get("speed"))

# --- RADAR ---

def show_interactive_radar():
    if "radar_data" not in st.session_state:
        st.session_state.radar_data = []

    if st.button("🔄 Refresh"):
        try:
            url = f"https://airlabs.co/api/v9/flights?airline_iata=SQ&api_key={st.secrets['AIRLABS_API_KEY']}"
            st.session_state.radar_data = requests.get(url).json().get("response", [])
        except:
            pass

    m = folium.Map(location=[1.35,103.8], zoom_start=4)

    for p in st.session_state.radar_data:
        if p.get("lat") and p.get("lng"):
            folium.Marker(
                [p["lat"], p["lng"]],
                tooltip=p.get("flight_iata","SQ")
            ).add_to(m)

    res = st_folium(m, height=600)

    clicked = res.get("last_object_clicked_tooltip")

    if clicked:
        p_data = next((x for x in st.session_state.radar_data if x.get("flight_iata")==clicked), None)
        render_fr24_card(clicked, p_data)

# --- NAV ---

menu = st.sidebar.radio("MODE", ["📡 Radar","🔍 Search","🗺️ Wayfinding"])

if menu=="📡 Radar":
    show_interactive_radar()

elif menu=="🔍 Search":
    f_num = st.text_input("Flight","11")
    f_date = st.date_input("Date")

    if st.button("Search"):
        data = fetch_search_data(f_num, str(f_date))
        if data["leg"]:
            render_search_manifest(data)

elif menu=="🗺️ Wayfinding":
    pdf = get_b64("Singapore-Changi-Airport-Transit-Area-Wayfinding.pdf")
    if pdf:
        st.markdown(f'<iframe src="data:application/pdf;base64,{pdf}" width="100%" height="900"></iframe>', unsafe_allow_html=True)

st.sidebar.markdown("KrisTracker Pro v2.0.4")
