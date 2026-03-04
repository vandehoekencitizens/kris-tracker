import hashlib
import time
import streamlit as st

def get_sia_headers(api_type):
    # 1. Pick the right Key/Secret combo
    if api_type == "status":
        api_key = st.secrets["SIA_STATUS_KEY"]
        api_secret = st.secrets["SIA_STATUS_SECRET"]
    elif api_type == "search":
        api_key = st.secrets["SIA_SEARCH_KEY"]
        api_secret = st.secrets["SIA_SEARCH_SECRET"]
    else:
        api_key = st.secrets["SIA_DEST_KEY"]
        api_secret = st.secrets["SIA_DEST_SECRET"]

    timestamp = str(int(time.time()))
    
    # 2. Build the Signature
    # If there's no secret, the signature is just based on the key + timestamp
    signature_base = api_key + api_secret + timestamp
    signature = hashlib.sha256(signature_base.encode()).hexdigest()
    
    return {
        "api-key": api_key,
        "x-signature": signature,
        "timestamp": timestamp,
        "Content-Type": "application/json"
    }
