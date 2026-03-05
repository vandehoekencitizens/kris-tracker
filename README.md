# KrisTracker Pro ✈️
**The ultimate operations dashboard for Singapore Airlines enthusiasts.**

KrisTracker Pro combines official airline gateway data with open-source ADS-B telemetry to provide a high-fidelity flight tracking experience, even when official sources are offline.

## ✨ Features
- **Resilient Tracking:** Automatically falls back to `adsb.lol` and `adsb.fi` if the SIA API is down.
- **Mach Physics Engine:** Calculates live Mach numbers based on barometric altitude and ground speed.
- **Network Radar:** A global view of all active `SIA` callsigns currently in the air.
- **Multi-Leg Support:** Visualizes complex routes (e.g., SQ11 SIN-NRT-LAX) including layover periods.
- **Wayfinding:** Built-in PDF viewer for Changi Airport transit maps.

## 🛠️ Setup
1. **API Keys:**
   - Obtain a `SIA_STATUS_KEY` from the Singapore Airlines Developer Portal.
   - Add it to `.streamlit/secrets.toml`:
     ```toml
     SIA_STATUS_KEY = "your_key_here"
     ```
2. **Assets:**
   - Place `Singapore-Changi-Airport-Transit-Area-Wayfinding.pdf` in the root folder.
3. **Install Dependencies:**
   ```bash
   pip install streamlit requests folium streamlit-folium
This project is an independent tool developed for tracking purposes and is not officially affiliated with Singapore Airlines.
