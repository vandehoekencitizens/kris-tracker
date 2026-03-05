import streamlit as st
import requests, uuid, math, folium, base64
from streamlit_folium import st_folium
from datetime import datetime

# --- 1. STYLING ---
st.set_page_config(page_title="KrisTracker Pro", page_icon="✈️", layout="wide")
SIA_NAVY, SIA_GOLD = "#00266B", "#BD9B60"

st.markdown(f"""<style>
    .spec-label {{ color: #666; font-size: 11px; text-transform: uppercase; font-weight: bold; letter-spacing: 0.8px; margin-bottom: 2px; }}
    .spec-value {{ color: {SIA_NAVY}; font-size: 17px; font-weight: 700; margin-bottom: 15px; font-family: 'Segoe UI', sans-serif; }}
    .time-box {{ background: #ffffff; padding: 12px; border-radius: 6px; border: 1px solid #d1d5db; border-left: 5px solid {SIA_GOLD}; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); }}
    .status-pill {{ background: {SIA_NAVY}; color: white; padding: 4px 12px; border-radius: 20px; font-size: 13px; font-weight: 600; }}
    .section-header {{ border-bottom: 2px solid #eee; padding-bottom: 5px; margin-bottom: 15px; color: #444; font-weight: 800; font-size: 14px; text-transform: uppercase; }}
</style>""", unsafe_allow_html=True)

# --- 2. DATA FUSION ENGINE ---

def fetch_unified_data(f_num, date_str):
    unified = {"source": "NONE", "legs": [], "status": "Unknown"}
    iata = f"SQ{f_num}".upper()
    
    # Priority: AirLabs (Most consistent for Gates/Actuals) -> SIA (Metadata) -> ADS-B
    try:
        url = f"https://airlabs.co/api/v9/flight?api_key={st.secrets['AIRLABS_API_KEY']}&flight_iata={iata}"
        al = requests.get(url, timeout=5).json().get("response")
        if al:
            unified["source"] = "AIRLABS OPERATIONS"
            unified["status"] = al.get("status", "Unknown").upper()
            unified["legs"] = [{
                "fn": iata,
                "ac_type": al.get("aircraft_icao", "N/A"),
                "dep_iata": al.get("dep_iata"),
                "arr_iata": al.get("arr_iata"),
                "dep_term": al.get("dep_terminal") or "TBA",
                "arr_term": al.get("arr_terminal") or "TBA",
                "dep_gate": al.get("dep_gate") or "TBA",
                "arr_gate": al.get("arr_gate") or "TBA",
                "times": {
                    "sch_dep": al.get("dep_time"),
                    "act_dep": al.get("dep_actual"),
                    "sch_arr": al.get("arr_time"),
                    "act_arr": al.get("arr_actual"),
                    "est_arr": al.get("arr_estimated")
                }
            }]
            return unified
    except: pass
    return unified

# --- 3. UI RENDERER (Every Detail Requested) ---

