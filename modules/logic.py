from __future__ import annotations

from datetime import datetime
from math import asin, cos, radians, sin, sqrt

import numpy as np
import pandas as pd


WALK_SPEED_KMH = 9
MOTO_SPEED_KMH = 45
CAR_URBAN_SPEED_KMH = 30
CAR_ROAD_SPEED_KMH = 100


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    return 2 * radius * asin(sqrt(a))


def parse_time(value: str) -> datetime:
    return datetime.combine(datetime.today(), datetime.strptime(value, "%H:%M").time())


def minutes_between(a: str, b: str) -> int:
    return abs(int((parse_time(a) - parse_time(b)).total_seconds() / 60))


def travel_minutes(distance_km: float, speed_kmh: float, minimum: int = 1) -> int:
    return max(minimum, int(round(distance_km / speed_kmh * 60)))


def access_mode_for_distance(distance_km: float) -> str:
    return "a pie" if distance_km <= 1 else "en moto compartida"


def car_distance_split(total_km: float) -> tuple[float, float]:
    urban_km = min(total_km, 4.0)
    road_km = max(total_km - urban_km, 0)
    return urban_km, road_km


def route_segment_estimates(
    row: pd.Series,
    parkings: dict[str, dict[str, object]],
    destination: tuple[float, float],
) -> dict[str, float | int | str]:
    access_km = float(row.get("pickup_access_km", 0.8))
    access_transport = access_mode_for_distance(access_km)
    access_speed = WALK_SPEED_KMH if access_transport == "a pie" else MOTO_SPEED_KMH
    access_minutes = travel_minutes(access_km, access_speed, 4 if access_transport == "a pie" else 2)

    car_total_km = float(row["distancia_km"])
    car_urban_km, car_road_km = car_distance_split(car_total_km)
    car_minutes = (
        travel_minutes(car_urban_km, CAR_URBAN_SPEED_KMH, 0)
        + travel_minutes(car_road_km, CAR_ROAD_SPEED_KMH, 0)
    )

    dest_lat, dest_lon = destination
    parking_data = parkings.get(row["parking"], {})
    parking_lat = float(parking_data.get("lat", dest_lat))
    parking_lon = float(parking_data.get("lon", dest_lon))
    last_mile_km = max(haversine_km(parking_lat, parking_lon, dest_lat, dest_lon) * 1.15, 0.3)
    last_mile_transport = "Moto compartida" if row["moto_destino"] else "A pie"
    last_mile_speed = MOTO_SPEED_KMH if row["moto_destino"] else WALK_SPEED_KMH
    last_mile_minutes = travel_minutes(last_mile_km, last_mile_speed, 2 if row["moto_destino"] else 4)

    return {
        "access_km": round(access_km, 1),
        "access_transport": access_transport,
        "access_minutes": access_minutes,
        "car_urban_km": round(car_urban_km, 1),
        "car_road_km": round(car_road_km, 1),
        "car_total_km": round(car_total_km, 1),
        "car_minutes": car_minutes,
        "last_mile_km": round(last_mile_km, 1),
        "last_mile_transport": last_mile_transport,
        "last_mile_minutes": last_mile_minutes,
        "total_km": round(access_km + car_total_km + last_mile_km, 1),
        "total_minutes": access_minutes + car_minutes + last_mile_minutes,
    }


def access_recommendation(distance_km: float, pickup: str, driver: str) -> tuple[str, str, int]:
    if distance_km <= 1:
        meters = int(distance_km * 1000)
        minutes = travel_minutes(distance_km, WALK_SPEED_KMH, 4)
        return "A pie", f"Camina {meters} m hasta el punto de recogida en {pickup}.", minutes
    minutes = travel_minutes(distance_km, MOTO_SPEED_KMH, 2)
    return (
        "Moto compartida",
        f"Reserva una moto compartida hasta {pickup} y unete al coche de {driver}.",
        minutes,
    )


def route_score(
    row: pd.Series,
    municipalities: dict[str, tuple[float, float]],
    desired_arrival: str,
    user_origin: str,
    passengers: int,
    preference: str,
) -> tuple[int, str, float]:
    user_lat, user_lon = municipalities[user_origin]
    pickup_km = haversine_km(user_lat, user_lon, row["lat"], row["lon"])
    proximity_score = max(0, 100 - pickup_km * 18)
    time_score = max(0, 100 - minutes_between(row["hora_llegada"], desired_arrival) * 2.6)
    seats_score = 100 if row["plazas_disponibles"] >= passengers else 25
    rating_score = row["valoracion"] / 5 * 100
    occupancy_score = min(row["ocupacion_actual"] / 4, 1) * 100
    hot_score = 100 if row["ruta_caliente"] else 68
    multimodal_score = 100 if row["moto_destino"] and row["parking"] else 72

    preference_bonus = 0
    if preference == "Menor precio":
        preference_bonus = max(0, 24 - row["precio"] * 3.2)
    elif preference == "Menor desvío":
        preference_bonus = max(0, 24 - pickup_km * 6)
    elif preference == "Mejor valoración":
        preference_bonus = (row["valoracion"] - 4) * 13
    elif preference == "Vehículo eléctrico/híbrido" and row["tipo_coche"] in ["eléctrico", "híbrido"]:
        preference_bonus = 18

    score = (
        proximity_score * 0.22
        + time_score * 0.23
        + seats_score * 0.16
        + rating_score * 0.12
        + occupancy_score * 0.09
        + hot_score * 0.09
        + multimodal_score * 0.09
        + preference_bonus
    )
    score = int(np.clip(round(score), 0, 100))
    mode, _, minutes = access_recommendation(pickup_km, row["origen"], row["conductor"])
    reason = (
        f"Llegada compatible, {pickup_km:.1f} km hasta recogida, acceso en {mode.lower()} "
        f"({minutes} min) y parking {row['parking']}."
    )
    return score, reason, pickup_km


def calculate_matches(
    trips: pd.DataFrame,
    municipalities: dict[str, tuple[float, float]],
    user_origin: str,
    desired_arrival: str,
    passengers: int,
    preference: str,
) -> pd.DataFrame:
    rows = []
    for _, row in trips.iterrows():
        score, reason, pickup_km = route_score(row, municipalities, desired_arrival, user_origin, passengers, preference)
        if row["plazas_disponibles"] < passengers:
            score = max(score - 38, 0)
        rows.append({**row.to_dict(), "score": score, "reason": reason, "pickup_km": pickup_km})
    return pd.DataFrame(rows).sort_values(["score", "valoracion"], ascending=False)


def impact_metrics(trips: pd.DataFrame) -> dict[str, float]:
    vehicles_used = len(trips)
    users_transported = int(trips["ocupacion_actual"].sum())
    vehicles_avoided = max(users_transported - vehicles_used, 0)
    avg_occupancy = users_transported / vehicles_used
    co2 = float(trips["co2_evitado"].sum())
    matched_requests = int(trips["solicitudes_match"].sum() * 0.69)
    total_requests = int(trips["solicitudes_match"].sum())
    return {
        "active_trips": vehicles_used,
        "users_transported": users_transported,
        "vehicles_avoided": vehicles_avoided,
        "avg_occupancy": avg_occupancy,
        "co2": co2,
        "matched_requests": matched_requests,
        "total_requests": total_requests,
        "matching_rate": matched_requests / total_requests * 100,
    }
