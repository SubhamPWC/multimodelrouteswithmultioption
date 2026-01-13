import folium
from streamlit_folium import st_folium

# Per-mode colors
COLORS = {
    'road_rec': '#3b82f6',
    'road_alt': ['#22d3ee', '#a78bfa', '#10b981'],
    'rail_rec': '#ef4444',
    'rail_alt': ['#f59e0b', '#fb7185', '#f97316'],
    'flight_rec': '#8b5cf6',
    'flight_alt': ['#60a5fa', '#14b8a6', '#eab308'],
}


def _polyline(coords, color, weight, opacity):
    folium.PolyLine(locations=coords, color=color, weight=weight, opacity=opacity)


def draw_map(origin, dest, routes, rec_idx: int):
    center_lat = (origin[0] + dest[0]) / 2.0
    center_lon = (origin[1] + dest[1]) / 2.0
    m = folium.Map(location=[center_lat, center_lon], zoom_start=6, tiles='CartoDB dark_matter')
    folium.CircleMarker(location=list(origin), radius=6, color='#22d3ee', fill=True, fill_opacity=0.95, popup='From').add_to(m)
    folium.CircleMarker(location=list(dest), radius=6, color='#f59e0b', fill=True, fill_opacity=0.95, popup='To').add_to(m)

    for idx, r in enumerate(routes):
        mode = r.get('mode', 'road')
        rec = (idx == rec_idx)
        color = COLORS[f'{mode}_rec'] if rec else COLORS[f'{mode}_alt'][idx % len(COLORS[f'{mode}_alt'])]
        weight = 9 if rec else 6
        tooltip = f"{mode.title()} • {'Recommended' if rec else 'Alternative'} #{idx} • {r.get('distance_km',0):.1f} km, {r.get('duration_min',0):.1f} min"

        coords = r.get('coords_latlon', [])
        if coords:
            # Shadow for recommended
            if rec:
                folium.PolyLine(coords, color='#000000', weight=14, opacity=0.35).add_to(m)
            folium.PolyLine(coords, color=color, weight=weight, opacity=0.98, tooltip=tooltip).add_to(m)
        else:
            # If geometry is GeoJSON LineString (lon,lat), convert
            geom = r.get('geometry')
            if isinstance(geom, dict) and geom.get('type') == 'LineString':
                coords = [(lat, lon) for lon, lat in geom.get('coordinates', [])]
                if rec:
                    folium.PolyLine(coords, color='#000000', weight=14, opacity=0.35).add_to(m)
                folium.PolyLine(coords, color=color, weight=weight, opacity=0.98, tooltip=tooltip).add_to(m)

    folium.LayerControl().add_to(m)
    return st_folium(m, height=560)
