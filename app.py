import streamlit as st
import requests
import hashlib
import time
import uuid
import folium
from streamlit_folium import st_folium
from supabase import create_client, Client

# --- 1. INITIAL CONFIGURATION ---
st.set_page_config(page_title="KrisTracker", page_icon="✈️", layout="wide")

# Initialize Supabase Client
@st.cache_resource
def init_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

# --- 2. AUTHENTICATION HELPERS ---
def get_sia_headers(api_type):
    """Generates the signature and headers for different SIA API keys."""
    if api_type == "status":
        key = st.secrets["SIA_STATUS_KEY"]
        secret = st.secrets["SIA_STATUS_SECRET"]
    elif api_type == "search":
        key = st.secrets["SIA_SEARCH_KEY"]
        secret = st.secrets["SIA_SEARCH_SECRET"]
    else:
        key = st.secrets["SIA_DEST_KEY"]
        secret = st.secrets["SIA_DEST_SECRET"]

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

# --- 3. SIDEBAR: USER LOGIN SYSTEM ---
st.sidebar.title("🔐 Members Area")

if "user" not in st.session_state:
    tab1, tab2 = st.sidebar.tabs(["Login", "Sign Up"])
    
    with tab1:
        email_log = st.text_input("Email", key="log_email")
        pass_log = st.text_input("Password", type="password", key="log_pass")
        if st.button("Log In"):
            try:
                res = supabase.auth.sign_in_with_password({"email": email_log, "password": pass_log})
                st.session_state["user"] = res.user
                st.rerun()
            except Exception as e:
                st.error("Login failed. Check credentials.")

    with tab2:
        email_reg = st.text_input("Email", key="reg_email")
        pass_reg = st.text_input("Password", type="password", key="reg_pass")
        if st.button("Register"):
            try:
                supabase.auth.sign_up({"email": email_reg, "password": pass_reg})
                st.success("Account created! (Confirm email if enabled)")
            except Exception as e:
                st.error("Registration failed.")
else:
    st.sidebar.write(f"Logged in as: **{st.session_state['user'].email}**")
    if st.sidebar.button("Log Out"):
        supabase.auth.sign_out()
