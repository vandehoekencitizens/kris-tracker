Gemini said
Here is a comprehensive README.md designed for your repository. It includes clear setup instructions, the feature list, and a copy-paste ready structure.

✈️ KrisTracker Pro: Singapore Airlines Live Operations Dashboard
KrisTracker Pro is a high-fidelity flight tracking and manifest visualization tool built for Singapore Airlines (SIA) operations. It fuses official SIA API data with AirLabs global telemetry to provide a unified "Flightradar24-style" experience, complete with aircraft imagery, live trails, and Changi Airport wayfinding.

🚀 Key Features
📡 Interactive Radar: Live global map showing all active SQ flights. Includes persistent zoom/center and "Live Trails" (flight paths) for selected aircraft.

🔍 Search Manifest: Deep-dive search by flight number and date. Pulls data directly from the Official SIA Gateway including terminal/gate assignments and real-time status.

🖼️ Telemetry Cards: Custom sidebar cards for active flights featuring altitude, groundspeed, and specific aircraft registration imagery (e.g., 9V-SMI, 9V-SKY).

🗺️ Wayfinding: Built-in interactive PDF viewer for the Singapore Changi Airport Transit Area navigation.

⚡ Performance Optimized: Implements Session-State Caching to prevent map reloading/flickering during user interaction.

🛠️ Setup Instructions
1. Requirements
Python 3.9+

Streamlit

Folium & Streamlit-Folium

2. Installation
Clone your repository and install the dependencies:

Bash
pip install streamlit requests folium streamlit-folium
3. API Keys Configuration
Create a folder named .streamlit in your root directory and add a secrets.toml file with your credentials:

Ini, TOML
# .streamlit/secrets.toml
SIA_STATUS_KEY = "YOUR_SIA_GATEWAY_API_KEY"
AIRLABS_API_KEY = "YOUR_AIRLABS_V9_API_KEY"
4. Required Assets
Ensure the following files are in your root folder for the UI to render correctly:

SQ loading screen.mp4 — Custom loading animation.

f5c530aa-d922-4920-9313-63a11c7f2921.png — Custom aircraft icon.

Singapore-Changi-Airport-Transit-Area-Wayfinding.pdf — The wayfinding guide.

Aircraft Images: 9V-SMI.jpg, 9V-SKY.jpg, 9V-MBO.jpg, 9V-SCK.avif, 9V-SWR.jpg.

🖥️ Running the App
Launch the dashboard locally using:

Bash
streamlit run app.py
📂 Project Structure
app.py: Core logic, UI components, and API fusion engine.

.streamlit/secrets.toml: Sensitive API credentials (ignored by git).

assets/: Folder for aircraft photos and icons.

🔧 Technical Details
API Fusion: The app tries the Official SIA Gateway first for ground-truth schedule data, falling back to AirLabs for live telemetry.

Map Persistence: Uses st.session_state to store map_center and map_zoom so the map doesn't reset when you click a plane.

Styling: Custom CSS injected via st.markdown to match the SIA Navy (#00266B) and Gold (#BD9B60) branding.
