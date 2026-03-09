# ✈️ KrisTracker Pro: Singapore Airlines Live Operations Dashboard

**KrisTracker Pro** is a high-fidelity flight tracking and manifest visualization tool built specifically for Singapore Airlines (SIA) operations. It fuses official SIA API data with AirLabs global telemetry to provide a unified, "Flightradar24-style" experience, complete with aircraft imagery, live flight paths, and Changi Airport wayfinding.

---

## 🚀 Key Features

* **📡 Interactive Radar with Live Trails**: Real-time global map showing all active SQ flights. Dynamically fetches and draws the flight path breadcrumbs for selected aircraft.
* **🧠 Smart Data Fusion (Search)**: Deep-dive search by flight number and date. The app uses an advanced data fusion engine that prioritizes **AirLabs** for live operational data, seamlessly filling in any missing gaps using the **Official SIA API Gateway**.
* **🖼️ Telemetry Cards**: Custom sidebar cards for active flights featuring high-resolution aircraft registration imagery (e.g., 9V-SMI, 9V-SKY). Displays live altitude (converted to **feet**) and groundspeed (converted to **knots**).
* **🗺️ Wayfinding**: Built-in interactive PDF viewer for the Singapore Changi Airport Transit Area navigation.
* **⚡ Performance Optimized**: Implements Streamlit **Session-State Caching** to retain map zoom and center, completely eliminating map reloading or flickering during user interactions.

---

## 🛠️ Setup & Installation

### 1. Requirements
Ensure you have **Python 3.9+** installed, then install the required dependencies:
```bash
pip install streamlit requests folium streamlit-folium

### 2. API Keys Configuration
Create a hidden folder named .streamlit in your root directory and add a secrets.toml file with your credentials:
```bash
# .streamlit/secrets.toml
SIA_STATUS_KEY = "YOUR_SIA_GATEWAY_API_KEY"
AIRLABS_API_KEY = "YOUR_AIRLABS_V9_API_KEY"

### 3. Required Local Assets
Ensure the following files are placed in your root folder for the UI to render correctly:

SQ loading screen.mp4 — Custom loading animation for the radar.

f5c530aa-d922-4920-9313-63a11c7f2921.png — Custom aircraft map icon.

Singapore-Changi-Airport-Transit-Area-Wayfinding.pdf — The Changi transit guide.

Aircraft Images: Upload your specific photos mapped to the ICAO codes (e.g., 9V-SMI.jpg, 9V-SKY.jpg, 9V-MBO.jpg, 9V-SCK.avif, 9V-SWR.jpg).

### 🖥️ Running the Application
Launch the dashboard locally using the Streamlit CLI:

```bash
streamlit run app.py

### 🔧 Technical Architecture
Frontend: Streamlit (Wide Layout) with custom CSS injected for SIA Navy (#00266B) and Gold (#BD9B60) branding.

Mapping Engine: Folium with streamlit_folium for bi-directional map interaction.

Telemetry Math: AirLabs outputs speed in km/h and altitude in meters. The script automatically applies multipliers (* 0.539957 for knots, * 3.28084 for feet) for standard aviation reporting.

Caching Strategy: @st.cache_data(ttl=60) is applied to the main fleet API call to respect rate limits and keep the UI lightning-fast, while @st.cache_data(ttl=300) caches specific flight trails.
