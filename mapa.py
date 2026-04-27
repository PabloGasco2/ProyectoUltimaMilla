from __future__ import annotations

from typing import Any

import folium
import networkx as nx
import osmnx as ox
import streamlit as st

from config import CARTOCIUDAD_WMS_URL, HUB
from datos_geo import bbox_portales, cargar_calles_osm, distancia_km


@st.cache_resource(show_spinner=False)
def cargar_grafo_calles(bbox: tuple[float, float, float, float], modo: str):
    south, west, north, east = bbox
    network_type = "walk" if modo == "walk" else "bike" if modo == "bike" else "drive"
    return ox.graph_from_bbox(north, south, east, west, network_type=network_type, simplify=True)


def _ruta_red(grafo, puntos: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if not grafo or len(puntos) < 2:
        return puntos
    coords = []
    try:
        nodos = [ox.distance.nearest_nodes(grafo, lon, lat) for lat, lon in puntos]
        for a, b in zip(nodos, nodos[1:]):
            if a == b:
                continue
            path = nx.shortest_path(grafo, a, b, weight="length")
            for node in path:
                data = grafo.nodes[node]
                coords.append((data["y"], data["x"]))
    except Exception:
        return puntos
    return coords or puntos


def _orden_nearest_neighbor(paradas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if paradas and all(p.get("orden_ruta") for p in paradas):
        return sorted(paradas, key=lambda p: p["orden_ruta"])
    pendientes = paradas[:]
    actual = (HUB["lat"], HUB["lon"])
    ordenadas = []
    while pendientes:
        siguiente = min(pendientes, key=lambda p: distancia_km(actual, (p["lat"], p["lon"])))
        pendientes.remove(siguiente)
        ordenadas.append(siguiente)
        actual = (siguiente["lat"], siguiente["lon"])
    return ordenadas


def _eventos_vehiculo(resultado: dict[str, Any], dia: int, vehiculo_id: str) -> list[dict[str, Any]]:
    eventos = [
        e for e in resultado.get("eventos_vehiculos", [])
        if e.get("dia") == dia and e.get("vehiculo_id") == vehiculo_id and e.get("lat") is not None and e.get("lon") is not None
    ]
    return sorted(eventos, key=lambda e: (float(e.get("hora_decimal", 0)), int(e.get("secuencia_evento", 0))))


def _puntos_operativos(resultado: dict[str, Any], dia: int, ruta: dict[str, Any], paradas: list[dict[str, Any]]) -> list[tuple[float, float]]:
    puntos = [(HUB["lat"], HUB["lon"])]
    for evento in _eventos_vehiculo(resultado, dia, ruta["vehiculo_id"]):
        punto = (float(evento["lat"]), float(evento["lon"]))
        if distancia_km(puntos[-1], punto) > 0.015:
            puntos.append(punto)
    if len(puntos) <= 1:
        puntos.extend((p["lat"], p["lon"]) for p in paradas)
    if distancia_km(puntos[-1], (HUB["lat"], HUB["lon"])) > 0.015:
        puntos.append((HUB["lat"], HUB["lon"]))
    return puntos


def crear_mapa_rutas(
    portales: list[dict[str, Any]],
    resultado: dict[str, Any],
    dia: int,
    vehiculos_visibles: list[str],
    vista: str,
    usar_red_real: bool,
):
    tiles = None
    mapa = folium.Map(location=(HUB["lat"], HUB["lon"]), zoom_start=15, tiles=tiles, control_scale=True)
    if vista == "satelite":
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri",
            name="Satelite",
        ).add_to(mapa)
    folium.TileLayer("CartoDB positron", name="Claro").add_to(mapa)
    folium.TileLayer("OpenStreetMap", name="OSM").add_to(mapa)
    folium.raster_layers.WmsTileLayer(
        url=CARTOCIUDAD_WMS_URL,
        name="Codigo postal oficial CartoCiudad",
        layers="codigo-postal",
        fmt="image/png",
        transparent=True,
        version="1.3.0",
        attr="CC BY 4.0 CartoCiudad / SCNE",
        show=True,
    ).add_to(mapa)

    folium.Marker(
        [HUB["lat"], HUB["lon"]],
        tooltip=HUB["nombre"],
        popup="Microhub fijo en parking de Joaquin Sorolla",
        icon=folium.Icon(color="green", icon="warehouse", prefix="fa"),
    ).add_to(mapa)

    bbox = bbox_portales(portales, margen=0.003)
    bbox_tuple = (bbox["south"], bbox["west"], bbox["north"], bbox["east"])
    grafos = {}
    calles = cargar_calles_osm()
    for calle in calles:
        folium.PolyLine(calle["geom"], color="#94a3b8", weight=1, opacity=0.35).add_to(mapa)

    rutas = resultado["rutas_por_dia"].get(dia, [])
    color_por_vehiculo = {ruta["vehiculo_id"]: ruta["color"] for ruta in rutas}
    nombre_por_vehiculo = {ruta["vehiculo_id"]: ruta["vehiculo"] for ruta in rutas}
    for ruta in rutas:
        if vehiculos_visibles and ruta["vehiculo_id"] not in vehiculos_visibles:
            continue
        paradas = _orden_nearest_neighbor(ruta["paradas"])
        puntos = _puntos_operativos(resultado, dia, ruta, paradas)
        if usar_red_real:
            modo = ruta["modo"]
            if modo not in grafos:
                grafos[modo] = cargar_grafo_calles(bbox_tuple, modo)
            coords = _ruta_red(grafos[modo], puntos)
        else:
            coords = puntos

        grupo = folium.FeatureGroup(name=ruta["vehiculo"], show=True)
        folium.PolyLine(coords, color=ruta["color"], weight=4, opacity=0.82, tooltip=ruta["vehiculo"]).add_to(grupo)
        for idx, p in enumerate(paradas, start=1):
            folium.CircleMarker(
                [p["lat"], p["lon"]],
                radius=4,
                color=ruta["color"],
                fill=True,
                fill_color=ruta["color"],
                fill_opacity=0.9,
                tooltip=f"{idx}. {p['calle']} {p['numero']} - {p.get('hora_entrega_txt', '')}",
                popup=(
                    f"{ruta['vehiculo']}<br>"
                    f"Repartidor: {ruta.get('trabajador', '')}<br>"
                    f"{idx}. {p['calle']} {p['numero']}<br>"
                    f"Hora: {p.get('hora_entrega_txt', '')}<br>"
                    f"{p['tipo']} - {p['servicio']}<br>"
                    f"Carga: {p.get('origen_carga', 'Hub')}"
                ),
            ).add_to(grupo)
        grupo.add_to(mapa)

    grupo_repos = folium.FeatureGroup(name="Viajes de reposicion al hub", show=True)
    hay_repos = False
    eventos_por_vehiculo: dict[str, list[dict[str, Any]]] = {}
    for evento in resultado.get("eventos_vehiculos", []):
        if evento.get("dia") == dia and evento.get("lat") is not None and evento.get("lon") is not None:
            eventos_por_vehiculo.setdefault(evento["vehiculo_id"], []).append(evento)
    for vehiculo_id, eventos in eventos_por_vehiculo.items():
        if vehiculos_visibles and vehiculo_id not in vehiculos_visibles:
            continue
        eventos = sorted(eventos, key=lambda e: (float(e.get("hora_decimal", 0)), int(e.get("secuencia_evento", 0))))
        anterior = None
        for evento in eventos:
            punto = (float(evento["lat"]), float(evento["lon"]))
            es_hub = evento.get("evento") == "Carga en hub"
            if es_hub and anterior and distancia_km(anterior, (HUB["lat"], HUB["lon"])) > 0.015:
                folium.PolyLine(
                    [anterior, (HUB["lat"], HUB["lon"])],
                    color=color_por_vehiculo.get(vehiculo_id, "#0f766e"),
                    weight=3,
                    opacity=0.8,
                    dash_array="6,6",
                    tooltip=f"{nombre_por_vehiculo.get(vehiculo_id, vehiculo_id)} vuelve al hub {evento.get('hora', '')}",
                ).add_to(grupo_repos)
                hay_repos = True
            anterior = punto
    if hay_repos:
        grupo_repos.add_to(mapa)

    traspasos = [t for t in resultado.get("traspasos", []) if t["dia"] == dia]
    if traspasos:
        grupo_t = folium.FeatureGroup(name="Traspasos furgoneta", show=True)
        for t in traspasos:
            folium.Marker(
                [t["lat"], t["lon"]],
                tooltip=f"Traspaso {t['paquetes']} paquetes a {t['hacia']}",
                popup=(
                    f"{t['traspaso_id']}<br>"
                    f"Hora: {t['hora']}<br>"
                    f"Desde: {t['desde']}<br>"
                    f"Hacia: {t['hacia']}<br>"
                    f"Paquetes P/M: {t.get('paquetes_pm', t['paquetes'])}<br>"
                    f"Paquetes XL: {t.get('paquetes_xl', 0)}<br>"
                    f"Dador P/M: {t.get('pm_dador_antes', '')} -> {t.get('pm_dador_despues', '')} / {t.get('capacidad_dador_pm', '')}<br>"
                    f"Receptor P/M: {t.get('pm_receptor_antes', '')} -> {t.get('pm_receptor_despues', '')} / {t.get('capacidad_receptor_pm', '')}<br>"
                    f"Ubicacion: {t['ubicacion']}"
                ),
                icon=folium.Icon(color="orange", icon="exchange", prefix="fa"),
            ).add_to(grupo_t)
        grupo_t.add_to(mapa)

    cargas_hub = [c for c in resultado.get("cargas_hub", []) if c["dia"] == dia]
    if cargas_hub:
        grupo_h = folium.FeatureGroup(name="Cargas en hub", show=True)
        for idx, c in enumerate(cargas_hub):
            offset = (idx % 8) * 0.000035
            folium.CircleMarker(
                [HUB["lat"] + offset, HUB["lon"] + offset],
                radius=6,
                color="#0f766e",
                fill=True,
                fill_color="#ef4444" if c.get("vehiculo_id", "").startswith("furgoneta") else "#14b8a6",
                fill_opacity=0.9,
                tooltip=f"{c['hora']} - {c['vehiculo']} carga {c['paquetes']} paquetes",
                popup=(
                    f"Carga en hub<br>"
                    f"Hora: {c['hora']}<br>"
                    f"Vehiculo: {c['vehiculo']}<br>"
                    f"Repartidor: {c['repartidor']}<br>"
                    f"Tipo: {c['tipo']}<br>"
                    f"P/M: {c.get('paquetes_pm', c['paquetes'])}<br>"
                    f"XL: {c.get('paquetes_xl', 0)}<br>"
                    f"Inv. P/M: {c.get('pm_antes', '')} -> {c.get('pm_despues', '')} / {c.get('cap_pm', '')}<br>"
                    f"Inv. XL: {c.get('xl_antes', '')} -> {c.get('xl_despues', '')} / {c.get('cap_xl', '')}<br>"
                    f"Carga total: {c['carga_antes']} -> {c['carga_despues']} / {c['capacidad']}"
                ),
            ).add_to(grupo_h)
        grupo_h.add_to(mapa)

    leyenda_items = []
    for ruta in rutas:
        if vehiculos_visibles and ruta["vehiculo_id"] not in vehiculos_visibles:
            continue
        leyenda_items.append(
            f"<div><span style='display:inline-block;width:12px;height:12px;background:{ruta['color']};margin-right:6px'></span>{ruta['vehiculo']} - {ruta.get('trabajador', '')}</div>"
        )
    if leyenda_items:
        html = """
        <div style="position: fixed; bottom: 24px; left: 24px; z-index: 9999;
        background: white; padding: 10px 12px; border: 1px solid #cbd5e1;
        border-radius: 6px; font-size: 12px; max-height: 220px; overflow-y: auto;">
        <strong>Rutas por unidad</strong>
        """ + "".join(leyenda_items) + "</div>"
        mapa.get_root().html.add_child(folium.Element(html))

    folium.LayerControl(collapsed=False).add_to(mapa)
    return mapa


def pintar_mapa(*args, **kwargs):
    from streamlit_folium import st_folium

    mapa = crear_mapa_rutas(*args, **kwargs)
    return st_folium(mapa, height=680, use_container_width=True, returned_objects=[], key="mapa_rutas_gls")
