from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import streamlit as st

from modules.logic import access_mode_for_distance, haversine_km, travel_minutes, WALK_SPEED_KMH, MOTO_SPEED_KMH


MUNICIPALITIES = {
    "Valencia": (39.4699, -0.3763),
    "Torrent": (39.4370, -0.4655),
    "Catarroja": (39.4033, -0.4034),
    "Albal": (39.3978, -0.4157),
    "Silla": (39.3625, -0.4113),
    "Picassent": (39.3635, -0.4595),
    "Benetússer": (39.4228, -0.3969),
    "Paiporta": (39.4281, -0.4170),
    "Alcàsser": (39.3675, -0.4440),
    "Sueca": (39.2026, -0.3111),
    "Cullera": (39.1667, -0.2536),
    "Gandía": (38.9680, -0.1800),
    "Xàtiva": (38.9904, -0.5189),
    "Almussafes": (39.2915, -0.4146),
}


DESTINATION_ZONES = [
    "Ford Almussafes - Puerta Norte",
    "Parque de Proveedores - Zona Este",
    "Área Industrial Sur",
    "Centro Logístico Almussafes",
    "Acceso CV-42",
]


SHIFTS = {
    "Turno mañana": {"start": "06:00", "end": "08:00", "target": "07:40"},
    "Turno central": {"start": "07:30", "end": "09:00", "target": "08:25"},
    "Turno tarde": {"start": "13:00", "end": "15:00", "target": "14:05"},
}


PARKINGS = {
    "Parking Almussafes Norte": {
        "lat": 39.3020,
        "lon": -0.4140,
        "plazas_totales": 180,
        "plazas_libres": 42,
        "reservas_30m": 19,
        "plazas_accesibles": 8,
        "accesibles_libres": 3,
        "cargadores": 12,
        "cargadores_libres": 4,
        "ocupacion": 77,
        "descuento": "25%",
        "distancia": "1,2 km",
        "motos": 14,
        "estado": "Alta demanda",
        "accesible": True,
        "ultima_actualizacion": "07:18",
    },
    "Parking Área Industrial Sur": {
        "lat": 39.2815,
        "lon": -0.4185,
        "plazas_totales": 140,
        "plazas_libres": 58,
        "reservas_30m": 12,
        "plazas_accesibles": 6,
        "accesibles_libres": 4,
        "cargadores": 8,
        "cargadores_libres": 5,
        "ocupacion": 59,
        "descuento": "20%",
        "distancia": "850 m",
        "motos": 8,
        "estado": "Operativo",
        "accesible": True,
        "ultima_actualizacion": "07:16",
    },
    "Parking Disuasorio Silla": {
        "lat": 39.3650,
        "lon": -0.4148,
        "plazas_totales": 95,
        "plazas_libres": 63,
        "reservas_30m": 7,
        "plazas_accesibles": 4,
        "accesibles_libres": 4,
        "cargadores": 4,
        "cargadores_libres": 2,
        "ocupacion": 34,
        "descuento": "15%",
        "distancia": "8,5 km",
        "motos": 6,
        "estado": "Alta disponibilidad",
        "accesible": True,
        "ultima_actualizacion": "07:15",
    },
    "Parking Intermodal Catarroja": {
        "lat": 39.4050,
        "lon": -0.4055,
        "plazas_totales": 75,
        "plazas_libres": 14,
        "reservas_30m": 11,
        "plazas_accesibles": 2,
        "accesibles_libres": 0,
        "cargadores": 2,
        "cargadores_libres": 0,
        "ocupacion": 81,
        "descuento": "10%",
        "distancia": "13,1 km",
        "motos": 3,
        "estado": "Baja disponibilidad",
        "accesible": False,
        "ultima_actualizacion": "07:17",
    },
}