def render_manifest(data):
    for leg in data["legs"]:
        st.markdown(f"### <span class='status-pill'>{data['status']}</span>", unsafe_allow_html=True)
        
        # --- SECTION 1: FLIGHT & AIRCRAFT ---
        st.markdown("<div class='section-header'>Flight & Aircraft Information</div>", unsafe_allow_html=True)
        r1_c1, r1_c2, r1_c3, r1_c4 = st.columns(4)
        with r1_c1:
            st.markdown(f"<div class='spec-label'>Flight Number</div><div class='spec-value'>{leg['fn']}</div>", unsafe_allow_html=True)
        with r1_c2:
            st.markdown(f"<div class='spec-label'>Aircraft Type</div><div class='spec-value'>{leg['ac_type']}</div>", unsafe_allow_html=True)
        with r1_c3:
            st.markdown(f"<div class='spec-label'>Departure Airport</div><div class='spec-value'>{leg['dep_iata']}</div>", unsafe_allow_html=True)
        with r1_c4:
            st.markdown(f"<div class='spec-label'>Arrival Airport</div><div class='spec-value'>{leg['arr_iata']}</div>", unsafe_allow_html=True)

        # --- SECTION 2: TERMINALS & GATES ---
        st.markdown("<div class='section-header'>Terminal & Gate Assignments</div>", unsafe_allow_html=True)
        r2_c1, r2_c2, r2_c3, r2_c4 = st.columns(4)
        with r2_c1:
            st.markdown(f"<div class='spec-label'>Departure Terminal</div><div class='spec-value'>Terminal {leg['dep_term']}</div>", unsafe_allow_html=True)
        with r2_c2:
            st.markdown(f"<div class='spec-label'>Arrival Terminal</div><div class='spec-value'>Terminal {leg['arr_term']}</div>", unsafe_allow_html=True)
        with r2_c3:
            st.markdown(f"<div class='spec-label'>Departure Gate</div><div class='spec-value'>{leg['dep_gate']}</div>", unsafe_allow_html=True)
        with r2_c4:
            st.markdown(f"<div class='spec-label'>Arrival Gate</div><div class='spec-value'>{leg['arr_gate']}</div>", unsafe_allow_html=True)

        # --- SECTION 3: DEPARTURE TIMES ---
        st.markdown("<div class='section-header'>Departure Schedule</div>", unsafe_allow_html=True)
        d1, d2 = st.columns(2)
        with d1:
            st.markdown("<div class='spec-label'>Scheduled Departure</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='time-box'>{leg['times']['sch_dep']}</div>", unsafe_allow_html=True)
        with d2:
            is_dep = data['status'] in ['DEPARTED', 'EN-ROUTE', 'LANDED', 'ARRIVED']
            val = leg['times']['act_dep'] if (is_dep and leg['times']['act_dep']) else "---"
            st.markdown("<div class='spec-label'>Actual Departure</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='time-box'>{val}</div>", unsafe_allow_html=True)

        # --- SECTION 4: ARRIVAL TIMES ---
        st.markdown("<div class='section-header'>Arrival Schedule</div>", unsafe_allow_html=True)
        a1, a2, a3 = st.columns(3)
        with a1:
            st.markdown("<div class='spec-label'>Scheduled Arrival</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='time-box'>{leg['times']['sch_arr']}</div>", unsafe_allow_html=True)
        with a2:
            is_enroute = data['status'] == 'EN-ROUTE'
            val = leg['times']['est_arr'] if (is_enroute and leg['times']['est_arr']) else "---"
            st.markdown("<div class='spec-label'>Estimated Arrival</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='time-box'>{val}</div>", unsafe_allow_html=True)
        with a3:
            is_arr = data['status'] in ['LANDED', 'ARRIVED']
            val = leg['times']['act_arr'] if (is_arr and leg['times']['act_arr']) else "---"
            st.markdown("<div class='spec-label'>Actual Arrival</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='time-box'>{val}</div>", unsafe_allow_html=True)

# --- 4. RADAR & NAVIGATION ---

def show_radar():
    st.subheader("🌐 Global SIA Fleet View")
    try:
        url = f"https://airlabs.co/api/v9/flights?airline_iata=SQ&api_key={st.secrets['AIRLABS_API_KEY']}"
        planes = requests.get(url).json().get("response", [])
        m = folium.Map(location=[1.35, 103.8], zoom_start=2, tiles="CartoDB dark_matter")
        for p in planes:
            if p.get('lat'):
                folium.Marker([p['lat'], p['lng']], 
                              popup=f"SQ{p.get('flight_number')} to {p.get('arr_iata')}",
                              icon=folium.Icon(color="blue", icon="plane")).add_to(m)
        st_folium(m, width="100%", height=500)
    except: st.error("Radar currently unavailable.")

# --- APP FLOW ---
st.sidebar.title("🛠️ KrisTracker Pro")
menu = st.sidebar.radio("Navigate", ["Flight Search", "Fleet Radar", "Wayfinding PDF"])

if menu == "Flight Search":
    c1, c2 = st.columns(2)
    f_num = c1.text_input("SQ Number", "11")
    f_date = c2.date_input("Date")
    if st.button("EXECUTE SEARCH"):
        data = fetch_unified_data(f_num, str(f_date))
        if data["source"] != "NONE":
            render_manifest(data)
        else: st.error("Flight not found in live operations database.")

elif menu == "Fleet Radar":
    show_radar()

elif menu == "Wayfinding PDF":
    try:
        with open("Singapore-Changi-Airport-Transit-Area-Wayfinding.pdf", "rb") as f:
            base64_pdf = base64.b64encode(f.read()).decode('utf-8')
        st.markdown(f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800"></iframe>', unsafe_allow_html=True)
    except: st.error("PDF Wayfinding file missing from root.")
