import streamlit as st
import requests
import hashlib
import time
import uuid
import folium
from streamlit_folium import st_folium
from supabase import create_client

# --- 1. SETTINGS & BRANDING ---
st.set_page_config(page_title="KrisTracker", page_icon="✈️", layout="wide")

SIA_NAVY = "#00266B"
SIA_GOLD = "#BD9B60"

# Inject Custom UI
st.markdown(f"""
    <style>
    .stApp {{ background-color: {SIA_NAVY}; color: white; }}
    [data-testid="stSidebar"] {{ background-color: #001a33; border-right: 1px solid {SIA_GOLD}; }}
    .flight-card {{
        background: rgba(255, 255, 255, 0.05);
        padding: 20px;
        border-radius: 15px;
        border-left: 5px solid {SIA_GOLD};
        margin-bottom: 20px;
    }}
    .stButton>button {{ background-color: {SIA_GOLD} !important; color: {SIA_NAVY} !important; font-weight: bold; width: 100%; }}
    .stTabs [data-baseweb="tab-list"] {{ gap: 20px; }}
    .stTabs [data-baseweb="tab"] {{ color: white; }}
    </style>
    """, unsafe_allow_html=True)

# --- 2. INITIALIZE CLIENTS ---
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- 3. LOGIC FUNCTIONS ---
def get_sia_headers():
    key = st.secrets["SIA_STATUS_KEY"]
    secret = st.secrets.get("SIA_STATUS_SECRET", "")
    timestamp = str(int(time.time()))
    signature = hashlib.sha256((key + secret + timestamp).encode()).hexdigest()
    return {
        "api-key": key, "x-signature": signature, "timestamp": timestamp,
        "x-csl-client-uuid": str(uuid.uuid4()), "Content-Type": "application/json"
    }

def get_live_sq_fleet():
    """Fetches real-time GPS for all SIA planes via OpenSky API."""
    url = "https://opensky-network.org/api/states/all"
    auth = (st.secrets["OPENSKY_CLIENT_ID"], st.secrets["OPENSKY_CLIENT_SECRET"])
    try:
        r = requests.get(url, auth=auth, timeout=10)
        states = r.json().get("states", [])
        # Filter: ICAO callsign 'SIA' = Singapore Airlines
        return [s for s in states if s[1] and s[1].strip().startswith("SIA")]
    except: return []

# --- 4. SIDEBAR AUTH ---
st.sidebar.image("https://upload.wikimedia.org/wikipedia/en/6/6b/Singapore_Airlines_Logo_2.svg", width=180)
if "user" not in st.session_state:
    mode = st.sidebar.radio("Member Access", ["Login", "Sign Up"])
    email = st.sidebar.text_input("Email")
    pw = st.sidebar.text_input("Password", type="password")
    if st.sidebar.button("Enter Portal"):
        try:
            if mode == "Login":
                res = supabase.auth.sign_in_with_password({"email": email, "password": pw})
            else:
                res = supabase.auth.sign_up({"email": email, "password": pw})
            st.session_state["user"] = res.user
            st.rerun()
        except: st.sidebar.error("Auth Failed")
    st.stop()
else:
    st.sidebar.write(f"Logged in: **{st.session_state['user'].email}**")
    if st.sidebar.button("Log Out"):
        del st.session_state["user"]
        st.rerun()

# --- 5. MAIN INTERFACE ---
st.title("🇸🇬 KrisTracker Dashboard")

tab1, tab2 = st.tabs(["🔎 Flight Status", "📡 Live Open Street Map"])

with tab1:
    col1, col2 = st.columns([1, 2])
    with col1:
        flight_no = st.text_input("Flight Number (e.g. SQ638)", "SQ638").upper()
        flight_digits = ''.join(filter(str.isdigit, flight_no))
        if st.button("Track Status"):
            headers = get_sia_headers()
            body = {"airlineCode": "SQ", "flightNumber": flight_digits, "scheduledDepartureDate": time.strftime("%Y-%m-%d")}
            try:
                res = requests.post("https://apigw.singaporeair.com/api/v1/flightstatus/get", headers=headers, json=body)
                data = res.json()["data"]["response"]["flights"][0]["legs"][0]
                
                st.markdown(f"""
                    <div class="flight-card">
                        <h3>{flight_no} | {data['flightStatus']}</h3>
                        <p><b>{data['origin']['airportCode']}</b> ({data['origin']['cityName']}) ➔ <b>{data['destination']['airportCode']}</b> ({data['destination']['cityName']})</p>
                        <p>Dep: {data['scheduledDepartureTime'].split('T')[1][:5]} | Arr: {data['scheduledArrivalTime'].split('T')[1][:5]}</p>
                    </div>
                """, unsafe_allow_html=True)
                
                # Save to History
                supabase.table("flight_history").insert({
                    "user_id": st.session_state["user"].id, "flight_number": flight_no,
                    "origin": data['origin']['airportCode'], "destination": data['destination']['airportCode']
                }).execute()
            except: st.error("Flight not found in Sandbox.")

with tab2:
    st.subheader("Global Live SIA Fleet (OSM Dark)")
    if st.button("Refresh Live Radar"):
        fleet = get_live_sq_fleet()
        # Open Street Map Tiles (Dark Mode)
        m = folium.Map(location=[1.35, 103.98], zoom_start=2, tiles='CartoDB dark_matter')
        
        for p in fleet:
            folium.Marker(
                [p[6], p[5]], 
                popup=f"SIA Flight: {p[1].strip()}",
                icon=folium.Icon(color='orange', icon='plane')
            ).add_to(m)
            
        st_folium(m, width="100%", height=500)
        st.write(f"Displaying **{len(fleet)}** active Singapore Airlines flights.")

# --- 6. HISTORY ---
st.divider()
try:
    hist = supabase.table("flight_history").select("*").eq("user_id", st.session_state["user"].id).order("tracked_at", desc=True).limit(5).execute()
    if hist.data:
        st.subheader("Your Recent Tracking")
        for item in hist.data:
            st.caption(f"🕒 {item['tracked_at'][:10]} | {item['flight_number']} ({item['origin']} → {item['destination']})")
except: pass
