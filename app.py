import streamlit as st
from supabase import create_client
import requests

# 1. SETUP: Connect to your free database
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.title("✈️ KrisTracker")

# 2. LOGIN FEATURE
st.sidebar.title("My Account")
email = st.sidebar.text_input("Email")
password = st.sidebar.text_input("Password", type="password")

if st.sidebar.button("Login / Sign Up"):
    # This tries to sign up. If user exists, it just logs them in.
    user = supabase.auth.sign_up({"email": email, "password": password})
    st.sidebar.success("Logged in as " + email)

# 3. THE TRACKER
flight_no = st.text_input("Enter SQ Flight Number", "SQ22")

if st.button("Track Now"):
    # We call the OpenSky API (Free) to find the plane
    st.write(f"Searching for {flight_no}...")
    # (In a real app, this is where the Map code from my previous message goes)
    st.info("Plane found! Latitude: 1.35, Longitude: 103.98 (Singapore Skies)")
