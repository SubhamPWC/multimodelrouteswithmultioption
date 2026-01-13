import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

from providers import fetch_road_routes, build_rail_routes, build_flight_routes
from optimization import road_cost_emissions, score_df
from map_utils import draw_map
from geometry_utils import haversine_km

st.set_page_config(page_title="Multi‑Modal (Road + Rail + Flight) Route Optimizer", layout="wide")

# CSS
from pathlib import Path
css_path = Path('assets/ui.css')
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

st.markdown('<div class="header-gradient">🧭 Multi‑Modal Route Optimizer</div>', unsafe_allow_html=True)
st.caption("Road, Rail, Flight — 3 alternatives per mode. Recommended path highlighted.")

# Sidebar inputs
st.sidebar.header("Configuration")
use_static = st.sidebar.checkbox("Use static points", value=True)
static_from = {
    "Kolkata (Esplanade)": (22.5667, 88.3667),
    "Howrah Maidan": (22.5892, 88.3475),
}
static_to = {
    "Salt Lake (Sector V)": (22.5792, 88.4317),
    "Kharagpur": (22.3400, 87.3250),
    "Bhubaneswar": (20.2961, 85.8250),
    "Delhi": (28.6315, 77.2167),
}

if use_static:
    origin_label = st.sidebar.selectbox("From", list(static_from.keys()), index=0)
    dest_label = st.sidebar.selectbox("To", list(static_to.keys()), index=0)
    origin = static_from[origin_label]
    dest = static_to[dest_label]
else:
    origin = (
        st.sidebar.number_input("From Lat", value=22.5667, format="%.6f"),
        st.sidebar.number_input("From Lon", value=88.3667, format="%.6f")
    )
    dest = (
        st.sidebar.number_input("To Lat", value=22.5792, format="%.6f"),
        st.sidebar.number_input("To Lon", value=88.4317, format="%.6f")
    )

st.sidebar.subheader("Road KPIs")
co2_g_per_km = st.sidebar.number_input("Road CO₂ g/km", value=120.0)
fuel_economy = st.sidebar.number_input("Fuel economy km/l", value=15.0)
fuel_price = st.sidebar.number_input("Fuel price ₹/l", value=110.0)

st.sidebar.subheader("Weights (Scoring)")
weights = {
    'distance_km': st.sidebar.slider("Distance", 0.0, 3.0, 1.0),
    'duration_min': st.sidebar.slider("Time", 0.0, 3.0, 1.0),
    'cost_inr': st.sidebar.slider("Cost", 0.0, 3.0, 1.0),
    'emissions_kg': st.sidebar.slider("CO₂", 0.0, 3.0, 1.0),
}

st.sidebar.subheader("Modes")
mode_select = st.sidebar.multiselect("Modes to include", ["road","rail","flight"], default=["road","rail","flight"])
avoid_tolls = st.sidebar.checkbox("Road: avoid tollways", value=False)
alt_count = st.sidebar.slider("Road alternatives (target)", 1, 5, 3)

ORS_API_KEY = st.secrets.get("ORS_API_KEY", "")

run = st.sidebar.button("🔎 Compute & Optimize")

for key in ['routes','df','scored_df','best_idx','origin','dest','message']:
    if key not in st.session_state:
        st.session_state[key] = None

