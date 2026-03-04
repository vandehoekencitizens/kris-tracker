import streamlit as st
import requests
import hashlib
import time
import folium
from streamlit_folium import st_folium

# --- 1. THE OPEN SKY TOKEN (FOR LIVE GPS) ---
def get_opensky_token():
    auth_url = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": st.secrets["OPENSKY_CLIENT_ID"],
        "client_secret": st.secrets["OPENSKY_CLIENT_SECRET"]
    }
    # This exchanges your Secret for a temporary "Access Token"
    response = requests.post(auth_url, data=data)
    return response.json().get("access_token")

# --- 2. THE SIA SIGNATURE (FOR OFFICIAL STATUS) ---
def get_sia_headers():
    api_key = st.secrets["SIA_API_KEY"]
    api_secret = st.secrets["SIA_SECRET"]
    timestamp = str(int(time.time()))
    
    # Formula: SHA256(Key + Secret + Timestamp)
    signature_base = api_key + api_secret + timestamp
    signature = hashlib.sha256(signature_base.encode()).hexdigest()
    
    return {
        "api-key": api_key,
        "x-signature": signature,
        "timestamp": timestamp
    }

# --- 3. THE UI ---
st.title("🇸🇬 KrisTracker Live")

flight_no = st.text_input("Enter SQ Flight Number", "SQ22").upper()

if st.button("Track Flight"):
    # Step A: Get SIA Status (Official Gate/Delay)
    sia_headers = get_sia_headers()
    # Note: Using the SIA Sandbox URL for testing
    sia_url = f"https://api.singaporeair.com/v1/flightstatus/get?flightNumber={flight_no}"
    
    # Step B: Get OpenSky Position (Live Map)
    token = get_opensky_token()
    os_headers = {"Authorization": f"Bearer {token}"}
    os_url = "https://opensky-network.org/api/states/all"
    
    # --- LOGIC TO SHOW RESULTS ---
    st.subheader(f"Status for {flight_no}")
    st.info("Checking official SIA records and live satellite data...")
    
    # (Simplified Map Placeholder)
    st.markdown("### 🗺️ Live Flight Path")
    m = folium.Map(location=[1.35, 103.98], zoom_start=4) # Centered on Singapore
    folium.Marker([1.35, 103.98], popup="Singapore Changi").add_to(m)
    st_folium(m, width=700, height=400)
