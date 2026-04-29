from __future__ import annotations

import folium
import pandas as pd
import streamlit.components.v1 as components

from modules.logic import route_segment_estimates
from modules.theme import AMBER, BORDER, MUTED, PANEL, PRIMARY, PRIMARY_DARK, SUCCESS, TEXT


def _synthetic_start(lat: float, lon: float, distance_km: float, route_id: int) -> tuple[float, float]:
    direction = -1 if route_id % 2 == 0 else 1
    capped_distance = min(distance_km, 4.5)
    lat_shift = direction * capped_distance / 111
    lon_shift = -direction * capped_distance / (111 * 0.78)
    return lat + lat_shift, lon + lon_shift


def _segment_popup(title: str, transport: str, minutes: int, price: float, detail: str) -> folium.Popup:
    return folium.Popup(
        f"""
        <div style="font-family: Inter, Arial; min-width: 240px;">
            <b>{title}</b><br>
            Transporte: {transport}<br>
            Tiempo estimado: {minutes} min<br>
            Precio estimado: {price:.2f} €<br><br>
            {detail}
        </div>
        """,
        max_width=320,
    )


def _add_segment(
    route_map: folium.Map,
    start: tuple[float, float],
    end: tuple[float, float],
    color: str,
    title: str,
    transport: str,
    minutes: int,
    price: float,
    detail: str,
    weight: int = 4,
    dash_array: str | None = None,
) -> None:
    folium.PolyLine(
        [start, end],
        color=color,
        weight=weight,
        opacity=0.92,
        dash_array=dash_array,
        tooltip=f"{transport} · {minutes} min · {price:.2f} €",
        popup=_segment_popup(title, transport, minutes, price, detail),
    ).add_to(route_map)


