import streamlit as st
import requests, uuid, math, folium, base64
from streamlit_folium import st_folium
from datetime import datetime

# --- 1. SETTINGS ---
st.set_page_config(page_title="KrisTracker Pro", page_icon="✈️", layout="wide")
SIA_NAVY = "#00266B"

st.markdown(f"""<style>
    .reportview-container .main .block-container {{ padding-top: 2rem; }}
    .spec-label {{ color: #666; font-size: 11px; text-transform: uppercase; font-weight: bold; letter-spacing: 0.5px; }}
    .spec-value {{ color: {SIA_NAVY}; font-size: 15px; font-weight: 600; margin-bottom: 12px; }}
    .time-box {{ background: #f8f9fb; padding: 12px; border-radius: 6px; border: 1px solid #e0e4e9; border-left: 4px solid {SIA_NAVY}; }}
    .status-tag {{ background: {SIA_NAVY}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; }}
</style>""", unsafe_allow_html=True)

# --- 2. DATA FUSION ENGINE ---

def fetch_unified_data(f_num, date_str):
    unified = {"source": "NONE", "legs": [], "status": "Unknown"}
    iata = f"SQ{f_num}".upper()

    # Priority 1: AirLabs (Best for live operational times & gates)
    try:
        url = f"https://airlabs.co/api/v9/flight?api_key={st.secrets['AIRLABS_API_KEY']}&flight_iata={iata}"
        al_res = requests.get(url, timeout=5).json()
        al = al_res.get("response")
        if al:
            unified["source"] = "LIVE AIRLABS"
            unified["status"] = al.get("status", "Unknown").upper()
            unified["legs"] = [{
                "flightNumber": iata,
                "aircraftTypeCode": al.get("aircraft_icao", "N/A"),
                "origin": {
                    "airportCode": al.get("dep_iata"), 
                    "terminal": al.get("dep_terminal", "TBA"),
                    "gate": al.get("dep_gate", "TBA")
                },
                "destination": {
                    "airportCode": al.get("arr_iata"), 
                    "terminal": al.get("arr_terminal", "TBA"),
                    "gate": al.get("arr_gate", "TBA")
                },
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

# --- 3. UI RENDERER ---

def render_specs(data):
    for leg in data["legs"]:
        st.markdown(f"### ✈️ Flight Details: {leg['flightNumber']} <span class='status-tag'>{data['status']}</span>", unsafe_allow_html=True)
        
        # Row 1: Terminals & Aircraft
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f"<div class='spec-label'>Aircraft Type</div><div class='spec-value'>{leg['aircraftTypeCode']}</div>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<div class='spec-label'>Departure Terminal</div><div class='spec-value'>{leg['origin']['terminal']}</div>", unsafe_allow_html=True)
        with c3:
            st.markdown(f"<div class='spec-label'>Arrival Terminal</div><div class='spec-value'>{leg['destination']['terminal']}</div>", unsafe_allow_html=True)
        with c4:
            st.markdown(f"<div class='spec-label'>Gate Status</div><div class='spec-value'>Dep: {leg['origin']['gate']} / Arr: {leg['destination']['gate']}</div>", unsafe_allow_html=True)

        # Row 2: Departure Times
        st.markdown("---")
        d1, d2 = st.columns(2)
        with d1:
            st.markdown("<div class='spec-label'>Scheduled Departure</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='time-box'>{leg['times']['sch_dep']}</div>", unsafe_allow_html=True)
        with d2:
            # Only show Actual if flight has departed/arrived
            is_departed = data['status'] in ['DEPARTED', 'EN-ROUTE', 'LANDED', 'ARRIVED']
            val = leg['times']['act_dep'] if (is_departed and leg['times']['act_dep']) else "---"
            st.markdown("<div class='spec-label'>Actual Departure</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='time-box'>{val}</div>", unsafe_allow_html=True)

        # Row 3: Arrival Times
        st.markdown("<br>", unsafe_allow_html=True)
        a1, a2, a3 = st.columns(3)
        with a1:
            st.markdown("<div class='spec-label'>Scheduled Arrival</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='time-box'>{leg['times']['sch_arr']}</div>", unsafe_allow_html=True)
        with a2:
            # Show Estimated only if en-route
            is_enroute = data['status'] == 'EN-ROUTE'
            val = leg['times']['est_arr'] if (is_enroute and leg['times']['est_arr']) else "---"
            st.markdown("<div class='spec-label'>Estimated Arrival</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='time-box'>{val}</div>", unsafe_allow_html=True)
        with a3:
            # Show Actual only if arrived
            is_arrived = data['status'] in ['LANDED', 'ARRIVED']
            val = leg['times']['act_arr'] if (is_arrived and leg['times']['act_arr']) else "---"
            st.markdown("<div class='spec-label'>Actual Arrival</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='time-box'>{val}</div>", unsafe_allow_html=True)

# --- 4. FLEET RADAR ---

def show_fleet_radar():
    st.header("🌐 SIA Global Fleet Radar")
    try:
        # Fetching entire SQ fleet from AirLabs to ensure planes appear
        fleet_url = f"https://airlabs.co/api/v9/flights?airline_iata=SQ&api_key={st.secrets['AIRLABS_API_KEY']}"
        res = requests.get(fleet_url).json()
        planes = res.get("response", [])
        
        m = folium.Map(location=[1.3521, 103.8198], zoom_start=3, tiles="CartoDB dark_matter")
        
        for p in planes:
            folium.Marker(
                location=[p['lat'], p['lng']],
                popup=f"Flight: {p['flight_iata']}<br>Alt: {p['alt']}ft<br>To: {p['arr_iata']}",
                icon=folium.Icon(color="blue", icon="plane")
            ).add_to(m)
        
        st_folium(m, width=1200, height=500)
        st.info(f"Tracking {len(planes)} active Singapore Airlines aircraft globally.")
    except Exception as e:
        st.error(f"Radar Error: {e}")

# --- 5. MAIN LOGIC ---

mode = st.sidebar.radio("Navigation", ["Flight Search", "SIA Fleet Radar"])

if mode == "Flight Search":
    sc1, sc2 = st.columns(2)
    f_num = sc1.text_input("SQ Flight Number", "11")
    f_date = sc2.date_input("Date")
    
    if st.button("GET OPERATIONAL DETAILS"):
        data = fetch_unified_data(f_num, str(f_date))
        if data["source"] != "NONE":
            render_specs(data)
        else:
            st.error("No live data found for this flight number today.")

elif mode == "SIA Fleet Radar":
    show_fleet_radar()
