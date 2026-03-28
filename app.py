import streamlit as st
import requests, uuid, math, folium, base64, json, os, time
from streamlit_folium import st_folium
from datetime import datetime, timezone

# --- CONFIG ---
st.set_page_config(page_title="KrisTracker Pro v2.0", page_icon="✈️", layout="wide")

SIA_NAVY, SIA_GOLD, FR_YELLOW = "#00266B", "#BD9B60", "#ffc107"

# --- STYLES (UNCHANGED) ---
st.markdown(f"""
<style>
[data-testid="stSidebar"] {{ min-width: 210px !important; max-width: 210px !important; }}
.spec-label {{ color: #666; font-size: 11px; font-weight: bold; }}
.spec-value {{ color: {SIA_NAVY}; font-size: 17px; font-weight: 700; }}
.status-pill {{ background: {SIA_NAVY}; color: white; padding: 4px 12px; border-radius: 20px; }}
.timer-text {{ font-size: 12px; color: {SIA_NAVY}; font-weight: bold; }}
</style>
""", unsafe_allow_html=True)

# --- HELPERS ---

def get_b64(path):
    if os.path.exists(path):
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return ""

def fmt_t(t):
    return t[-5:] if t else "---"

# --- AIRLABS RADAR DATA ---

@st.cache_data(ttl=300)
def fetch_airlabs():
    try:
        url = f"https://airlabs.co/api/v9/flights?airline_iata=SQ&api_key={st.secrets['AIRLABS_API_KEY']}"
        data = requests.get(url, timeout=10).json()
        return data.get("response", [])
    except:
        return []

# --- FULL SIA SEARCH (RESTORED) ---

@st.cache_data(ttl=300)
def fetch_search_data(f_num, date_str):
    try:
        url = "https://apigw.singaporeair.com/api/uat/v2/flightstatus/getbynumber"

        headers = {
            "api_key": st.secrets["SIA_STATUS_KEY"],
            "x-csl-client-id": "SPD",
            "x-csl-client-uuid": str(uuid.uuid4())
        }

        res = requests.post(
            url,
            json={
                "airlineCode": "SQ",
                "flightNumber": f_num,
                "scheduledDepartureDate": date_str
            },
            headers=headers,
            timeout=5
        ).json()

        flight = res.get("data", {}).get("response", {}).get("flights", [None])[0]

        if not flight:
            return None

        leg = flight["legs"][-1]

        return {
            "fn": f"SQ{f_num}",
            "ac": leg.get("aircraftTypeCode"),
            "dep": leg.get("origin", {}).get("airportCode"),
            "arr": leg.get("destination", {}).get("airportCode"),
            "status": leg.get("flightStatus"),
            "times": {
                "sch_dep": leg.get("scheduledDepartureTime"),
                "sch_arr": leg.get("scheduledArrivalTime"),
                "act_dep": leg.get("actualDepartureTime"),
                "act_arr": leg.get("actualArrivalTime"),
                "est_arr": leg.get("estimatedArrivalTime")
            }
        }

    except:
        return None

# --- UI: SEARCH MANIFEST (RESTORED) ---

def render_manifest(d):
    st.markdown(f"### {d['fn']}")

    st.markdown(f"<span class='status-pill'>{d['status']}</span>", unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.write(f"**Flight**: {d['fn']}")
    c2.write(f"**Aircraft**: {d['ac']}")
    c3.write(f"**From**: {d['dep']}")
    c4.write(f"**To**: {d['arr']}")

    st.markdown("#### Schedule")
    s1, s2, s3 = st.columns(3)

    s1.write(f"Sched Dep: {fmt_t(d['times']['sch_dep'])}")
    s2.write(f"Sched Arr: {fmt_t(d['times']['sch_arr'])}")
    s3.write(f"Est Arr: {fmt_t(d['times']['est_arr'])}")

    st.markdown("#### Actuals")
    a1, a2 = st.columns(2)

    a1.write(f"Actual Dep: {fmt_t(d['times']['act_dep'])}")
    a2.write(f"Actual Arr: {fmt_t(d['times']['act_arr'])}")

# --- RADAR (FIXED) ---

def radar():

    if "data" not in st.session_state:
        st.session_state.data = []
    if "selected" not in st.session_state:
        st.session_state.selected = None
    if "map_center" not in st.session_state:
        st.session_state.map_center = [1.35, 103.8]
    if "map_zoom" not in st.session_state:
        st.session_state.map_zoom = 4
    if "last_fetch" not in st.session_state:
        st.session_state.last_fetch = 0

    # --- FETCH ---
    if time.time() - st.session_state.last_fetch > 300:
        st.session_state.data = fetch_airlabs()
        st.session_state.last_fetch = time.time()

    col_map, col_info = st.columns([2.5, 1.5])

    # --- MAP ---
    m = folium.Map(
        location=st.session_state.map_center,
        zoom_start=st.session_state.map_zoom,
        tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
        attr='Google'
    )

    # --- FIXED MARKERS ---
    for p in st.session_state.data:
        lat = p.get("lat")
        lon = p.get("lng")

        if lat is None or lon is None:
            continue

        folium.Marker(
            [lat, lon],
            tooltip=p.get("flight_iata", "SQ"),
            popup=f"{p.get('flight_iata')}<br>{p.get('dep_iata')} → {p.get('arr_iata')}"
        ).add_to(m)

    with col_map:
        res = st_folium(m, width=None, height=800)

    clicked = res.get("last_object_clicked_tooltip")

    if clicked:
        st.session_state.selected = clicked

        plane = next((x for x in st.session_state.data if x.get("flight_iata") == clicked), None)

        if plane and plane.get("lat") and plane.get("lng"):
            st.session_state.map_center = [plane["lat"], plane["lng"]]
            st.session_state.map_zoom = 7
            st.rerun()

    with col_info:
        if st.session_state.selected:
            st.write("### Flight Info")

            data = next((x for x in st.session_state.data if x.get("flight_iata") == st.session_state.selected), None)

            if data:
                st.write(data)
        else:
            st.info("Click a plane to view details")

            for p in st.session_state.data[:15]:
                st.write(f"{p.get('flight_iata')} | {p.get('dep_iata')} → {p.get('arr_iata')}")

# --- NAV ---

menu = st.sidebar.radio("MODE", ["📡 Radar", "🔍 Search", "🗺️ Wayfinding"])

if menu == "📡 Radar":
    radar()

elif menu == "🔍 Search":

    st.title("Flight Search")

    col1, col2 = st.columns(2)

    f_num = col1.text_input("Flight Number", "11")
    f_date = col2.date_input("Date")

    if st.button("Search Flight"):

        data = fetch_search_data(f_num, str(f_date))

        if data:
            render_manifest(data)
        else:
            st.error("No flight found")

elif menu == "🗺️ Wayfinding":

    st.title("Wayfinding")

    pdf = get_b64("wayfinding.pdf")

    if pdf:
        st.markdown(f'<iframe src="data:application/pdf;base64,{pdf}" width="100%" height="900"></iframe>', unsafe_allow_html=True)
    else:
        st.warning("PDF not found")