MOTO_HUBS = {
    "Moto Hub Almussafes": {
        "lat": 39.2918,
        "lon": -0.4120,
        "motos_totales": 24,
        "motos_disponibles": 17,
        "reservadas": 4,
        "mantenimiento": 3,
        "bateria": 82,
        "zona": "Área industrial central",
        "parking": "Parking Almussafes Norte",
        "matricula": "4821 KLM",
        "plaza_parking": "43/180",
        "sla_reposicion": "11 min",
    },
    "Moto Hub Parking Norte": {
        "lat": 39.3024,
        "lon": -0.4144,
        "motos_totales": 18,
        "motos_disponibles": 14,
        "reservadas": 2,
        "mantenimiento": 2,
        "bateria": 76,
        "zona": "Parking Almussafes Norte",
        "parking": "Parking Almussafes Norte",
        "matricula": "7394 MNP",
        "plaza_parking": "58/180",
        "sla_reposicion": "14 min",
    },
    "Moto Hub Área Industrial Sur": {
        "lat": 39.2808,
        "lon": -0.4190,
        "motos_totales": 14,
        "motos_disponibles": 8,
        "reservadas": 3,
        "mantenimiento": 3,
        "bateria": 69,
        "zona": "Área Industrial Sur",
        "parking": "Parking Área Industrial Sur",
        "matricula": "6158 RST",
        "plaza_parking": "27/140",
        "sla_reposicion": "18 min",
    },
    "Moto Hub Silla": {
        "lat": 39.3658,
        "lon": -0.4142,
        "motos_totales": 10,
        "motos_disponibles": 6,
        "reservadas": 1,
        "mantenimiento": 3,
        "bateria": 73,
        "zona": "Intermodal Silla",
        "parking": "Parking Disuasorio Silla",
        "matricula": "9042 BCD",
        "plaza_parking": "16/95",
        "sla_reposicion": "20 min",
    },
}


MOTO_RESERVATION_DETAILS = {
    "Moto Hub Almussafes": {
        "parking": "Parking Almussafes Norte",
        "matricula": "4821 KLM",
        "plaza_parking": "43/180",
    },
    "Moto Hub Parking Norte": {
        "parking": "Parking Almussafes Norte",
        "matricula": "7394 MNP",
        "plaza_parking": "58/180",
    },
    "Moto Hub Área Industrial Sur": {
        "parking": "Parking Área Industrial Sur",
        "matricula": "6158 RST",
        "plaza_parking": "27/140",
    },
    "Moto Hub Silla": {
        "parking": "Parking Disuasorio Silla",
        "matricula": "9042 BCD",
        "plaza_parking": "16/95",
    },
}


def _build_moto_hubs() -> dict[str, dict[str, object]]:
    return {
        hub: {**info, **MOTO_RESERVATION_DETAILS.get(hub, {})}
        for hub, info in MOTO_HUBS.items()
    }


LOCKERS = [
    "Locker Valencia Sur",
    "Locker Silla Intermodal",
    "Locker Catarroja",
    "Locker Almussafes Industrial",
    "Locker Torrent Avinguda",
    "Locker Xàtiva Estación",
    "Locker Gandía Estación",
    "Locker Sueca Centro",
]


@dataclass(frozen=True)
class AppData:
    municipalities: dict[str, tuple[float, float]]
    trips: pd.DataFrame
    passengers: pd.DataFrame
    parkings: dict[str, dict[str, object]]
    moto_hubs: dict[str, dict[str, object]]
    lockers: list[str]
    daily: pd.DataFrame
    demand: pd.DataFrame
    locker_activity: pd.DataFrame


