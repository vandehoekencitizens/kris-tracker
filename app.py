import streamlit as st
import requests
import hashlib
import time
import uuid
import folium
from streamlit_folium import st_folium
from supabase import create_client, Client

# --- 1. CONFIGURATION & SECRETS ---
st.set_page_config(page_title="KrisTracker", page_icon="✈️", layout="wide")

@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- 2. AUTHENTICATION LOGIC ---
def get_sia_headers(api_type):
    if api_type == "status":
        key, secret = st.secrets["SIA_STATUS_KEY"], st.secrets["SIA_STATUS_SECRET"]
    elif api_type == "search":
        key, secret = st.secrets["SIA_SEARCH_KEY"], st.secrets["SIA_SEARCH_SECRET"]
    else:
        key, secret = st.secrets["SIA_DEST_KEY"], st.secrets["SIA_DEST_SECRET"]

    timestamp = str(int(time.time()))
    # Signature: SHA256(Key + Secret + Timestamp)
    signature_base = key + secret + timestamp
    signature = hashlib.sha256(signature_base.encode()).hexdigest()
    
    return {
        "api-key": key,
        "x-signature": signature,
        "timestamp": timestamp,
        "x-csl-client-uuid": str(uuid.uuid4()),
        "Content-Type": "application/json"
    }

# --- 3. SIDEBAR: LOGIN/SIGNUP ---
st.sidebar.title("🔐 KrisTracker Members")
if "user" not in st.session_state:
    auth_mode = st.sidebar.radio("Action", ["Login", "Sign Up"])
    email = st.sidebar.text_input("Email")
    password = st.sidebar.text_input("Password", type="password")
    
    if auth_mode == "Login":
        if st.sidebar.button("Log In"):
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state["user"] = res.user
                st.rerun()
            except:
                st.sidebar.error("Invalid Login.")
    else:
        if st.sidebar.button("Register"):
            try:
                supabase.auth.sign_up({"email": email, "password": password})
                st.sidebar.success("Check your email for confirmation!")
            except:
                st.sidebar.error("Sign up failed.")
else:
    st.sidebar.write(f"Logged in: **{st.session_state['user'].email}**")
    if st.sidebar.button("Log Out"):
        del st.session_state["user"]
        st.rerun()

# --- 4. MAIN APP LOGIC (LOCKED) ---
if "user" not in st.session_state:
    st.title("🇸🇬 KrisTracker")
    st.info("Welcome! Please log in from the sidebar to track Singapore Airlines flights.")
    st.stop()

# --- 5. THE TRACKER ---
st.title("✈️ Live Flight Tracking")

flight_input = st.text_input("Enter SQ Flight Number", "SQ638").upper()
# Extract digits (e.g., 'SQ638' -> '638')
flight_digits = ''.join(filter(str.isdigit, flight_input))

if st.button("Track Now"):
    headers = get_sia_headers("status")
    payload = {
        "airlineCode": "SQ",
        "flightNumber": flight_digits,
        "scheduledDepartureDate": time.strftime("%Y-%m-%d")
    }
    
    # Request to SIA API
    with st.spinner("Fetching official SIA data..."):
        try:
            url = "https://apigw.singaporeair.com/api/v1/flightstatus/get"
            response = requests.post(url, headers=headers, json=payload)
            data = response.json()
            
            # Navigating the JSON Sample #1 Structure
            flight_info = data["data"]["response"]["flights"][0]["legs"][0]
            
            # DISPLAY RESULTS
            c1, c2, c3 = st.columns(3)
            c1.metric("Status", flight_info["flightStatus"])
            c2.metric("Origin", flight_info["origin"]["airportCode"])
            c3.metric("Destination", flight_info["destination"]["airportCode"])
            
            st.divider()
            
            # MAP (Using default coordinates for the Sample)
            st.subheader("📍 Live Position")
            m = folium.Map(location=[1.35, 103.98], zoom_start=4)
            folium.Marker(
                [1.35, 103.98], 
                popup=f"SQ{flight_digits} to {flight_info['destination']['cityName']}",
                icon=folium.Icon(color='blue', icon='plane')
            ).add_to(m)
            st_folium(m, width=1000, height=450)
            
        except Exception as e:
            st.error(f"Flight not found or API Limit reached. (Sandbox usually only likes SQ638)")
            st.write("Tip: Make sure your Status Key is Active in the SIA Portal.")
