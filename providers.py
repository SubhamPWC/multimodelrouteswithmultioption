import requests
from typing import List, Dict, Any, Tuple
from geometry_utils import haversine_km
from optimization import rail_kpis, flight_kpis

# OSRM public demo server
OSRM_URL = 'https://router.project-osrm.org/route/v1/driving/{coords}?alternatives=true&overview=full&steps=true'

class ORSClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.url = 'https://api.openrouteservice.org/v2/directions/driving-car'

    def fetch(self, origin: Tuple[float,float], dest: Tuple[float,float], alt_count: int, avoid_tolls: bool=False):
        if not self.api_key:
            return {'error': 'Missing ORS_API_KEY'}
        headers = {'Authorization': self.api_key, 'Content-Type': 'application/json'}
        crow = haversine_km(origin, dest)
        use_alts = crow <= 100.0
        body = {
            'coordinates': [[origin[1], origin[0]],[dest[1], dest[0]]],
            'instructions': True,
            'preference': 'recommended' if use_alts else 'fastest'
        }
        if use_alts:
            body['alternative_routes'] = {'share_factor':0.6,'target_count':max(1,alt_count),'weight_factor':1.4}
        if avoid_tolls:
            body['options'] = {'avoid_features':['tollways']}
        try:
            resp = requests.post(self.url, json=body, headers=headers, timeout=60)
        except requests.RequestException as e:
            return {'error': f'ORS network error: {e}'}
        if resp.ok:
            return resp.json()
        if resp.status_code == 400 and use_alts:
            body['alternative_routes'] = None
            body['preference'] = 'fastest'
            try:
                resp2 = requests.post(self.url, json=body, headers=headers, timeout=60)
                if resp2.ok:
                    return resp2.json()
            except requests.RequestException as e:
                return {'error': f'ORS retry error: {e}'}
        try:
            msg = resp.json().get('error',{}).get('message') or resp.text
        except Exception:
            msg = resp.text
        return {'error': f'ORS HTTP {resp.status_code}: {msg}'}

    @staticmethod
    def parse(resp: Dict[str,Any], alt_target:int=4) -> List[Dict[str,Any]]:
        if not isinstance(resp, dict) or resp.get('error'):
            return []
        routes = []
        if 'features' in resp:
            for feat in resp.get('features', [])[:alt_target]:
                props = feat.get('properties', {})
                segs = props.get('segments', [])
                steps_all, road_names = [], []
                for seg in segs:
                    for s in seg.get('steps', []):
                        nm = s.get('name') or s.get('instruction')
                        if nm and nm != '-': road_names.append(nm)
                        steps_all.append({'name': s.get('name'), 'instruction': s.get('instruction'),
                                          'distance_m': s.get('distance',0), 'duration_s': s.get('duration',0)})
                seen, summary = set(), []
                for nm in road_names:
                    if nm not in seen:
                        summary.append(nm); seen.add(nm)
                    if len(summary) >= 10: break
                routes.append({
                    'mode':'road',
                    'distance_km': props.get('summary',{}).get('distance',0)/1000.0,
                    'duration_min': props.get('summary',{}).get('duration',0)/60.0,
                    'geometry': feat.get('geometry',{}),
                    'steps': steps_all,
                    'roads_summary': ', '.join(summary)
                })
        return routes

class OSRMClient:
    @staticmethod
    def fetch(origin: Tuple[float,float], dest: Tuple[float,float]) -> Dict[str,Any]:
        coords = f"{origin[1]},{origin[0]};{dest[1]},{dest[0]}"
        url = OSRM_URL.format(coords=coords)
        try:
            resp = requests.get(url, timeout=60)
            if resp.ok:
                return resp.json()
            return {'error': f'OSRM HTTP {resp.status_code}: {resp.text}'}
        except requests.RequestException as e:
            return {'error': f'OSRM network error: {e}'}

    @staticmethod
    def parse(resp: Dict[str,Any], alt_target:int=4) -> List[Dict[str,Any]]:
        if not isinstance(resp, dict) or resp.get('error'):
            return []
        routes = []
        for r in resp.get('routes', [])[:alt_target]:
            distance_km = r.get('distance',0)/1000.0
            duration_min = r.get('duration',0)/60.0
            coords, steps_all, road_names = [], [], []
            poly = r.get('geometry')
            if isinstance(poly, str):
                coords = OSRMClient._decode_polyline5(poly)
            for leg in r.get('legs', []):
                for s in leg.get('steps', []):
                    nm = s.get('name') or s.get('ref') or s.get('mode')
                    if nm and nm != '-': road_names.append(nm)
                    steps_all.append({'name': s.get('name'), 'instruction': s.get('maneuver',{}).get('type'),
                                      'distance_m': s.get('distance',0), 'duration_s': s.get('duration',0)})
            seen, summary = set(), []
            for nm in road_names:
                if nm not in seen:
                    summary.append(nm); seen.add(nm)
                if len(summary) >= 10: break
            routes.append({
                'mode':'road',
                'distance_km': distance_km,
                'duration_min': duration_min,
                'coords_latlon': coords,
                'steps': steps_all,
                'roads_summary': ', '.join(summary)
            })
        return routes

    @staticmethod
    def _decode_polyline5(polyline_str: str):
        coords = []
        index, lat, lng = 0, 0, 0
        while index < len(polyline_str):
            result, shift = 0, 0
            while True:
                b = ord(polyline_str[index]) - 63
                index += 1
                result |= (b & 0x1f) << shift
                shift += 5
                if b < 0x20:
                    break
            dlat = ~(result >> 1) if result & 1 else result >> 1
            lat += dlat
            result, shift = 0, 0
            while True:
                b = ord(polyline_str[index]) - 63
                index += 1
                result |= (b & 0x1f) << shift
                shift += 5
                if b < 0x20:
                    break
            dlng = ~(result >> 1) if result & 1 else result >> 1
            lng += dlng
            coords.append((lat / 1e5, lng / 1e5))
        return coords

