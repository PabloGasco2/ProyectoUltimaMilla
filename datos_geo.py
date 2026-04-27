from __future__ import annotations

import math
from typing import Any

import requests
import streamlit as st

from config import CARTOCIUDAD_ADDRESS_URL, FALLBACK_BBOX, OVERPASS_URL, POSTCODE


def _headers() -> dict[str, str]:
    return {"User-Agent": "gls-simulador-46007/1.0"}


@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def cargar_portales_46007() -> list[dict[str, Any]]:
    params = {
        "f": "json",
        "limit": "10000",
        "filter": f"component_PostalDescriptor='{POSTCODE}'",
    }
    response = requests.get(CARTOCIUDAD_ADDRESS_URL, params=params, headers=_headers(), timeout=90)
    response.raise_for_status()
    features = response.json().get("features", [])

    portales = []
    vistos = set()
    for feature in features:
        props = feature.get("properties", {})
        geom = feature.get("geometry") or {}
        coords = geom.get("coordinates") or []
        if geom.get("type") != "Point" or len(coords) < 2:
            continue

        calle = props.get("component_ThoroughfareName") or "Sin calle"
        numero = props.get("locator_designator_addressNumber") or "S/N"
        extension = props.get("locator_designator_addressNumberExtension")
        if extension:
            numero = f"{numero}{extension}"

        clave = (calle, numero, round(coords[1], 7), round(coords[0], 7))
        if clave in vistos:
            continue
        vistos.add(clave)

        portales.append(
            {
                "id": len(portales),
                "calle": calle,
                "numero": str(numero),
                "lat": float(coords[1]),
                "lon": float(coords[0]),
                "fuente": props.get("dataProvider") or "CartoCiudad",
            }
        )

    return portales


@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def cargar_calles_osm() -> list[dict[str, Any]]:
    bbox = bbox_portales(cargar_portales_46007())
    query = f"""
    [out:json][timeout:80];
    (
      way["highway"]["name"]({bbox["south"]},{bbox["west"]},{bbox["north"]},{bbox["east"]});
    );
    out tags geom;
    """
    response = requests.get(OVERPASS_URL, params={"data": query}, headers=_headers(), timeout=90)
    response.raise_for_status()
    calles = []
    for el in response.json().get("elements", []):
        geom = [(p["lat"], p["lon"]) for p in el.get("geometry", []) if "lat" in p and "lon" in p]
        if len(geom) >= 2:
            calles.append({"nombre": el.get("tags", {}).get("name", "Calle"), "geom": geom, "tags": el.get("tags", {})})
    return calles


def bbox_portales(portales: list[dict[str, Any]], margen: float = 0.002) -> dict[str, float]:
    if not portales:
        return FALLBACK_BBOX.copy()
    lats = [p["lat"] for p in portales]
    lons = [p["lon"] for p in portales]
    return {
        "south": min(lats) - margen,
        "west": min(lons) - margen,
        "north": max(lats) + margen,
        "east": max(lons) + margen,
    }


def distancia_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = a
    lat2, lon2 = b
    radio = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlat / 2) ** 2
    y = math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return 2 * radio * math.asin(math.sqrt(x + y))
