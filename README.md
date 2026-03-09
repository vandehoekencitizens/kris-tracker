# ✈️ KrisTracker Pro: Singapore Airlines Operations Dashboard

**KrisTracker Pro** is a high-performance flight tracking and manifest visualization tool designed for Singapore Airlines (SIA). It merges live global telemetry from AirLabs with official schedule data from the SIA API Gateway to create a unified, premium operational experience.

---

## 🚀 Key Features

### 📡 Persistent Interactive Radar
* **Anti-Reload Logic**: Implements Session State and `st.cache_data` to ensure the map remains fixed on your current zoom/center even when selecting aircraft.
* **Live Path Tracking**: Dynamically renders flight "breadcrumbs" (trails) for the selected aircraft.
* **Telemetry Corrections**: 
    * **Altitude**: Automatically converted from Meters to **Feet** ($m \times 3.28084$).
    * **Groundspeed**: Automatically converted from KM/H to **Knots** ($km/h \times 0.539957$).

### 🔍 Search Manifest (Data Fusion)
* **AirLabs Priority**: Uses a dual-API fetch system. If data exists in both AirLabs and the SIA Gateway, the app prioritizes **AirLabs** for real-time truth while using the **SIA API** to fill in terminal and gate gaps.
* **Status Visualization**: Custom SIA-branded "Status Pills" (Scheduled, En-Route, Landed) and detailed manifest layouts.

### 🗺️ Terminal Wayfinding
* **Integrated Changi Map**: A built-in high-resolution PDF viewer for the Singapore Changi Airport Transit Area, embedded directly into the Streamlit interface.

---

## 🛠️ Technical Setup

### 1. Prerequisites
Install the required Python libraries:
```bash
pip install streamlit requests folium streamlit-folium
---
### 2. API Credentials
Create a file at .streamlit/secrets.toml in your project folder:
```bash
SIA_STATUS_KEY = "YOUR_SIA_GATEWAY_API_KEY"
AIRLABS_API_KEY = "YOUR_AIRLABS_V9_API_KEY"
---
### 3. Required AssetsFor the UI to function correctly, ensure these files are in your root directory:
SQ loading screen.mp4 — Radar loading video.f5c530aa-d922-4920-9313-63a11c7f2921.png — Custom aircraft map marker.Singapore-Changi-Airport-Transit-Area-Wayfinding.pdf — Wayfinding guide.Aircraft Photos: 9V-SMI.jpg, 9V-SKY.jpg, 9V-MBO.jpg, 9V-SCK.avif, 9V-SWR.jpg.🖥️ UsageLaunch the dashboard from your terminal:Bashstreamlit run app.py
---
### ⚙️ Unit & Logic ReferenceMetricSource Unit (Raw)Display UnitConversion FactorAltitudeMetersFeet$\times 3.28084$GroundspeedKM/HKnots$\times 0.539957$Data PriorityAirLabsSIA GatewayAirLabs Priority

