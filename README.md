# ✈️ KrisTracker Executive | SIA Fleet Operations Portal

**KrisTracker** is a high-performance flight operations dashboard designed for Singapore Airlines fleet monitoring. Built with Python and Streamlit, it integrates real-time global telemetry with official SIA UAT API services to provide a comprehensive "Command Center" experience.

---

## 🚀 Key Features

### 📡 Global Fleet Radar
* **Real-time Telemetry:** Tracks SIA/SQ aircraft globally via the OpenSky Network.
* **Aviation Precision:** Displays altitude in feet ($ft$), ground speed in knots ($kts$), and real-time **Mach Number** calculations.
* **Interactive Mapping:** Built with Folium and CartoDB Dark Matter for a professional, low-light operations room aesthetic.

### 🔎 Official Flight Status (SIA UAT)
* **Visual Boarding Cards:** Custom-rendered UI components for flight legs, departing/arriving terminals, and real-time status badges.
* **Search Flexibility:** Lookup by **Flight Number** (e.g., SQ317) or **Route** (e.g., SIN to LHR).
* **Mashery-Optimized Throttling:** Built-in QPS (Queries Per Second) management to prevent `403 Developer Over Qps` errors common in trial API keys.

### 🔒 Enterprise Security & UI
* **Supabase Auth:** Secure login gate integrated with Supabase GoTrue.
* **Executive Branding:** Custom CSS injection featuring the official SIA Navy (`#00266B`) and Gold (`#BD9B60`) color palette.
* **Debug Mode:** A dedicated "OP-CENTER" toggle for real-time API heartbeat and raw response monitoring.

---

## 🛠 Tech Stack

| Component | Technology |
| :--- | :--- |
| **Frontend** | [Streamlit](https://streamlit.io/) |
| **Mapping** | [Folium](https://python-visualization.github.io/folium/) |
| **Database/Auth** | [Supabase](https://supabase.com/) |
| **Flight Telemetry** | [OpenSky Network API](https://opensky-network.org/) |
| **Flight Status** | [SIA Developer Portal (UAT)](https://developer.singaporeair.com/) |

---

## ⚙️ Setup & Installation

1.  **Clone the Repository:**
    ```bash
    git clone [https://github.com/your-username/kristracker-executive.git](https://github.com/your-username/kristracker-executive.git)
    cd kristracker-executive
    ```

2.  **Install Dependencies:**
    ```bash
    pip install streamlit requests folium streamlit-folium pandas supabase
    ```

3.  **Configure Secrets:**
    Create a `.streamlit/secrets.toml` file with the following keys:
    ```toml
    SUPABASE_URL = "your_supabase_url"
    SUPABASE_KEY = "your_supabase_anon_key"
    SIA_STATUS_KEY = "your_sia_api_key"
    OPENSKY_CLIENT_ID = "your_username"
    OPENSKY_CLIENT_SECRET = "your_password"
    ```

4.  **Run the App:**
    ```bash
    streamlit run app.py
    ```

---

## 📡 API Implementation Details

The application uses a custom-built throttled request handler to interface with the SIA API Gateway:

$$ \text{Request Delay} = \max(1.5s, \text{Process Time}) $$

This ensures that the `x-csl-client-uuid` and `api_key` headers remain compliant with Sandbox rate limits while maintaining a responsive user interface.

---

## ⚖️ Disclaimer
This project is an independent tool developed for tracking purposes and is not officially affiliated with Singapore Airlines.
