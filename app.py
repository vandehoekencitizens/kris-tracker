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

# Auto-recovery for Google OAuth sessions
if "user" not in st.session_state:
    try:
        res = supabase.auth.get_session()
        if res and res.session:
            st.session_state["user"] = res.session.user
    except:
        pass

# --- 2. REFINED EXECUTIVE UI ---
SIA_DEEP_NAVY = "#000C24"     
SIA_GOLD_ACCENT = "#D8B24A"   
SIA_CHAMPAGNE = "#F7F3E8"     

st.markdown(f"""
    <style>
    /* Global Background */
    .stApp {{ background-color: {SIA_DEEP_NAVY}; color: {SIA_CHAMPAGNE}; }}
    
    /* Sidebar Styling */
    [data-testid="stSidebar"] {{ 
        background-color: #000612 !important; 
        border-right: 1px solid {SIA_GOLD_ACCENT}44; 
    }}

    /* LOGO FIX: Turns the black logo into SIA Gold */
    [data-testid="stSidebarContent"] img {{
        filter: brightness(0) saturate(100%) invert(78%) sepia(54%) saturate(436%) hue-rotate(1deg) brightness(92%) contrast(89%);
        padding-top: 20px;
        padding-bottom: 10px;
    }}
    
    /* Input Labels: Tight Vertical Spacing */
    label {{ 
        color: {SIA_GOLD_ACCENT} !important; 
        font-weight: 600 !important;
        font-size: 0.9rem !important;
        margin-bottom: -25px !important;
    }}

    /* High Contrast Input Boxes */
    input {{ 
        background-color: #FFFFFF !important; 
        color: #000000 !important; 
        border: 2px solid {SIA_GOLD_ACCENT} !important;
        border-radius: 4px !important;
    }}
    
    /* Premium Buttons */
    .stButton>button {{ 
        background-color: {SIA_GOLD_ACCENT} !important; 
        color: #000 !important; 
        font-weight: 700 !important;
        text-transform: uppercase;
        border-radius: 4px; border: none;
    }}

    /* Google Login Button Fix */
    .google-btn {{
        display: flex; align-items: center; justify-content: center;
        background-color: #FFFFFF; color: #000000 !important;
        padding: 12px; border-radius: 4px; text-decoration: none !important;
        font-weight: bold; margin: 20px 0; border: 1px solid #ccc;
    }}
    
    .flight-card {{
        background: rgba(255, 255, 255, 0.07);
        backdrop-filter: blur(10px);
        padding: 25px; border-radius: 12px; border: 1px solid {SIA_GOLD_ACCENT}33;
    }}
    </style>
    """, unsafe_allow_html=True)

# --- 3. SIDEBAR AUTH ---
try:
    st.sidebar.image("singapore-airlines-1-logo-png-transparent.png", width=220)
except:
    st.sidebar.title("🇸🇬 KrisTracker")

if "user" not in st.session_state:
    st.sidebar.markdown("<p style='color:#D8B24A; font-weight:bold; margin-bottom:5px;'>Member Access</p>", unsafe_allow_html=True)
    
    # GOOGLE OAUTH WITH PROMPT FIX
    # Note: Replace URL with your actual live streamlit URL
    target_url = "https://your-app-name.streamlit.app/" 
    
    res = supabase.auth.sign_in_with_oauth({
        "provider": "google",
        "options": {
            "redirect_to": target_url,
            "query_params": {"prompt": "select_account"} 
        }
    })
    
    st.sidebar.markdown(f'<a href="{res.url}" target="_self" class="google-btn">🏨 Sign in with Google</a>', unsafe_allow_html=True)
    
    st.sidebar.write("--- OR ---")
    email = st.sidebar.text_input("Email")
    pw = st.sidebar.text_input("Password", type="password")
    
    if st.sidebar.button("Enter Lounge"):
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
st.title("🇸🇬 KrisTracker Executive")
t1, t2 = st.tabs(["🔎 Flight Search", "📡 Fleet Radar"])

with t1:
    f_input = st.text_input("Flight Number", "SQ638").upper()
    if st.button("Track Status"):
        with st.spinner("Accessing SIA Gateway..."):
            headers = get_sia_headers()
            body = {"airlineCode": "SQ", "flightNumber": ''.join(filter(str.isdigit, f_input)), "scheduledDepartureDate": time.strftime("%Y-%m-%d")}
            try:
                res = requests.post("https://apigw.singaporeair.com/api/v1/flightstatus/get", headers=headers, json=body)
                data = res.json()["data"]["response"]["flights"][0]["legs"][0]
                st.markdown(f"""
                    <div class="flight-card">
                        <h3>{f_input} Status: {data['flightStatus']}</h3>
                        <p>{data['origin']['airportCode']} ➔ {data['destination']['airportCode']}</p>
                    </div>
                """, unsafe_allow_html=True)
                supabase.table("flight_history").insert({"user_id": user.id, "flight_number": f_input, "origin": data['origin']['airportCode'], "destination": data['destination']['airportCode']}).execute()
            except: st.error("Flight data unavailable.")

with t2:
    if st.button("Load Live Positions"):
        fleet = get_live_sq_fleet()
        m = folium.Map(location=[1.35, 103.98], zoom_start=3, tiles='CartoDB dark_matter')
        for p in fleet:
            folium.Marker([p[6], p[5]], popup=f"SQ: {p[1].strip()}", icon=folium.Icon(color='orange')).add_to(m)
        st_folium(m, width="100%", height=500)
