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
.section-header {{ border-bottom: 2px solid #eee; font-weight: 800; }}
.fr-callsign {{ color: {FR_YELLOW}; font-size: 26px; font-weight: 900; }}
</style>""", unsafe_allow_html=True)

# --- 2. HELPERS ---
def get_b64(path):
    if os.path.exists(path):
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return ""

def get_ac_image(ac_code):
    mapping = {
        "A359": "9V-SMI.jpg",
        "A388": "9V-SKY.jpg",
        "B38M": "9V-MBO.jpg",
        "77W": "9V-SWR.jpg",
    }
    return mapping.get(str(ac_code).upper())

def fmt_t(t):
    return t[-5:] if t else "---"

# --- 3. AIRLABS ONLY DATA ---
@st.cache_data(ttl=120)
def fetch_airlabs(flight_iata=None):
    try:
        url = f"https://airlabs.co/api/v9/flights?airline_iata=SQ&api_key={st.secrets['AIRLABS_API_KEY']}"
        return requests.get(url, timeout=10).json().get("response", [])
    except:
        return []

# --- 4. SEARCH ---
def search_flight(flight_num):
    try:
        iata = f"SQ{flight_num}"
        url = f"https://airlabs.co/api/v9/flight?api_key={st.secrets['AIRLABS_API_KEY']}&flight_iata={iata}"
        return requests.get(url, timeout=10).json().get("response")
    except:
        return None

# --- 5. SEARCH UI ---
def render_search():
    st.title("🔍 Flight Search")
    fnum = st.text_input("Flight Number (SQ)", "11")

    if st.button("Search"):
        data = search_flight(fnum)
        if not data:
            st.error("No data found")
            return

        st.subheader(f"{data.get('flight_iata')}")

        col1, col2 = st.columns(2)
        col1.write("Departure: " + str(data.get("dep_iata")))
        col2.write("Arrival: " + str(data.get("arr_iata")))

# --- 6. RADAR ---
def render_radar():
    if "radar_data" not in st.session_state:
        st.session_state.radar_data = fetch_airlabs()

    if st.button("🔄 Refresh"):
        st.session_state.radar_data = fetch_airlabs()

    col_info, col_map = st.columns([1.5, 2.5])

    # --- MAP (UNCHANGED) ---
    m = folium.Map(
        location=[1.35, 103.8],
        zoom_start=4,
        tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
        attr='Google'
    )

    icon_b64 = get_b64("icon.png")

    for p in st.session_state.radar_data:
        if not p.get("lat") or not p.get("lng"):
            continue

        html = f"""
        <div style="transform: rotate({p.get('dir',0)}deg);">
            <img src="data:image/png;base64,{icon_b64}" width="25"/>
        </div>
        """

        folium.Marker(
            [p["lat"], p["lng"]],
            tooltip=p.get("flight_iata"),
            icon=folium.DivIcon(html=html)
        ).add_to(m)

    with col_map:
        res = st_folium(m, width="100%", height=700)

    with col_info:
        if res.get("last_object_clicked_tooltip"):
            flight = next((x for x in st.session_state.radar_data if x.get("flight_iata") == res["last_object_clicked_tooltip"]), None)

            if flight:
                st.markdown(f"### {flight.get('flight_iata')}")
                st.write("Aircraft:", flight.get("aircraft_icao"))
                st.write("Speed:", flight.get("speed"))
                st.write("Altitude:", flight.get("alt"))

                img = get_ac_image(flight.get("aircraft_icao"))
                if img and os.path.exists(img):
                    st.image(img)

# --- 7. WAYFINDING ---
def render_wayfinding():
    st.title("🗺️ Wayfinding")
    pdf = get_b64("wayfinding.pdf")

    if pdf:
        st.markdown(f'<iframe src="data:application/pdf;base64,{pdf}" width="100%" height="900"></iframe>', unsafe_allow_html=True)
    else:
        st.warning("No PDF found")

# --- 8. NAV ---
menu = st.sidebar.radio("MODE", ["📡 Radar", "🔍 Search", "🗺️ Wayfinding"])

if menu == "📡 Radar":
    render_radar()
elif menu == "🔍 Search":
    render_search()
elif menu == "🗺️ Wayfinding":
    render_wayfinding()