def _build_trips() -> pd.DataFrame:
    drivers = [
        "Marta G.",
        "Carlos R.",
        "Amparo S.",
        "Javier M.",
        "Laura P.",
        "Vicent F.",
        "Ana B.",
        "Sergio T.",
        "Noelia C.",
        "Pau L.",
        "Rocío N.",
        "Héctor V.",
        "Elena V.",
        "Damián Q.",
        "Marina J.",
        "Salva P.",
    ]
    origins = [x for x in MUNICIPALITIES if x != "Almussafes"]
    departure_by_shift = {
        "Turno mañana": ["06:05", "06:18", "06:28", "06:35", "06:42", "06:48", "06:55", "07:00", "07:06", "07:12", "07:18", "07:24"],
        "Turno central": ["07:35", "07:44", "07:52", "08:00", "08:08", "08:16", "08:24"],
        "Turno tarde": ["13:05", "13:16", "13:28", "13:42", "13:55", "14:06"],
    }
    arrival_by_shift = {
        "Turno mañana": ["07:22", "07:28", "07:32", "07:35", "07:38", "07:40", "07:42", "07:45", "07:48"],
        "Turno central": ["08:14", "08:20", "08:26", "08:32", "08:38", "08:44"],
        "Turno tarde": ["13:48", "13:56", "14:05", "14:12", "14:20", "14:28"],
    }
    vehicles = ["eléctrico", "híbrido", "diésel", "gasolina"]
    parking_names = list(PARKINGS.keys())
    dest_lat, dest_lon = MUNICIPALITIES["Almussafes"]
    rows = []
    idx = 1

    for origin_index, origin in enumerate(origins):
        base_frequency = 4 if origin in ["Valencia", "Torrent", "Silla", "Catarroja"] else 3
        for offset in range(base_frequency):
            shift = list(SHIFTS.keys())[(origin_index + offset) % len(SHIFTS)]
            lat, lon = MUNICIPALITIES[origin]
            driver = drivers[(origin_index + offset * 4) % len(drivers)]
            vehicle = vehicles[(origin_index + offset) % len(vehicles)]
            capacity = 5 if vehicle in ["eléctrico", "híbrido"] and offset % 3 == 0 else 4 if vehicle != "gasolina" else 3
            reserved = int(np.clip((origin_index + offset * 2) % capacity, 0, capacity - 1))
            pending = int((origin_index + offset) % 3)
            occupancy = int(np.clip(reserved + 1, 1, capacity))
            seats = max(capacity - occupancy, 0)
            distance = haversine_km(lat, lon, dest_lat, dest_lon) * (1.13 + 0.02 * offset)
            price = 1.15 + distance * 0.087 - (0.42 if vehicle == "eléctrico" else 0.25 if vehicle == "híbrido" else 0)
            parking = parking_names[(origin_index + offset) % len(parking_names)]
            hot = origin in ["Valencia", "Torrent", "Silla", "Catarroja", "Benetússer"] or (offset == 0 and shift == "Turno mañana")
            moto = parking in ["Parking Almussafes Norte", "Parking Área Industrial Sur"] or origin in ["Silla", "Torrent", "Catarroja"]
            accessible = vehicle in ["eléctrico", "híbrido"] or parking != "Parking Intermodal Catarroja"
            package = offset != 1 or origin in ["Valencia", "Silla", "Torrent", "Gandía"]
            co2_per_passenger = 0.12 * distance
            avoided = co2_per_passenger * max(occupancy - 1, 0)
            rating = round(4.35 + ((origin_index + offset * 2) % 7) * 0.08, 1)
            pickup_name = f"{origin} · punto {['estación', 'ayuntamiento', 'avenida principal', 'parking intermodal'][offset % 4]}"
            pickup_access_km = [0.6, 1.4, 2.6, 4.2][offset % 4]
            pickup_access_mode = access_mode_for_distance(pickup_access_km)
            pickup_access_speed = WALK_SPEED_KMH if pickup_access_mode == "a pie" else MOTO_SPEED_KMH
            pickup_access_minutes = travel_minutes(pickup_access_km, pickup_access_speed, 4 if pickup_access_mode == "a pie" else 2)
            confirmation = ["Confirmación automática", "Requiere aprobación", "Solo empresa verificada"][(origin_index + offset) % 3]
            pickup_access_mode = access_mode_for_distance(pickup_access_km)
            rows.append(
                {
                    "id": idx,
                    "conductor": driver,
                    "origen": origin,
                    "destino": "Área industrial de Almussafes",
                    "zona_destino": DESTINATION_ZONES[(origin_index + offset) % len(DESTINATION_ZONES)],
                    "turno": shift,
                    "hora_salida": departure_by_shift[shift][(origin_index + offset) % len(departure_by_shift[shift])],
                    "hora_llegada": arrival_by_shift[shift][(origin_index + offset) % len(arrival_by_shift[shift])],
                    "punto_recogida": pickup_name,
                    "pickup_access_km": pickup_access_km,
                    "pickup_access_mode": pickup_access_mode,
                    "pickup_access_minutes": pickup_access_minutes,
                    "plazas_disponibles": int(seats),
                    "plazas_reservadas": int(reserved),
                    "solicitudes_pendientes": int(pending),
                    "ocupacion_actual": int(occupancy),
                    "capacidad": int(capacity),
                    "precio": round(max(price, 1.35), 2),
                    "distancia_km": round(distance, 1),
                    "co2_pasajero": round(co2_per_passenger, 1),
                    "co2_evitado": round(avoided, 1),
                    "parking": parking,
                    "moto_destino": moto,
                    "valoracion": rating,
                    "tipo_coche": vehicle,
                    "codigo_ruta": f"TRB-R-{idx:05d}",
                    "codigo_reserva": f"TRB-B-{20260400 + idx}",
                    "matricula_vehiculo": f"{2400 + idx:04d} {['LKM', 'MNP', 'RST', 'BCD'][idx % 4]}",
                    "empresa_origen": ["Ford España", "Lear Corporation", "Faurecia", "DHL Supply Chain"][idx % 4],
                    "estado_ruta": ["Abierta", "Preconfirmada", "Completa"][idx % 3],
                    "validacion_empresa": "Verificada",
                    "ultima_actualizacion": f"07:{(12 + idx) % 60:02d}",
                    "ruta_caliente": hot,
                    "accesible": accessible,
                    "acepta_paquetes": package,
                    "recurrente": "L-V" if offset % 2 == 0 else "Martes y jueves",
                    "confirmacion": confirmation,
                    "puntualidad_pct": int(88 + ((origin_index + offset) % 10)),
                    "solicitudes_match": int(10 + (origin_index % 5) * 4 + offset * 3),
                    "cancelaciones": int((origin_index + offset) % 3),
                    "lat": lat,
                    "lon": lon,
                    "dest_lat": dest_lat,
                    "dest_lon": dest_lon,
                }
            )
            idx += 1

    return pd.DataFrame(rows)


