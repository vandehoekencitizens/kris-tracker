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

# Auto-recovery for Google OAuth sessions
if "user" not in st.session_state:
    try:
        res = supabase.auth.get_session()
        if res and res.session:
            st.session_state["user"] = res.session.user
    except:
        pass

# --- 2. HIGH-CONTRAST PREMIUM UI ---
SIA_DEEP_NAVY = "#001030"     # Deep background
SIA_GOLD_ACCENT = "#D8B24A"   # Rich Gold for accents
SIA_CHAMPAGNE = "#F7F3E8"     # Off-white for readability
SIA_SIDEBAR = "#000814"       # Near-black sidebar

st.markdown(f"""
    <style>
    .stApp {{ background-color: {SIA_DEEP_NAVY}; color: {SIA_CHAMPAGNE}; }}
    [data-testid="stSidebar"] {{ background-color: {SIA_SIDEBAR}; border-right: 1px solid {SIA_GOLD_ACCENT}; }}
    
    /* Search Inputs: High Contrast */
    input {{ background-color: #FFFFFF !important; color: #000000 !important; border-radius: 8px !important; }}
    
    /* Buttons: Dark text on Gold */
    .stButton>button {{ 
        background-color: {SIA_GOLD_ACCENT} !important; color: {SIA_DEEP_NAVY} !important; 
        font-weight: bold; border-radius: 8px; border: none; padding: 0.6rem;
    }}
    
    /* Flight Cards */
    .flight-card {{
        background: rgba(255, 255, 255, 0.08); padding: 24px; border-radius: 12px; 
        border: 1px solid {SIA_GOLD_ACCENT}; margin-bottom: 20px; color: white;
    }}
    
    .google-btn {{
        display: block; width: 100%; text-align: center; background-color: white; 
        color: #444; padding: 12px; border-radius: 8px; text-decoration: none; 
        font-weight: bold; border: 1px solid #ddd; margin-top: 10px;
    }}
    
    h1, h2, h3 {{ color: {SIA_GOLD_ACCENT} !important; }}
    </style>
    """, unsafe_allow_html=True)

# --- 3. SIDEBAR AUTH ---
try:
    # Use your uploaded local file
    st.sidebar.image("singapore-airlines-1-logo-png-transparent.png", width=220)
except:
    st.sidebar.subheader("🇸🇬 KrisTracker")

if "user" not in st.session_state:
    st.sidebar.subheader("Member Login")
    
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
            st.sidebar.error(f"Auth Error: {str(e)}")
    st.stop()
else:
    user = st.session_state["user"]
    name = user.user_metadata.get("full_name", user.email)
    st.sidebar.success(f"Welcome, **{name}**")
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
st.title("🇸🇬 KrisTracker Dashboard")
t1, t2 = st.tabs(["🔎 Flight Status", "📡 Live Fleet Radar"])

with t1:
    flight_no = st.text_input("Flight Number", "SQ638").upper()
    if st.button("Track Flight"):
        with st.spinner("Connecting to SIA Gateway..."):
            headers = get_sia_headers()
            body = {"airlineCode": "SQ", "flightNumber": ''.join(filter(str.isdigit, flight_no)), "scheduledDepartureDate": time.strftime("%Y-%m-%d")}
            try:
                res = requests.post("https://apigw.singaporeair.com/api/v1/flightstatus/get", headers=headers, json=body)
                data = res.json()["data"]["response"]["flights"][0]["legs"][0]
                st.markdown(f"""
                    <div class="flight-card">
                        <h2>{flight_no} | {data['flightStatus']}</h2>
                        <p><b>Origin:</b> {data['origin']['airportCode']} ({data['origin']['cityName']})</p>
                        <p><b>Destination:</b> {data['destination']['airportCode']} ({data['destination']['cityName']})</p>
                    </div>
                """, unsafe_allow_html=True)
                # Save to Supabase
                supabase.table("flight_history").insert({
                    "user_id": user.id, "flight_number": flight_no, 
                    "origin": data['origin']['airportCode'], "destination": data['destination']['airportCode']
                }).execute()
            except:
                st.error("Data not available for this flight today (Sandbox usually limited to SQ638).")

with t2:
    if st.button("Refresh Fleet Radar"):
        with st.spinner("Fetching global aircraft positions..."):
            fleet = get_live_sq_fleet()
            m = folium.Map(location=[1.35, 103.98], zoom_start=3, tiles='CartoDB dark_matter')
            for p in fleet:
                folium.Marker([p[6], p[5]], popup=f"Flight: {p[1].strip()}", 
                              icon=folium.Icon(color='orange', icon='plane')).add_to(m)
            st_folium(m, width="100%", height=500)
            st.info(f"Tracking {len(fleet)} SIA aircraft worldwide.")

# --- 6. HISTORY ---
st.divider()
try:
    hist = supabase.table("flight_history").select("*").eq("user_id", user.id).order("tracked_at", desc=True).limit(5).execute()
    if hist.data:
        st.subheader("Your Recent Searches")
        for item in hist.data:
            st.caption(f"🕒 {item['tracked_at'][:10]} | {item['flight_number']} ({item['origin']} → {item['destination']})")
except: pass