# Rail & Flight hubs (India) — simplified
RAIL_HUBS = {
    'Howrah (HWH)': (22.5893, 88.3570),
    'Sealdah (SDAH)': (22.5697, 88.3736),
    'New Delhi (NDLS)': (28.6430, 77.2215),
    'Chennai Central (MAS)': (13.0823, 80.2750),
    'Mumbai CSMT (CSMT)': (18.9398, 72.8356),
    'Secunderabad (SC)': (17.4350, 78.5011),
}

AIR_HUBS = {
    'Kolkata CCU': (22.6547, 88.4467),
    'Delhi DEL': (28.5562, 77.1000),
    'Mumbai BOM': (19.0952, 72.8741),
    'Bengaluru BLR': (13.1992, 77.7063),
    'Chennai MAA': (12.9941, 80.1809),
    'Hyderabad HYD': (17.2400, 78.4294),
}


def _nearest_hubs(point: Tuple[float,float], hubs: Dict[str,Tuple[float,float]], topn=4):
    dlist = []
    for name, coord in hubs.items():
        d = haversine_km(point, coord)
        dlist.append((name, coord, d))
    dlist.sort(key=lambda x: x[2])
    return dlist[:topn]


def build_rail_routes(origin, dest, alt_target:int=4) -> List[Dict[str,Any]]:
    origin_near = _nearest_hubs(origin, RAIL_HUBS, topn=alt_target)
    dest_near = _nearest_hubs(dest, RAIL_HUBS, topn=alt_target)
    candidates = []
    for on in origin_near:
        for dn in dest_near:
            total = on[2] + dn[2]
            candidates.append((on[0], on[1], dn[0], dn[1], total))
    candidates.sort(key=lambda x: x[4])
    routes = []
    for i, (on_name, on_coord, dn_name, dn_coord, _) in enumerate(candidates[:alt_target]):
        coords = [origin, on_coord, dn_coord, dest]
        seg_d = haversine_km(origin, on_coord) + haversine_km(on_coord, dn_coord) + haversine_km(dn_coord, dest)
        duration_min, cost_inr, emissions_kg = rail_kpis(seg_d)
        routes.append({
            'mode':'rail',
            'distance_km': round(seg_d,2),
            'duration_min': duration_min,
            'cost_inr': round(cost_inr,2),
            'emissions_kg': emissions_kg,
            'stations': f"{on_name} → {dn_name}",
            'coords_latlon': coords,
            'steps': [
                {'name': on_name, 'instruction': 'Board train', 'distance_m': 0, 'duration_s': 0},
                {'name': dn_name, 'instruction': 'Alight train', 'distance_m': 0, 'duration_s': 0},
            ],
            'roads_summary': f"{on_name}, {dn_name}"
        })
    return routes


def build_flight_routes(origin, dest, alt_target:int=4) -> List[Dict[str,Any]]:
    origin_near = _nearest_hubs(origin, AIR_HUBS, topn=alt_target)
    dest_near = _nearest_hubs(dest, AIR_HUBS, topn=alt_target)
    candidates = []
    for on in origin_near:
        for dn in dest_near:
            total = on[2] + dn[2]
            candidates.append((on[0], on[1], dn[0], dn[1], total))
    candidates.sort(key=lambda x: x[4])
    routes = []
    for i, (on_name, on_coord, dn_name, dn_coord, _) in enumerate(candidates[:alt_target]):
        coords = [origin, on_coord, dn_coord, dest]
        seg_d = haversine_km(origin, on_coord) + haversine_km(on_coord, dn_coord) + haversine_km(dn_coord, dest)
        duration_min, cost_inr, emissions_kg = flight_kpis(seg_d)
        routes.append({
            'mode':'flight',
            'distance_km': round(seg_d,2),
            'duration_min': duration_min,
            'cost_inr': round(cost_inr,2),
            'emissions_kg': emissions_kg,
            'stations': f"{on_name} → {dn_name}",
            'coords_latlon': coords,
            'steps': [
                {'name': on_name, 'instruction': 'Board flight', 'distance_m': 0, 'duration_s': 0},
                {'name': dn_name, 'instruction': 'Alight flight', 'distance_m': 0, 'duration_s': 0},
            ],
            'roads_summary': f"{on_name}, {dn_name}"
        })
    return routes


def fetch_road_routes(origin, dest, alt_target:int, ors_api_key:str, avoid_tolls=False) -> List[Dict[str,Any]]:
    routes: List[Dict[str,Any]] = []
    if ors_api_key:
        ors = ORSClient(ors_api_key)
        r = ors.fetch(origin, dest, alt_target, avoid_tolls)
        routes.extend(ORSClient.parse(r, alt_target=alt_target))
    if len(routes) < alt_target:
        osrm = OSRMClient.fetch(origin, dest)
        routes.extend(OSRMClient.parse(osrm, alt_target=alt_target))
    return routes[:alt_target]
