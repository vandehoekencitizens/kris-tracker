import streamlit as st
import requests
import hashlib
import time
import uuid
import folium
from streamlit_folium import st_folium
from supabase import create_client

# --- 1. INITIALIZATION & SESSION RECOVERY ---
st.set_page_config(page_title="KrisTracker Executive", page_icon="✈️", layout="wide")

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

# --- 2. EXECUTIVE UI (HIGH-CONTRAST & GLASSMORPHISM) ---
SIA_DEEP_NAVY = "#000C24"     
SIA_GOLD_ACCENT = "#D8B24A"   
SIA_CHAMPAGNE = "#F7F3E8"     
SIA_CARD_BG = "rgba(255, 255, 255, 0.07)"

st.markdown(f"""
    <style>
    .stApp {{ background-color: {SIA_DEEP_NAVY}; color: {SIA_CHAMPAGNE}; }}
    [data-testid="stSidebar"] {{ background-color: #000612; border-right: 1px solid {SIA_GOLD_ACCENT}44; }}
    
    /* Input Fields: Pure High-Contrast */
    input {{ 
        background-color: #FFFFFF !important; 
        color: #000000 !important; 
        border: 2px solid {SIA_GOLD_ACCENT} !important;
        border-radius: 4px !important;
    }}
    
    /* Buttons: Executive Gold */
    .stButton>button {{ 
        background-color: {SIA_GOLD_ACCENT} !important; 
        color: #000 !important; 
        font-weight: 700 !important;
        letter-spacing: 1.2px;
        text-transform: uppercase;
        border: none; padding: 0.75rem;
    }}
    .stButton>button:hover {{ box-shadow: 0 0 20px {SIA_GOLD_ACCENT}88; transform: translateY(-1px); }}

    /* Glassmorphism Flight Card */
    .flight-card {{
        background: {SIA_CARD_BG};
        backdrop-filter: blur(12px);
        padding: 25px; border-radius: 15px; 
        border: 1px solid rgba(216, 178, 74, 0.3); 
        margin-bottom: 20px;
    }}

    .google-btn {{
        display: block; text-align: center; background-color: #FFF; color: #000;
        padding: 12px; border-radius: 4px; text-decoration: none; font-weight: bold;
        margin-top: 10px; border: 1px solid #ccc;
    }}
    
    h1, h2, h3 {{ color: {SIA_GOLD_ACCENT} !important; font-weight: 300 !important; }}
    </style>
    """, unsafe_allow_html=True)

# --- 3. SIDEBAR AUTH ---
try:
    st.sidebar.image("singapore-airlines-1-logo-png-transparent.png", width=220)
except:
    st.sidebar.title("KrisTracker")

if "user" not in st.session_state:
    st.sidebar.subheader("Member Access")
    
    # Google OAuth (Crucial: Update the redirect_to URL below)
    res = supabase.auth.sign_in_with_oauth({
        "provider": "google",
        "options": {"redirect_to": "https://kristracker.streamlit.app/"} 
    })
    st.sidebar.markdown(f'<a href="{res.url}" target="_self" class="google-btn">🏨 Sign in with Google</a>', unsafe_allow_html=True)
    
    st.sidebar.write("--- OR ---")
    email = st.sidebar.text_input("Email")
    pw = st.sidebar.text_input("Password", type="password")
    
    if st.sidebar.button("Access Lounge"):
        try:
            resp = supabase.auth.sign_in_with_password({"email": email, "password": pw})
            st.session_state["user"] = resp.user
            st.rerun()
        except:
            st.sidebar.error("Invalid Credentials")
    st.stop()
else:
    user = st.session_state["user"]
    name = user.user_metadata.get("full_name", user.email)
    st.sidebar.success(f"Welcome, {name}")
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

# --- 5. MAIN CONTENT ---
st.title("🇸🇬 KrisTracker Executive Dashboard")
t1, t2 = st.tabs(["🔎 Flight Status", "📡 Live Radar"])

with t1:
    col1, col2 = st.columns([1, 2])
    with col1:
        flight_no = st.text_input("Flight Number", "SQ638").upper()
        track_btn = st.button("Track Progress")
    
    if track_btn:
        with st.spinner("Authenticating with SIA Gateway..."):
            headers = get_sia_headers()
            body = {"airlineCode": "SQ", "flightNumber": ''.join(filter(str.isdigit, flight_no)), "scheduledDepartureDate": time.strftime("%Y-%m-%d")}
            try:
                res = requests.post("https://apigw.singaporeair.com/api/v1/flightstatus/get", headers=headers, json=body)
                data = res.json()["data"]["response"]["flights"][0]["legs"][0]
                with col2:
                    st.markdown(f"""
                        <div class="flight-card">
                            <h2 style="margin-top:0;">{flight_no} | {data['flightStatus']}</h2>
                            <hr style="border-color:{SIA_GOLD_ACCENT}33;">
                            <p style="font-size:1.2rem;"><b>{data['origin']['airportCode']}</b> → <b>{data['destination']['airportCode']}</b></p>
                            <p>City: {data['destination']['cityName']}</p>
                        </div>
                    """, unsafe_allow_html=True)
                # History Save
                supabase.table("flight_history").insert({"user_id": user.id, "flight_number": flight_no, "origin": data['origin']['airportCode'], "destination": data['destination']['airportCode']}).execute()
            except:
                st.error("Live data restricted. (Sandbox SQ638 allowed).")

with t2:
    if st.button("Refresh Global Radar"):
        fleet = get_live_sq_fleet()
        m = folium.Map(location=[1.35, 103.98], zoom_start=3, tiles='CartoDB dark_matter')
        for p in fleet:
            folium.Marker([p[6], p[5]], popup=f"SQ Flight: {p[1].strip()}", 
                          icon=folium.Icon(color='orange', icon='plane')).add_to(m)
        st_folium(m, width="100%", height=550)

# --- 6. FOOTER HISTORY ---
st.write("")
try:
    hist = supabase.table("flight_history").select("*").eq("user_id", user.id).order("tracked_at", desc=True).limit(3).execute()
    if hist.data:
        st.markdown(f"<h3 style='font-size:1rem;'>Recent Activity</h3>", unsafe_allow_html=True)
        cols = st.columns(3)
        for i, item in enumerate(hist.data):
            cols[i].caption(f"✈️ {item['flight_number']} ({item['origin']}- {item['destination']})")
except: pass
