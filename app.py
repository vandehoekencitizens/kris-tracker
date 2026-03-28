import streamlit as st
import requests, uuid, math, folium, base64, json, os, time
from streamlit_folium import st_folium
from datetime import datetime, timezone

# --- 1. CORE STYLING & ASSETS ---
st.set_page_config(page_title="KrisTracker Pro v2.0", page_icon="✈️", layout="wide")
SIA_NAVY, SIA_GOLD, FR_YELLOW = "#00266B", "#BD9B60", "#ffc107"

st.markdown(f"""<style>
    [data-testid="stSidebar"] {{ min-width: 210px !important; max-width: 210px !important; }}
    .spec-label {{ color: #666; font-size: 11px; text-transform: uppercase; font-weight: bold; }}
    .spec-value {{ color: {SIA_NAVY}; font-size: 17px; font-weight: 700; }}
    .status-pill {{ background: {SIA_NAVY}; color: white; padding: 4px 12px; border-radius: 20px; }}
</style>""", unsafe_allow_html=True)

# --- 2. HELPERS ---

def get_b64(file_path):
    try:
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                return base64.b64encode(f.read()).decode('utf-8')
    except:
        pass
    return ""

def fmt_t(dt_str):
    try:
        return dt_str[11:16]
    except:
        return "---"

def calc_eta_str(est_iso):
    try:
        if not est_iso:
            return ""
        est = datetime.fromisoformat(est_iso.replace("Z", "+00:00"))
        delta = (est - datetime.now(timezone.utc)).total_seconds()
        if delta > 0:
            h, rem = divmod(int(delta), 3600)
            m, _ = divmod(rem, 60)
            return f" (In {h}h {m}m)"
        return " (Arriving)"
    except:
        return ""

# --- 3. AIRLABS DATA ENGINE ---

@st.cache_data(ttl=120, show_spinner=False)
def fetch_radar_data():
    try:
        url = f"https://airlabs.co/api/v9/flights?airline_iata=SQ&api_key={st.secrets['AIRLABS_API_KEY']}"
        res = requests.get(url, timeout=10).json()
        return res.get("response", [])
    except:
        return []

@st.cache_data(ttl=300, show_spinner=False)
def fetch_flight(flight_iata):
    try:
        url = f"https://airlabs.co/api/v9/flight?api_key={st.secrets['AIRLABS_API_KEY']}&flight_iata={flight_iata}"
        res = requests.get(url, timeout=10).json()
        return res.get("response")
    except:
        return None

# --- 4. UI ---

def render_fr24_card(flight_iata, data):
    st.markdown(f"### ✈ {flight_iata}")

    if not data:
        st.warning("No data available")
        return

    st.markdown(f"**Status:** {data.get('status','---')}")
    st.markdown(f"**Aircraft:** {data.get('aircraft_icao','---')}")
    st.markdown(f"**From:** {data.get('dep_iata','---')} → **To:** {data.get('arr_iata','---')}")

    st.markdown("---")

    st.markdown(f"""
    **Scheduled Departure:** {fmt_t(data.get('dep_time'))}  
    **Scheduled Arrival:** {fmt_t(data.get('arr_time'))}  
    """)

    if data.get("arr_estimated"):
        st.markdown(f"**ETA:** {fmt_t(data.get('arr_estimated'))}{calc_eta_str(data.get('arr_estimated'))}")

# --- 5. RADAR ---

def show_interactive_radar():
    if "map_center" not in st.session_state:
        st.session_state.map_center = [1.35, 103.8]
    if "map_zoom" not in st.session_state:
        st.session_state.map_zoom = 4
    if "selected_flight" not in st.session_state:
        st.session_state.selected_flight = None
    if "radar_data" not in st.session_state:
        st.session_state.radar_data = []

    # Refresh logic
    if st.button("🔄 Refresh Radar"):
        st.session_state.radar_data = fetch_radar_data()

    # Fetch if empty
    if not st.session_state.radar_data:
        st.session_state.radar_data = fetch_radar_data()

    col_map, col_info = st.columns([2.5, 1.5])

    # MAP
    m = folium.Map(location=st.session_state.map_center, zoom_start=st.session_state.map_zoom, tiles="cartodbpositron")

    for p in st.session_state.radar_data:
        if p.get("lat") and p.get("lng"):
            folium.Marker(
                [p["lat"], p["lng"]],
                tooltip=p.get("flight_iata"),
            ).add_to(m)

    with col_map:
        res = st_folium(m, width="100%", height=800, returned_objects=["last_object_clicked_tooltip"])

    clicked = res.get("last_object_clicked_tooltip")

    if clicked and clicked != st.session_state.selected_flight:
        st.session_state.selected_flight = clicked
        st.rerun()

    # INFO PANEL
    with col_info:
        if st.session_state.selected_flight:
            data = fetch_flight(st.session_state.selected_flight)
            render_fr24_card(st.session_state.selected_flight, data)
        else:
            st.info("Click a plane on the map")

# --- 6. SEARCH (AirLabs ONLY) ---

def search_flight():
    st.title("🔍 Flight Search")

    flight = st.text_input("Flight IATA (e.g. SQ11)")

    if st.button("Search") and flight:
        data = fetch_flight(flight.upper())
        if data:
            render_fr24_card(flight.upper(), data)
        else:
            st.error("Flight not found")

# --- 7. WAYFINDING ---

def wayfinding():
    st.title("🗺️ Wayfinding")

    pdf_b64 = get_b64("Singapore-Changi-Airport-Transit-Area-Wayfinding.pdf")

    if pdf_b64:
        st.markdown(f"""
        <iframe src="data:application/pdf;base64,{pdf_b64}" 
        width="100%" height="900" style="border:none;"></iframe>
        """, unsafe_allow_html=True)
    else:
        st.warning("PDF not found")

# --- 8. NAV ---

menu = st.sidebar.radio("Mode", ["📡 Radar", "🔍 Search", "🗺️ Wayfinding"])

if menu == "📡 Radar":
    show_interactive_radar()

elif menu == "🔍 Search":
    search_flight()

elif menu == "🗺️ Wayfinding":
    wayfinding()

st.sidebar.markdown("---")
st.sidebar.markdown("**KrisTracker Pro** v2 (AirLabs Only)")
