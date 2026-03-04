import streamlit as st
import requests
import uuid
import folium
import pandas as pd
import os
from streamlit_folium import st_folium
from supabase import create_client

# --- 1. INITIALIZATION ---
st.set_page_config(page_title="KrisTracker | SIA UAT Portal", page_icon="✈️", layout="wide")

@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- 2. THE "RADAR FIX" (Enhanced OpenSky Query) ---
@st.cache_data(ttl=60)
def get_fleet_cached():
    # Attempting to fetch with more permissive headers
    url = "https://opensky-network.org/api/states/all"
    auth = (st.secrets["OPENSKY_CLIENT_ID"], st.secrets["OPENSKY_CLIENT_SECRET"])
    try:
        r = requests.get(url, auth=auth, timeout=15)
        if r.status_code != 200:
            st.sidebar.error(f"OpenSky API denied access ({r.status_code})")
            return []
        
        data = r.json().get("states", [])
        sia_flights = []
        for s in data:
            callsign = str(s[1]).strip() if s[1] else ""
            # SQ/SIA can sometimes appear as "SIA" or just "SQ" in telemetry
            if callsign.startswith("SIA") or callsign.startswith("SQ"):
                sia_flights.append({
                    "Callsign": callsign,
                    "Reg": s[0].upper(),
                    "Lat": s[6], "Lon": s[5],
                    "Alt (ft)": int(s[7] * 3.28) if s[7] else 0,
                    "GS (kts)": int(s[9] * 1.94) if s[9] else 0
                })
        return sia_flights
    except Exception as e:
        st.sidebar.warning("Live Radar currently offline.")
        return []

# --- 3. THE "UAT SEARCH FIX" ---
def call_sia_uat(endpoint, payload):
    # Using the UAT specific endpoint and your STATUS KEY
    # NOTE: Many SIA UAT environments use /api/uat/ instead of /api/
    url = f"https://apigw.singaporeair.com/api/uat/v1/flightstatus/{endpoint}"
    
    headers = {
        "Content-Type": "application/json",
        "api_key": st.secrets["SIA_STATUS_KEY"],
        "x-csl-client-uuid": str(uuid.uuid4())
    }
    
    try:
        # We use a POST request as per SIA docs for getbyroute/getbynumber
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        
        # DEBUG: Show the raw response if it fails so we can see the error
        if res.status_code != 200:
            return {"status": "HTTP_ERROR", "code": res.status_code, "msg": res.text}
            
        return res.json()
    except Exception as e:
        return {"status": "FAILURE", "message": str(e)}

# --- 4. LOGIN BYPASS (For testing speed) ---
if "user" not in st.session_state:
    st.title("KrisTracker Login")
    with st.form("login"):
        em = st.text_input("Email")
        pw = st.text_input("Password", type="password")
        if st.form_submit_button("SIGN IN"):
            try:
                resp = supabase.auth.sign_in_with_password({"email": em.lower().strip(), "password": pw})
                st.session_state["user"] = resp.user
                st.rerun()
            except:
                st.error("Invalid Login. Ensure email is confirmed or delete/re-register user in Supabase.")
    st.stop()

# --- 5. DASHBOARD ---
st.title("SIA Flight Operations (UAT)")

t_radar, t_search = st.tabs(["📡 LIVE RADAR", "🔎 FLIGHT SEARCH"])

with t_radar:
    fleet = get_fleet_cached()
    col_a, col_b = st.columns([3, 1])
    
    with col_a:
        m = folium.Map(location=[1.35, 103.98], zoom_start=3, tiles='CartoDB dark_matter')
        for ac in fleet:
            if ac['Lat'] and ac['Lon']:
                folium.Marker([ac['Lat'], ac['Lon']], popup=ac['Callsign'], 
                              icon=folium.Icon(color='orange', icon='plane')).add_to(m)
        st_folium(m, width="100%", height=500, key="radar_main")
    
    with col_b:
        st.metric("SIA Airborne", len(fleet))
        if fleet:
            st.dataframe(pd.DataFrame(fleet).drop(['Lat', 'Lon'], axis=1), hide_index=True)
        else:
            st.info("No planes found in current scan. OpenSky might be rate-limiting.")

with t_search:
    st.subheader("Search by Route (UAT)")
    c1, c2, c3 = st.columns(3)
    orig = c1.text_input("From (IATA)", "SIN")
    dest = c2.text_input("To (IATA)", "LHR")
    date = c3.date_input("Departure Date")
    
    if st.button("EXECUTE UAT SEARCH"):
        # The payload format MUST match exactly
        payload = {
            "originAirportCode": orig.upper(),
            "destinationAirportCode": dest.upper(),
            "scheduledDepartureDate": date.strftime("%Y-%m-%d")
        }
        
        with st.spinner("Querying SIA UAT..."):
            res = call_sia_uat("getbyroute", payload)
            
        if res and res.get("status") == "SUCCESS":
            st.success("Flights retrieved successfully.")
            st.json(res.get("data"))
        else:
            st.error(f"Search Failed. Error Info: {res}")