if run:
    try:
        if origin == dest:
            st.session_state.message = "Origin and destination are identical. Choose different points."
        else:
            all_routes = []
            if 'road' in mode_select:
                road_routes = fetch_road_routes(origin, dest, alt_count, ORS_API_KEY, avoid_tolls)
                # compute KPIs
                for r in road_routes:
                    cost_inr, emissions_kg = road_cost_emissions(r.get('distance_km',0.0), fuel_economy, fuel_price, co2_g_per_km)
                    r['cost_inr'] = cost_inr
                    r['emissions_kg'] = emissions_kg
                    r['mode'] = 'road'
                all_routes.extend(road_routes)
            if 'rail' in mode_select:
                all_routes.extend(build_rail_routes(origin, dest))
            if 'flight' in mode_select:
                all_routes.extend(build_flight_routes(origin, dest))

            if not all_routes:
                st.session_state.message = "No routes found/built. Try different points or modes."
                st.session_state.routes = None
            else:
                # Build dataframe
                rows = []
                for i, r in enumerate(all_routes):
                    rows.append({
                        'Route': i,
                        'mode': r.get('mode','road'),
                        'distance_km': round(r.get('distance_km',0.0),2),
                        'duration_min': round(r.get('duration_min',0.0),2),
                        'cost_inr': r.get('cost_inr',0.0),
                        'emissions_kg': r.get('emissions_kg',0.0),
                        'roads_summary': r.get('roads_summary',''),
                    })
                df = pd.DataFrame(rows)
                scored_df, best_idx = score_df(df, weights)

                st.session_state.routes = all_routes
                st.session_state.df = df
                st.session_state.scored_df = scored_df
                st.session_state.best_idx = best_idx
                st.session_state.origin = origin
                st.session_state.dest = dest
                st.session_state.message = None
    except Exception as e:
        st.session_state.message = f"Unexpected error: {e}"

if st.session_state.message:
    st.error(st.session_state.message)

if st.session_state.routes and st.session_state.scored_df is not None:
    st.subheader("All Available Routes")
    df = st.session_state.scored_df.copy()
    df['Tag'] = np.where(df['tag']=='recommended', "<span class='badge recommended'>Recommended</span>", "<span class='badge alt'>Alt</span>")
    disp = df[['Route','mode','distance_km','duration_min','cost_inr','emissions_kg','roads_summary','score','Tag']]
    st.write("<div class='table-note'>Scores reflect your sidebar weights (MinMax). Lower is better.</div>", unsafe_allow_html=True)
    st.write(disp.to_html(escape=False, index=False), unsafe_allow_html=True)
    st.markdown("<hr class='hr-soft'>", unsafe_allow_html=True)

    st.subheader("Recommended Route")
    best_row = df.iloc[0]
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: st.markdown(f"<div class='card'><div>Distance (km)</div><div class='value'>{best_row['distance_km']}</div></div>", unsafe_allow_html=True)
    with c2: st.markdown(f"<div class='card'><div>Time (min)</div><div class='value'>{best_row['duration_min']}</div></div>", unsafe_allow_html=True)
    with c3: st.markdown(f"<div class='card'><div>Cost (₹)</div><div class='value'>{best_row['cost_inr']}</div></div>", unsafe_allow_html=True)
    with c4: st.markdown(f"<div class='card'><div>CO₂ (kg)</div><div class='value'>{best_row['emissions_kg']}</div></div>", unsafe_allow_html=True)
    with c5: st.markdown(f"<div class='card'><div>Score</div><div class='value'>{best_row['score']:.3f}</div></div>", unsafe_allow_html=True)

    st.markdown("<hr class='hr-soft'>", unsafe_allow_html=True)

    st.subheader("Route Visualization")
    rec_route_id = int(best_row['Route']) if st.session_state.best_idx != -1 else 0
    draw_map(st.session_state.origin, st.session_state.dest, st.session_state.routes, rec_route_id)

    st.markdown("<hr class='hr-soft'>", unsafe_allow_html=True)

    st.subheader("Turn‑by‑turn / Stops — Recommended")
    steps_df = pd.DataFrame(st.session_state.routes[rec_route_id].get('steps', []))
    if not steps_df.empty:
        steps_df = steps_df[["name","instruction","distance_m","duration_s"]]
        steps_df.rename(columns={"name":"Road/Stop","instruction":"Instruction","distance_m":"Segment (m)","duration_s":"Segment (s)"}, inplace=True)
    st.dataframe(steps_df, use_container_width=True)
