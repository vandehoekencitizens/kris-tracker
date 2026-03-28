import streamlit as st
import requests
import folium
import base64
import os
import time
from datetime import datetime, timezone
from streamlit_folium import st_folium

# =====================
# CONFIG
# =====================

st.set_page_config(page_title="InflightTracker", layout="wide")

# 👉 USE YOUR KEY HERE
AIRLABS_KEY = "PUT_YOUR_KEY_HERE"

# =====================
# STYLES
# =====================

st.markdown("""
<style>
[data-testid="stSidebar"] {
    min-width: 220px;
    max-width: 220px;
}

.card {
    padding: 10px;
    border-radius: 10px;
    background: #f5f5f5;
    margin-bottom: 10px;
}

</style>
""", unsafe_allow_html=True)

# =====================
# HELPERS
# =====================

def safe(x):
    return x if x is not None else ""

def get_img_b64(path):
    if os.path.exists(path):
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return None


def format_time(t):
    try:
        return t[-5:]
    except:
        return "---"


def eta(arr):
    try:
        if not arr:
            return ""
        dt = datetime.fromisoformat(arr.replace("Z", "+00:00"))
        delta = (dt - datetime.now(timezone.utc)).total_seconds()
        if delta > 0:
            return f" (+{int(delta//60)} min)"
        return " (Arrived)"
    except:
        return ""


# =====================
# API (AIRLABS)
# =====================

@st.cache_data(ttl=120)
def get_flights():
    url = f"https://airlabs.co/api/v9/flights?api_key={AIRLABS_KEY}"
    r = requests.get(url)
    return r.json().get("response", [])


@st.cache_data(ttl=120)
def get_flight(code):
    url = f"https://airlabs.co/api/v9/flight?api_key={AIRLABS_KEY}&flight_iata={code}"
    r = requests.get(url)
    return r.json().get("response", {})


# =====================
# AIRCRAFT IMAGE
# =====================

def aircraft_img(code):
    mapping = {
        "A359": "A359.png",
        "A388": "A388.png",
        "B38M": "B38M.png",
        "B77W": "B77W.png",
    }
    return mapping.get(str(code).upper())


# =====================
# FLIGHT CARD
# =====================

def render_card(f):
    st.markdown("### ✈️ Flight")

    col1, col2 = st.columns(2)

    with col1:
        st.write("DEP:", safe(f.get("dep_iata")))
        st.write(format_time(f.get("dep_time")))

    with col2:
        st.write("ARR:", safe(f.get("arr_iata")))
        st.write(format_time(f.get("arr_time")) + eta(f.get("arr_estimated")))

    st.write("---")
    st.write("Aircraft:", f.get("aircraft_icao"))
    st.write("Status:", f.get("status"))

    img = aircraft_img(f.get("aircraft_icao"))
    if img and os.path.exists(img):
        st.image(img, use_container_width=True)


# =====================
# RADAR
# =====================

def radar():
    if "flights" not in st.session_state:
        st.session_state.flights = []

    if time.time() - st.session_state.get("last", 0) > 120:
        try:
            st.session_state.flights = get_flights()
            st.session_state.last = time.time()
        except:
            pass

    m = folium.Map(
        location=[1.35, 103.8],
        zoom_start=5,
        tiles="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}"
    )

    icon = get_img_b64("plane.png")

    for f in st.session_state.flights:
        if f.get("lat") and f.get("lng"):
            html = f"""
            <div style="transform:rotate({f.get('dir',0)}deg)">
                <img src="data:image/png;base64,{icon}" width="25">
            </div>
            """

            folium.Marker(
                [f["lat"], f["lng"]],
                tooltip=f.get("flight_iata"),
                icon=folium.DivIcon(html=html)
            ).add_to(m)

    col1, col2 = st.columns([3,1])

    with col2:
        clicked = st_folium(m, height=700)

    sel = None

    if clicked.get("last_object_clicked_tooltip"):
        code = clicked["last_object_clicked_tooltip"]
        sel = next((x for x in st.session_state.flights if x.get("flight_iata") == code), None)

    with col1:
        if sel:
            render_card(sel)
        else:
            st.info("Click aircraft")


# =====================
# SEARCH
# =====================

def search():
    st.title("🔍 Search")

    code = st.text_input("Flight (e.g SQ11)").upper()

    if st.button("Search"):
        f = get_flight(code)

        if not f:
            st.error("Not found")
            return

        render_card(f)


# =====================
# WAYFINDING
# =====================

def wayfinding():
    st.title("🗺️ Wayfinding")

    file = "wayfinding.pdf"

    if os.path.exists(file):
        with open(file, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()

        st.markdown(f"""
        <iframe src="data:application/pdf;base64,{b64}" width="100%" height="900"></iframe>
        """, unsafe_allow_html=True)
    else:
        st.warning("PDF missing")


# =====================
# MAIN
# =====================

mode = st.sidebar.radio("Mode", ["Radar", "Search", "Wayfinding"])

if mode == "Radar":
    radar()
elif mode == "Search":
    search()
else:
    wayfinding()
