import streamlit as st
import requests
import hashlib
import time
import uuid
import folium
from streamlit_folium import st_folium
from supabase import create_client

# --- 1. INITIALIZATION & SESSION RECOVERY ---
st.set_page_config(page_title="KrisTracker", page_icon="✈️", layout="wide")

@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# Catch session from OAuth redirect
if "user" not in st.session_state:
    try:
        res = supabase.auth.get_session()
        if res and res.session:
            st.session_state["user"] = res.session.user
    except:
        pass

# --- 2. BRANDING & UI ---
SIA_NAVY, SIA_GOLD = "#00266B", "#BD9B60"
st.markdown(f"""
    <style>
    .stApp {{ background-color: {SIA_NAVY}; color: white; }}
    [data-testid="stSidebar"] {{ background-color: #001a33; border-right: 1px solid {SIA_GOLD}; }}
    .flight-card {{
        background: rgba(255, 255, 255, 0.05);
        padding: 20px; border-radius: 15px; border-left: 5px solid {SIA_GOLD}; margin-bottom: 20px;
    }}
    .stButton>button {{ background-color: {SIA_GOLD} !important; color: {SIA_NAVY} !important; font-weight: bold; width: 100%; border-radius: 8px; }}
    .google-btn {{
        display: block; width: 100%; text-align: center; background-color: white; 
        color: #444; padding: 10px; border-radius: 8px; text-decoration: none; 
        font-weight: bold; border: 1px solid #ddd; margin-top: 10px;
    }}
    input {{ color: black !important; }}
    </style>
    """, unsafe_allow_html=True)

# --- 3. SIDEBAR AUTHENTICATION ---
# Loading your uploaded logo file
try:
    st.sidebar.image("singapore-airlines-1-logo-png-transparent.png", width=220)
except:
    st.sidebar.write("✈️ **KrisTracker**")

if "user" not in st.session_state:
    st.sidebar.subheader("Member Access")
    
    # Google OAuth
    res = supabase.auth.sign_in_with_oauth({
        "provider": "google",
        "options": {"redirect_to": "https://your-app-name.streamlit.app"} # <--- UPDATE THIS
    })
    st.sidebar.markdown(f'<a href="{res.url}" target="_self" class="google-btn">🏨 Sign in with Google</a>', unsafe_allow_html=True)
    
    st.sidebar.write("--- OR ---")
    
    mode = st.sidebar.radio("Email Mode", ["Login", "Sign Up"])
    email = st.sidebar.text_input("Email")
    pw = st.sidebar.text_input("Password", type="password")
    
    if st.sidebar.button("Enter Portal"):
        try:
            if mode == "Login":
                resp = supabase.auth.sign_in_with_password({"email": email, "password": pw})
                st.session_state["user"] = resp.user
            else:
                supabase.auth.sign_up({"email": email, "password": pw})
                st.sidebar.success("📩 Confirmation email sent!")
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"Error: {str(e)}")
    st.stop()

else:
    # User Profile Logic
    user = st.session_state["user"]
    full_name = user.user_metadata.get("full_name", user.email)
    avatar = user.user_metadata.get("avatar_url")
    
    if avatar:
        st.sidebar.image(avatar, width=50)
    st.sidebar.success(f"Welcome, **{full_name}**!")
    
    if st.sidebar.button("Log Out"):
        supabase.auth.sign_out()
        del st.session_state["user"]
        st.rerun()

# --- 4. LOGIC FUNCTIONS ---
def get_sia_headers():
    key = st.secrets["SIA_STATUS_KEY"]
    secret = st.secrets.get("SIA_STATUS_SECRET", "")
    ts = str(int(time.time()))
    sig = hashlib.sha256((key + secret + ts).encode()).hexdigest()
    return {
        "api-key": key, "x-signature": sig, "timestamp": ts,
        "x-csl-client-uuid": str(uuid.uuid4()), "Content-Type": "application/json"
    }

def get_live_sq_fleet():
    url = "https://opensky-network.org/api/states/all"
    auth = (st.secrets["OPENSKY_CLIENT_ID"], st.secrets["OPENSKY_CLIENT_SECRET"])
    try:
        r = requests.get(url, auth=auth, timeout=10)
        states = r.json().get("states", [])
        return [s for s in states if s[1] and s[1].strip().startswith("SIA")]
    except: return []

# --- 5. MAIN DASHBOARD ---
st.title("🇸🇬 KrisTracker Dashboard")
t1, t2 = st.tabs(["🔎 Specific Flight Search", "📡 Live OpenStreet Map"])

with t1:
    flight_no = st.text_input("SQ Flight (e.g. SQ638)", "SQ638").upper()
    if st.button("Track Status"):
        with st.spinner("Accessing SIA Gateway..."):
            headers = get_sia_headers()
            body = {"airlineCode": "SQ", "flightNumber": ''.join(filter(str.isdigit, flight_no)), "scheduledDepartureDate": time.strftime("%Y-%m-%d")}
            try:
                res = requests.post("https://apigw.singaporeair.com/api/v1/flightstatus/get", headers=headers, json=body)
                data = res.json()["data"]["response"]["flights"][0]["legs"][0]
                st.markdown(f"""
                    <div class="flight-card">
                        <h3>{flight_no} | {data['flightStatus']}</h3>
                        <p><b>{data['origin']['airportCode']}</b> ({data['origin']['cityName']}) ➔ <b>{data['destination']['airportCode']}</b> ({data['destination']['cityName']})</p>
                    </div>
                """, unsafe_allow_html=True)
                supabase.table("flight_history").insert({"user_id": user.id, "flight_number": flight_no, "origin": data['origin']['airportCode'], "destination": data['destination']['airportCode']}).execute()
            except: 
                st.error("Data unavailable. Ensure the flight exists today (Sandbox: SQ638).")

with t2:
    if st.button("Refresh Fleet Radar"):
        with st.spinner("Fetching global fleet positions..."):
            fleet = get_live_sq_fleet()
            m = folium.Map(location=[1.35, 103.98], zoom_start=3, tiles='CartoDB dark_matter')
            for p in fleet:
                folium.Marker([p[6], p[5]], popup=f"Flight: {p[1].strip()}", icon=folium.Icon(color='orange', icon='plane')).add_to(m)
            st_folium(m, width="100%", height=500)
            st.write(f"Currently tracking **{len(fleet)}** active SIA aircraft.")

# --- 6. HISTORY ---
st.divider()
try:
    hist = supabase.table("flight_history").select("*").eq("user_id", user.id).order("tracked_at", desc=True).limit(5).execute()
    if hist.data:
        st.subheader("Recent Activity")
        for item in hist.data:
            st.caption(f"🕒 {item['tracked_at'][:10]} | {item['flight_number']} ({item['origin']} → {item['destination']})")
except: pass
