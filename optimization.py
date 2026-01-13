import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

# KPI calculators

def road_cost_emissions(distance_km: float, fuel_economy_kmpl: float, fuel_price_inr: float, co2_g_per_km: float):
    litres = max(distance_km, 0.0) / max(fuel_economy_kmpl, 0.0001)
    cost_inr = litres * fuel_price_inr
    emissions_kg = (co2_g_per_km * max(distance_km, 0.0)) / 1000.0
    return round(cost_inr, 2), round(emissions_kg, 3)

# Simple rail/flight models (tunable)
RAIL_SPEED_KMPH = 70.0
RAIL_COST_PER_KM = 0.8   # ₹/km
RAIL_CO2_G_PER_KM = 30.0

FLIGHT_SPEED_KMPH = 650.0
FLIGHT_COST_PER_KM = 6.0  # ₹/km approx
FLIGHT_CO2_G_PER_KM = 120.0


def rail_kpis(distance_km: float):
    duration_min = (max(distance_km, 0.0) / RAIL_SPEED_KMPH) * 60.0
    cost_inr = max(distance_km, 0.0) * RAIL_COST_PER_KM
    emissions_kg = (RAIL_CO2_G_PER_KM * max(distance_km, 0.0)) / 1000.0
    return round(duration_min, 2), round(cost_inr, 2), round(emissions_kg, 3)


def flight_kpis(distance_km: float):
    duration_min = (max(distance_km, 0.0) / FLIGHT_SPEED_KMPH) * 60.0
    cost_inr = max(distance_km, 0.0) * FLIGHT_COST_PER_KM
    emissions_kg = (FLIGHT_CO2_G_PER_KM * max(distance_km, 0.0)) / 1000.0
    return round(duration_min, 2), round(cost_inr, 2), round(emissions_kg, 3)


def score_df(df: pd.DataFrame, weights: dict):
    if df.empty:
        df['score'] = []
        return df, -1
    cols = ['distance_km', 'duration_min', 'cost_inr', 'emissions_kg']
    scaler = MinMaxScaler()
    norm = scaler.fit_transform(df[cols])
    w = np.array([weights.get(c, 1.0) for c in cols])
    scores = (norm @ w.reshape(-1,1)).flatten()
    df['score'] = scores
    best_idx = int(np.argmin(scores))
    df['tag'] = ''
    df.loc[df.index[best_idx], 'tag'] = 'recommended'
    return df.sort_values(by='score').reset_index(drop=True), best_idx
