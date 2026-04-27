from __future__ import annotations


POSTCODE = "46007"
DIAS_MES = 30
HUB = {
    "nombre": "Microhub Estacion Joaquin Sorolla - Parking",
    "lat": 39.45915,
    "lon": -0.38145,
}

FALLBACK_BBOX = {
    "south": 39.455,
    "west": -0.394,
    "north": 39.4715,
    "east": -0.363,
}

CARTOCIUDAD_ADDRESS_URL = "https://api-features.idee.es/collections/address/items"
CARTOCIUDAD_WMS_URL = "https://www.cartociudad.es/wms-inspire/direcciones-ccpp"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def config_default() -> dict:
    return {
        "demanda_min": 400,
        "demanda_max": 420,
        "ratio_urgente": 0.20,
        "ratio_sobre": 0.15,
        "ratio_pm": 0.70,
        "ratio_xl": 0.15,
        "prob_fallo_1": 0.03,
        "prob_reintento_urgente": 0.50,
        "score_digitalizacion": 100.0,
        "objetivo_gls": 95.0,
        "alquiler_m2": 16.0,
        "m2_hub": 70,
        "capacidad_hub": 3500,
        "coste_hora": 12.05,
        "coste_fijo_hub": 250.0,
        "coste_carga": 0.05,
        "semilla": 42,
        "modo_optimizacion": "rapido",
        "modo_productividad": "ruta_distancia",
        "tiempo_entrega_min": 1.0,
        "tiempo_entrega_furgoneta_min": 2.0,
        "vista_mapa": "claro",
        "max_vehiculos_tipo": 8,
        "usar_traspaso_furgoneta": True,
        "vehiculos": vehiculos_default(),
    }


def vehiculos_default() -> dict:
    return {
        "bicicleta_cargo": {
            "nombre": "Bicicleta cargo",
            "icono": "bicycle",
            "color": "#2563eb",
            "alquiler_mes": 180.0,
            "energia_100km": 0.15,
            "productividad_min": 15,
            "productividad_max": 18,
            "velocidad_kmh": 13.0,
            "cap_sobre": 35,
            "cap_pm": 28,
            "cap_xl": 0,
            "cargas_dia": 2,
            "modo": "bike",
            "preferencia": 3,
        },
        "triciclo": {
            "nombre": "Triciclo electrico",
            "icono": "truck",
            "color": "#0891b2",
            "alquiler_mes": 320.0,
            "energia_100km": 0.25,
            "productividad_min": 15,
            "productividad_max": 18,
            "velocidad_kmh": 11.0,
            "cap_sobre": 45,
            "cap_pm": 35,
            "cap_xl": 0,
            "cargas_dia": 2,
            "modo": "bike",
            "preferencia": 3,
        },
        "furgoneta": {
            "nombre": "Furgoneta electrica",
            "icono": "truck",
            "color": "#dc2626",
            "alquiler_mes": 650.0,
            "energia_100km": 2.80,
            "productividad_min": 12,
            "productividad_max": 15,
            "productividad_xl_min": 10,
            "productividad_xl_max": 12,
            "velocidad_kmh": 40.0,
            "cap_sobre": 90,
            "cap_pm": 70,
            "cap_xl": 18,
            "cargas_dia": 1,
            "modo": "drive",
            "preferencia": 3,
        },
        "andarin": {
            "nombre": "Andarin",
            "icono": "person",
            "color": "#16a34a",
            "alquiler_mes": 5.0,
            "energia_100km": 0.0,
            "productividad_min": 15,
            "productividad_max": 18,
            "velocidad_kmh": 4.8,
            "cap_sobre": 25,
            "cap_pm": 18,
            "cap_xl": 0,
            "cargas_dia": 0,
            "modo": "walk",
            "preferencia": 3,
        },
        "remolque_bici": {
            "nombre": "Remolque bici",
            "icono": "bicycle",
            "color": "#7c3aed",
            "alquiler_mes": 150.0,
            "energia_100km": 0.25,
            "productividad_min": 15,
            "productividad_max": 18,
            "velocidad_kmh": 10.0,
            "cap_sobre": 45,
            "cap_pm": 40,
            "cap_xl": 0,
            "cargas_dia": 2,
            "modo": "bike",
            "preferencia": 3,
        },
    }


TARIFAS = {
    "sobre": 1.0,
    "pm": 1.2,
    "xl": 1.5,
    "extra_urgente": 0.5,
}

NOMBRES_TRABAJADORES = [
    "Ana",
    "Carlos",
    "Marta",
    "Javier",
    "Lucia",
    "Pablo",
    "Sofia",
    "Diego",
    "Elena",
    "Raul",
    "Irene",
    "Marcos",
    "Nuria",
    "Alvaro",
    "Clara",
    "Hector",
    "Paula",
    "Sergio",
    "Vera",
    "Tomas",
]