def render_route_map(
    trips: pd.DataFrame,
    municipalities: dict[str, tuple[float, float]],
    parkings: dict[str, dict[str, object]],
    moto_hubs: dict[str, dict[str, object]],
    map_key: str = "tribbu_route_map",
) -> None:
    route_map = folium.Map(
        location=[39.34, -0.405],
        zoom_start=10,
        tiles="OpenStreetMap",
        control_scale=True,
    )
    dest_lat, dest_lon = municipalities["Almussafes"]
    destination = (dest_lat, dest_lon)
    bounds = [[dest_lat, dest_lon]]

    folium.Marker(
        destination,
        popup="<b>Área industrial de Almussafes</b><br>Destino laboral principal",
        tooltip="Área industrial de Almussafes",
        icon=folium.Icon(color="black", icon="briefcase", prefix="fa"),
    ).add_to(route_map)

    for _, row in trips.iterrows():
        pickup = (float(row["lat"]), float(row["lon"]))
        segments = route_segment_estimates(row, parkings, destination)
        access_km = float(segments["access_km"])
        access_minutes = int(segments["access_minutes"])
        user_start = _synthetic_start(pickup[0], pickup[1], access_km, int(row["id"]))

        parking_data = parkings.get(row["parking"], {})
        parking_point = (
            float(parking_data.get("lat", dest_lat)),
            float(parking_data.get("lon", dest_lon)),
        )

        bounds.extend([list(user_start), list(pickup), list(parking_point)])

        route_type = "Ruta caliente" if row["ruta_caliente"] else "Ruta con moto" if row["moto_destino"] else "Ruta con parking"
        access_transport = str(segments["access_transport"])
        access_price = 0.0 if access_transport == "a pie" else 1.20
        car_minutes = int(segments["car_minutes"])
        last_mile_transport = str(segments["last_mile_transport"])
        last_mile_minutes = int(segments["last_mile_minutes"])
        last_mile_price = 1.10 if row["moto_destino"] else 0.0

        total_minutes = int(segments["total_minutes"])
        total_price = access_price + float(row["precio"]) + last_mile_price

        popup_html = f"""
        <div style="font-family: Inter, Arial; min-width: 260px;">
            <b>{row['origen']} → Almussafes</b><br>
            {row['conductor']} · {row.get('turno', 'Turno mañana')}<br><br>
            <b>Salida</b>: {row['hora_salida']} desde {row.get('punto_recogida', row['origen'])}<br>
            <b>Llegada</b>: {row['hora_llegada']} · {row.get('zona_destino', 'Área industrial')}<br>
            <b>Plazas</b>: {row['plazas_disponibles']} libres · {row.get('plazas_reservadas', row['ocupacion_actual'])} reservadas<br>
            <b>Tiempo total</b>: {total_minutes} min · <b>Precio total</b>: {total_price:.2f} €<br><br>
            <b>Tramos calculados</b><br>
            Distancia total: {segments['total_km']} km<br>
            1. {access_transport}: {segments['access_km']} km a {'9' if access_transport == 'a pie' else '45'} km/h - {access_minutes} min - {access_price:.2f} EUR<br>
            2. Coche urbano: {segments['car_urban_km']} km a 30 km/h<br>
            3. Coche carretera/autovia: {segments['car_road_km']} km a 100 km/h<br>
            4. Coche compartido total: {segments['car_total_km']} km - {car_minutes} min - {float(row['precio']):.2f} EUR<br>
            5. {last_mile_transport}: {segments['last_mile_km']} km a {'45' if last_mile_transport == 'Moto compartida' else '9'} km/h - {last_mile_minutes} min - {last_mile_price:.2f} EUR<br><br>
            Tipo: {route_type}
        </div>
        """
        trip_popup = folium.Popup(popup_html, max_width=340)

        _add_segment(
            route_map,
            user_start,
            pickup,
            AMBER,
            f"Acceso al punto de recogida · {row['origen']}",
            access_transport,
            access_minutes,
            access_price,
            f"{segments['access_km']} km hasta {row.get('punto_recogida', row['origen'])}. Velocidad usada: {'9 km/h andando' if access_transport == 'a pie' else '45 km/h en moto'}.",
            weight=3,
            dash_array="8,8",
        )
        _add_segment(
            route_map,
            pickup,
            parking_point,
            TEXT,
            f"Coche compartido · {row['origen']} → Almussafes",
            "Coche compartido",
            car_minutes,
            float(row["precio"]),
            f"Conductor {row['conductor']}. {segments['car_urban_km']} km urbanos a 30 km/h y {segments['car_road_km']} km de carretera/autovia a 100 km/h.",
            weight=5 if row["ruta_caliente"] else 4,
        )
        _add_segment(
            route_map,
            parking_point,
            destination,
            AMBER if row["moto_destino"] else MUTED,
            f"Última milla · {row['parking']}",
            last_mile_transport,
            last_mile_minutes,
            last_mile_price,
            f"Desde {row['parking']} hasta {row.get('zona_destino', 'Área industrial de Almussafes')}.",
            weight=3,
            dash_array="4,7",
        )

        folium.CircleMarker(
            pickup,
            radius=7,
            color=TEXT,
            fill=True,
            fill_color=PRIMARY,
            fill_opacity=0.95,
            popup=trip_popup,
            tooltip=f"Pickup · {row['origen']} · {total_minutes} min · {total_price:.2f} €",
        ).add_to(route_map)

    for name, data in parkings.items():
        parking_location = (float(data["lat"]), float(data["lon"]))
        bounds.append(list(parking_location))
        folium.CircleMarker(
            parking_location,
            radius=8,
            color=TEXT,
            fill=True,
            fill_color=PRIMARY,
            fill_opacity=0.95,
            popup=(
                f"<b>{name}</b><br>"
                f"Ocupación: {data['ocupacion']}%<br>"
                f"Plazas libres: {data['plazas_libres']}<br>"
                f"Reservas 30 min: {data.get('reservas_30m', 0)}<br>"
                f"Accesibles libres: {data.get('accesibles_libres', 0)}<br>"
                f"Descuento alta ocupación: {data['descuento']}<br>"
                f"Motos: {data['motos']}"
            ),
            tooltip=f"{name} · {data['plazas_libres']} plazas libres",
        ).add_to(route_map)

    for name, data in moto_hubs.items():
        hub_location = (float(data["lat"]), float(data["lon"]))
        bounds.append(list(hub_location))
        folium.CircleMarker(
            hub_location,
            radius=9,
            color=TEXT,
            fill=True,
            fill_color=PRIMARY,
            fill_opacity=0.8,
            popup=(
                f"<b>{name}</b><br>{data['zona']}<br>"
                f"Motos disponibles: {data['motos_disponibles']} / {data['motos_totales']}<br>"
                f"Reservadas: {data['reservadas']} · Mantenimiento: {data['mantenimiento']}<br>"
                f"Batería media: {data['bateria']}% · Reposición: {data['sla_reposicion']}"
            ),
            tooltip=f"{name} · {data['motos_disponibles']} motos",
        ).add_to(route_map)

    legend = f"""
    <div style="position: fixed; bottom: 34px; left: 34px; z-index: 9999; background: {PANEL}; padding: 12px 14px; border: 1px solid {BORDER}; border-radius: 14px; box-shadow: 0 10px 24px rgba(17,17,17,.12); font-size: 13px;">
        <b>Tramos de ruta</b><br>
        <span style="color:{AMBER};">━</span> Acceso al pickup<br>
        <span style="color:{TEXT};">━</span> Coche compartido<br>
        <span style="color:{AMBER};">━</span> Moto / última milla<br>
        <span style="color:{PRIMARY};">●</span> Parking y hubs
    </div>
    """
    route_map.get_root().html.add_child(folium.Element(legend))
    if len(bounds) > 1:
        route_map.fit_bounds(bounds, padding=(25, 25))
    map_html = route_map.get_root().render()
    components.html(map_html, height=640, scrolling=False)
