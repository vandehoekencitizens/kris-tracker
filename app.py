import streamlit as st
import requests, uuid, time
from datetime import datetime

# --- 1. SETTINGS & STYLING ---
st.set_page_config(page_title="KrisTracker Dispatch Pro", page_icon="✈️", layout="wide")

SIA_NAVY, SIA_GOLD = "#00266B", "#BD9B60"
st.markdown(f"""<style>
    .dispatch-card {{ background: white; border-radius: 12px; box-shadow: 0 10px 40px rgba(0,0,0,0.08); overflow: hidden; margin-bottom: 2rem; border: 1px solid #eef0f2; }}
    .header-band {{ background: {SIA_NAVY}; color: white; padding: 25px 40px; display: flex; justify-content: space-between; align-items: center; }}
    .status-pill {{ padding: 8px 18px; border-radius: 30px; font-weight: 800; font-size: 13px; }}
    .status-on-time {{ background: #e7f7ed; color: #28a745; }}
    .status-delayed {{ background: #fff4f4; color: #dc3545; }}
    .main-grid {{ display: grid; grid-template-columns: 1fr 0.4fr 1fr; gap: 20px; padding: 40px; align-items: center; }}
    .label-tiny {{ font-size: 11px; font-weight: 700; color: #999; text-transform: uppercase; margin-bottom: 4px; }}
    .val-large {{ font-size: 34px; font-weight: 800; color: {SIA_NAVY}; line-height: 1.1; }}
    .val-sub {{ font-size: 14px; color: #666; margin-top: 2px; font-weight: 500; }}
    .detail-bar {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); background: #fafafa; border-top: 1px solid #eee; padding: 20px 40px; gap: 20px; }}
    .btn-map {{ display: inline-block; padding: 8px 15px; background: {SIA_GOLD}; color: white !important; border-radius: 4px; text-decoration: none; font-weight: bold; font-size: 12px; }}
</style>""", unsafe_allow_html=True)

# --- 2. DATA ENGINES (SIA + ADS-B) ---
def get_fastest_adsb(f_num):
    callsign = f"SIA{f_num}".upper()
    for url in ["https://opendata.adsb.fi/api/v2/callsign/", "https://api.adsb.lol/v2/callsign/"]:
        try:
            r = requests.get(f"{url}{callsign}", timeout=1.5).json()
            if r.get("aircraft"): return r["aircraft"][0]
        except: continue
    return None

def get_sia_data(f_num, date_str):
    url = "https://apigw.singaporeair.com/api/uat/v2/flightstatus/getbynumber"
    headers = {"api_key": st.secrets["SIA_STATUS_KEY"], "x-csl-client-id": "SPD", "x-csl-client-uuid": str(uuid.uuid4())}
    try:
        res = requests.post(url, json={"airlineCode": "SQ", "flightNumber": f_num, "scheduledDepartureDate": date_str}, headers=headers, timeout=5).json()
        return res.get("data", {}).get("response", {}).get("flights", [None])[0]
    except: return None

def format_t(iso_str):
    if not iso_str: return None
    try: return datetime.fromisoformat(iso_str.replace("Z", "")).strftime("%H:%M")
    except: return iso_str[-5:]

# --- 3. THE DISPATCH RENDERER (11 DETAILS) ---
def render_dispatch_card(sia_data, adsb=None):
    leg = sia_data.get("legs", [{}])[0]
    origin, dest = leg.get("origin", {}), leg.get("destination", {})
    status = leg.get("flightStatus", "Scheduled").upper()
    
    # Time Logic
    s_dep, a_dep = leg.get("scheduledDepartureTime"), leg.get("actualDepartureTime")
    s_arr, a_arr, e_arr = leg.get("scheduledArrivalTime"), leg.get("actualArrivalTime"), leg.get("estimatedArrivalTime")
    is_landed = "ARRIVED" in status or "LANDED" in status
    is_departed = a_dep is not None

    # Terminal Logic
    arr_term = dest.get("airportTerminal", "TBA")
    if dest.get("airportCode") == "SIN" and (not arr_term or arr_term == "TBA"): arr_term = "T2/3"
    dep_term = origin.get("airportTerminal", "1")
    if origin.get("airportCode") == "KUL" and dep_term == "M": dep_term = "1"

    # UI Rendering
    st.markdown(f"""
    <div class="dispatch-card">
        <div class="header-band">
            <div><small>FLIGHT NUMBER</small><div style="font-size:26px; font-weight:900;">SQ {sia_data.get('flightNumber')}</div></div>
            <div class="status-pill status-on-time">{status}</div>
        </div>
        <div class="main-grid">
            <div>
                <div class="label-tiny">Departure ({origin.get('airportCode')})</div>
                <div class="val-large">{format_t(a_dep) if is_departed else format_t(s_dep)}</div>
                <div class="val-sub">{"Actual" if is_departed else "Scheduled"} Departure</div>
                {f'<div class="val-sub" style="font-size:12px; color:#aaa;">Scheduled: {format_t(s_dep)}</div>' if is_departed else ""}
            </div>
            <div style="text-align:center; opacity:0.2; font-size:30px;">✈️</div>
            <div style="text-align:right;">
                <div class="label-tiny">Arrival ({dest.get('airportCode')})</div>
                <div class="val-large">{format_t(a_arr) if is_landed else (format_t(e_arr) or format_t(s_arr))}</div>
                <div class="val-sub">{"Actual" if is_landed else "Estimated"} Arrival</div>
                <div class="val-sub" style="font-size:12px; color:#aaa;">Scheduled: {format_t(s_arr)}</div>
            </div>
        </div>
        <div class="detail-bar">
            <div><div class="label-tiny">Aircraft</div><b>{leg.get('aircraftType', 'B787')}</b></div>
            <div><div class="label-tiny">Reg</div><b>{adsb.get('r', '9V-XXX') if adsb else '---'}</b></div>
            <div><div class="label-tiny">Dep Terminal</div><b>{dep_term}</b></div>
            <div><div class="label-tiny">Arr Terminal</div><b>{arr_term}</b></div>
            {f'<div><a href="https://www.singaporeair.com/saar5/pdf/travel-info/Singapore-Changi-Airport-Transit-Area-Wayfinding.pdf" target="_blank" class="btn-map">📂 MAP</a></div>' if dest.get('airportCode') == "SIN" else ""}
        </div>
    </div>
    """, unsafe_allow_html=True)

# --- 4. APP INTERFACE (RETAINED FEATURES) ---
st.sidebar.title("🛠️ KrisTracker Tools")
debug_mode = st.sidebar.toggle("Debug Mode", False)
search_mode = st.sidebar.radio("Mode", ["Flight Number", "Route Search"])

if search_mode == "Flight Number":
    c1, c2 = st.columns(2)
    f_num = c1.text_input("SQ #", "115")
    f_date = c2.date_input("Date")
    if st.button("TRACK"):
        with st.spinner("Fetching Dispatch Data..."):
            sia = get_sia_data(f_num, str(f_date))
            adsb = get_fastest_adsb(f_num)
            if sia:
                render_dispatch_card(sia, adsb)
                if debug_mode: st.json(sia)
            else: st.error("Flight not found.")

elif search_mode == "Route Search":
    st.subheader("Route Search Engine")
    # Existing route search logic would go here...
    st.info("Route search is ready for integration.")
