import streamlit as st
import requests
import hashlib
import time
import uuid
import folium
from streamlit_folium import st_folium
from supabase import create_client, Client

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="KrisTracker", page_icon="✈️", layout="wide")

# SIA Official Brand Colors
SIA_NAVY = "#00266B"
SIA_GOLD = "#BD9B60"
SIA_WHITE = "#FFFFFF"

# Initialize Supabase
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- 2. CUSTOM PREMIUM UI (CSS) ---
st.markdown(f"""
    <style>
    .stApp {{
        background-color: {SIA_NAVY};
        color: {SIA_WHITE};
    }}
    [data-testid="stSidebar"] {{
        background-color: #001a33;
        border-right: 1px solid {SIA_GOLD};
    }}
    .flight-card {{
        background-color: rgba(255, 255, 255, 0.05);
        padding: 25px;
        border-radius: 15px;
        border-left: 5px solid {SIA_GOLD};
        margin-bottom: 25px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }}
    .stButton>button {{
        background-color: {SIA_GOLD} !important;
        color: {SIA_NAVY} !important;
        font-weight: bold;
        border-radius: 5px;
        width: 100%;
    }}
    .stMetric {{
        background-color: rgba(255, 255, 255, 0.05);
        padding: 10px;
        border-radius: 10px;
    }}
    </style>
    """, unsafe_allow_html=True)

# --- 3. AUTHENTICATION HELPERS ---
def get_sia_headers(api_type):
    if api_type == "status":
        key, secret = st.secrets["SIA_STATUS_KEY"], st.secrets["SIA_STATUS_SECRET"]
    elif api_type == "search":
        key, secret = st.secrets["SIA_SEARCH_KEY"], st.secrets["SIA_SEARCH_SECRET"]
    else:
        key, secret = st.secrets["SIA_DEST_KEY"], st.secrets["SIA_DEST_SECRET"]

    timestamp = str(int(time.time()))
    signature = hashlib.sha256((key + secret + timestamp).encode()).hexdigest()
    
    return {
        "api-key": key,
        "x-signature": signature,
        "timestamp": timestamp,
        "x-csl-client-uuid": str(uuid.uuid4()),
        "Content-Type": "application/json"
    }

# --- 4. SIDEBAR LOGS & AUTH ---
st.sidebar.image("https://upload.wikimedia.org/wikipedia/en/6/6b/Singapore_Airlines_Logo_2.svg", width=200)
st.sidebar.markdown(f"<h2 style='color:{SIA_GOLD}; text-align:center;'>KrisTracker</h2>", unsafe_allow_html=True)

if "user" not in st.session_state:
    auth_choice = st.sidebar.radio("Member Access", ["Login", "Sign Up"])
    email = st.sidebar.text_input("Email")
    password = st.sidebar.text_input("Password", type="password")
    
    if auth_choice == "Login" and st.sidebar.button("Access Portal"):
        try:
            res = supabase.auth.sign_in_with_password({"email": email, "password": password})
            st.session_state["user"] = res.user
            st.rerun()
        except: st.sidebar.error("Invalid Credentials")
    elif auth_choice == "Sign Up" and st.sidebar.button("Create Account"):
        try:
            supabase.auth.sign_up({"email": email, "password": password})
            st.sidebar.success("Account created!")
        except: st.sidebar.error("Signup failed.")
    st.stop()
else:
    st.sidebar.write(f"Welcome, **{st.session_state['user'].email}**")
    if st.sidebar.button("Logout"):
        del st.session_state["user"]
        st.rerun()

# --- 5. TRACKER MAIN INTERFACE ---
st.title("✈️ Live Flight Tracking")
flight_no = st.text_input("Enter Flight Number", "SQ638").upper()
flight_digits = ''.join(filter(str.isdigit, flight_no))

if st.button("Search Flight Data"):
    with st.spinner("Connecting to SIA Gateway..."):
        headers = get_sia_headers("status")
        body = {"airlineCode": "SQ", "flightNumber": flight_digits, "scheduledDepartureDate": time.strftime("%Y-%m-%d")}
        
        try:
            url = "https://apigw.singaporeair.com/api/v1/flightstatus/get"
            response = requests.post(url, headers=headers, json=body)
            data = response.json()["data"]["response"]["flights"][0]["legs"][0]
            
            # BOARDING PASS UI
            st.markdown(f"""
                <div class="flight-card">
                    <div style='display: flex; justify-content: space-between; align-items: center;'>
                        <div style='text-align: left;'>
                            <p style='color:{SIA_GOLD}; margin:0;'>ORIGIN</p>
                            <h1 style='margin:0;'>{data['origin']['airportCode']}</h1>
                            <p style='margin:0;'>{data['origin']['cityName']}</p>
                        </div>
                        <div style='font-size: 50px;'>✈️</div>
                        <div style='text-align: right;'>
                            <p style='color:{SIA_GOLD}; margin:0;'>DESTINATION</p>
                            <h1 style='margin:0;'>{data['destination']['airportCode']}</h1>
                            <p style='margin:0;'>{data['destination']['cityName']}</p>
                        </div>
                    </div>
                    <hr style='border: 0.1px solid rgba(189,155,96,0.3);'>
                    <h3 style='color:{SIA_GOLD};'>Status: {data['flightStatus']}</h3>
                </div>
            """, unsafe_allow_html=True)
            
            # MAP
            m = folium.Map(location=[1.35, 103.98], zoom_start=4, tiles='CartoDB dark_matter')
            folium.Marker([1.35, 103.98], popup=f"SQ{flight_digits}", icon=folium.Icon(color='orange', icon='plane')).add_to(m)
            st_folium(m, width="100%", height=400)
            
            # SAVE TO SUPABASE
            supabase.table("flight_history").insert({
                "user_id": st.session_state["user"].id,
                "flight_number": f"SQ{flight_digits}",
                "origin": data['origin']['airportCode'],
                "destination": data['destination']['airportCode']
            }).execute()

        except:
            st.error("Flight not found in Sandbox. Try 'SQ638'.")

# --- 6. HISTORY SECTION ---
st.markdown("### 📜 Recent Tracking Activity")
try:
    history = supabase.table("flight_history").select("*").eq("user_id", st.session_state["user"].id).order("tracked_at", desc=True).limit(5).execute()
    if history.data:
        for item in history.data:
            st.caption(f"🕒 {item['tracked_at'][:10]} | {item['flight_number']} | {item['origin']} → {item['destination']}")
except:
    st.info("Start tracking to see your history.")