def _build_passengers() -> pd.DataFrame:
    names = [
        "Lucía P.",
        "Andrés M.",
        "Belén R.",
        "Marc S.",
        "Irene F.",
        "Pilar C.",
        "Dani V.",
        "Teresa A.",
        "Nerea B.",
        "Ferran G.",
        "Mónica L.",
        "Raúl S.",
        "Clara N.",
        "Iván T.",
    ]
    origins = ["Valencia", "Torrent", "Silla", "Catarroja", "Albal", "Gandía", "Xàtiva", "Paiporta", "Benetússer", "Sueca", "Picassent", "Cullera", "Alcàsser", "Valencia"]
    preferences = ["Menor precio", "Menor desvío", "Mejor valoración", "Vehículo eléctrico/híbrido"]
    needs = ["Sin necesidades especiales", "Movilidad reducida", "Alerta visual", "Transcripción del chat"]
    return pd.DataFrame(
        {
            "pasajero": names,
            "origen": origins,
            "turno": ["Turno mañana", "Turno mañana", "Turno central", "Turno mañana", "Turno tarde", "Turno mañana", "Turno mañana", "Turno central", "Turno mañana", "Turno tarde", "Turno mañana", "Turno mañana", "Turno central", "Turno mañana"],
            "zona_destino": [DESTINATION_ZONES[i % len(DESTINATION_ZONES)] for i in range(len(names))],
            "llegada_deseada": ["07:40", "07:35", "08:25", "07:38", "14:05", "07:50", "07:35", "08:30", "07:42", "14:10", "07:36", "07:45", "08:28", "07:32"],
            "preferencia": [preferences[i % len(preferences)] for i in range(len(names))],
            "necesidad": [needs[i % len(needs)] for i in range(len(names))],
            "estado": ["Match propuesto", "Confirmado", "Pendiente", "Confirmado", "Match propuesto", "Sin oferta directa", "Confirmado", "Pendiente", "Confirmado", "Match propuesto", "Pendiente", "Sin oferta directa", "Confirmado", "Match propuesto"],
            "radio_pickup_km": [1.0, 1.5, 2.0, 0.8, 1.2, 3.5, 2.5, 1.0, 1.5, 2.0, 1.2, 2.8, 1.4, 0.9],
        }
    )


