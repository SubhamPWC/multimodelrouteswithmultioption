# Multi‑Modal Route Optimizer (Road + Rail + Flight) — Streamlit

A dark, dashboard‑style app that:
- Shows **Road**, **Rail**, and **Flight** modes.
- **Always returns up to 3 routes** per mode, even for long distances:
  - Road: ORS (driving‑car) with OSRM fallback to get 3 alternatives.
  - Rail: Synthesized via major **Indian rail hubs** (Howrah, Sealdah, New Delhi, Chennai, Mumbai, Secunderabad).
  - Flight: Synthesized via major **Indian airports** (CCU, DEL, BOM, BLR, MAA, HYD).
- Displays **road/street names** (turn‑by‑turn) for **Road** mode.
- Displays **station/airport names** for **Rail/Flight** modes.
- Highlights the **recommended route** on a **dark map** with a glow; alternatives use distinct colors.
- Provides a table with **Distance (km), Time (min), Cost (₹), CO₂ (kg), Mode, roads_summary/stations, Score, Tag**.
- Summary cards + simple charts.

> **Note:** ORS often limits alternatives for long trips; we fetch 3 road alternatives using **OSRM** fallback to satisfy “3 routes” even when long. Rail/Flight are synthesized for planning visuals only (no real schedules).

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Community Cloud
- Main file: `app.py`
- Secrets →
```toml
ORS_API_KEY = "YOUR_ORS_API_KEY"  # optional, road mode still works via OSRM fallback
```