def _build_daily() -> pd.DataFrame:
    rng = np.random.default_rng(24)
    days = pd.date_range(end=pd.Timestamp.today().normalize(), periods=28)
    trend = np.linspace(46, 118, len(days))
    requests = trend * 1.62 + rng.normal(0, 8, len(days))
    matched = requests * np.linspace(0.52, 0.76, len(days)) + rng.normal(0, 4, len(days))
    return pd.DataFrame(
        {
            "fecha": days,
            "viajes": np.maximum(30, trend + rng.normal(0, 5, len(days))).round().astype(int),
            "solicitudes": np.maximum(55, requests).round().astype(int),
            "matches": np.maximum(35, matched).round().astype(int),
            "motos": np.maximum(8, trend * 0.38 + rng.normal(0, 4, len(days))).round().astype(int),
            "paquetes": np.maximum(2, trend * 0.16 + rng.normal(0, 2, len(days))).round().astype(int),
        }
    )


def _build_demand() -> pd.DataFrame:
    rows = []
    base = {
        "Torrent": (54, 31),
        "Valencia": (48, 34),
        "Gandía": (29, 10),
        "Xàtiva": (27, 12),
        "Cullera": (21, 11),
        "Sueca": (19, 13),
        "Picassent": (18, 14),
        "Paiporta": (16, 13),
        "Silla": (42, 35),
        "Catarroja": (39, 30),
    }
    shifts = ["Turno mañana", "Turno central", "Turno tarde"]
    for index, (city, (requests, supply)) in enumerate(base.items()):
        for shift_index, shift in enumerate(shifts):
            factor = [1.0, 0.42, 0.35][shift_index]
            rows.append(
                {
                    "Municipio": city,
                    "Turno": shift,
                    "Solicitudes": int(round(requests * factor)),
                    "Oferta": int(round(supply * factor * (0.95 if shift_index == 0 else 0.78))),
                    "Franja crítica": ["06:45-07:30", "08:00-08:45", "13:35-14:15"][shift_index],
                    "Prioridad": ["Alta", "Media", "Media"][shift_index] if requests - supply > 9 else "Media",
                }
            )
    return pd.DataFrame(rows)


def _build_locker_activity() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Locker": LOCKERS,
            "Capacidad": [42, 36, 28, 58, 30, 24, 26, 22],
            "Huecos libres": [17, 12, 8, 19, 15, 11, 9, 10],
            "Paquetes entrantes": [12, 9, 7, 18, 5, 4, 6, 3],
            "Paquetes salientes": [6, 8, 5, 11, 4, 3, 5, 2],
            "SLA recogida": ["4h 20m", "3h 55m", "5h 10m", "2h 40m", "4h 35m", "6h 15m", "5h 50m", "6h 30m"],
            "Estado": ["Operativo", "Operativo", "Operativo", "Alta demanda", "Operativo", "Baja demanda", "Operativo", "Baja demanda"],
            "Verificación": ["QR + PIN", "QR + PIN", "QR + PIN", "QR + PIN + foto", "QR + PIN", "QR + PIN", "QR + PIN", "QR + PIN"],
        }
    )


@st.cache_data
def load_app_data() -> AppData:
    return AppData(
        municipalities=MUNICIPALITIES,
        trips=_build_trips(),
        passengers=_build_passengers(),
        parkings=PARKINGS,
        moto_hubs=_build_moto_hubs(),
        lockers=LOCKERS,
        daily=_build_daily(),
        demand=_build_demand(),
        locker_activity=_build_locker_activity(),
    )
