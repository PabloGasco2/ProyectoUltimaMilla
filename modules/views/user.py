from __future__ import annotations

from datetime import datetime, time, timedelta

import pandas as pd
import streamlit as st

from modules.data import AppData
from modules.logic import access_recommendation, calculate_matches, haversine_km, impact_metrics, minutes_between, route_segment_estimates
from modules.maps import render_route_map
from modules.ui import availability_card, badge, feature_card, journey_card, metric_card, page_title, trip_card


def render_user_workspace(data: AppData, persona: str) -> None:
    if persona == "Pasajero":
        section = st.radio(
            "Menú pasajero",
            ["Inicio", "Viaje", "Match", "Mapa", "Servicios", "Accesible"],
            horizontal=True,
            label_visibility="collapsed",
            key="passenger_menu",
        )
        if section == "Inicio":
            render_passenger_home(data)
        elif section == "Viaje":
            render_search_trip(data)
        elif section == "Match":
            render_matching(data)
        elif section == "Mapa":
            render_user_map(data)
        elif section == "Servicios":
            render_user_services(data)
        elif section == "Accesible":
            render_accessibility(data)
    else:
        section = st.radio(
            "Menú conductor",
            ["Inicio", "Publicar", "Reservas", "Servicios", "Incentivos", "Mapa"],
            horizontal=True,
            label_visibility="collapsed",
            key="driver_menu",
        )
        if section == "Inicio":
            render_driver_home(data)
        elif section == "Publicar":
            render_publish_trip(data)
        elif section == "Reservas":
            render_driver_seats(data)
        elif section == "Servicios":
            render_driver_packages(data)
        elif section == "Incentivos":
            render_driver_incentives(data)
        elif section == "Mapa":
            page_title("Mapa de mis rutas", "Pulsa una línea para consultar el punto de recogida y el itinerario operativo.")
            render_route_map(data.trips, data.municipalities, data.parkings, data.moto_hubs, map_key="driver_route_map")


def render_passenger_home(data: AppData) -> None:
    page_title("Tu movilidad diaria a Almussafes", "Una experiencia de trabajador: encontrar coche, llegar al punto de recogida y completar el último tramo.")
    metrics = impact_metrics(data.trips)
    with st.expander("Resumen de hoy", expanded=True):
        cols = st.columns(2)
        with cols[0]:
            metric_card("Viajes disponibles", str(metrics["active_trips"]), "Rutas activas hacia Almussafes")
        with cols[1]:
            metric_card("Tasa de match", f"{metrics['matching_rate']:.0f}%", "Solicitudes emparejadas")

    with st.expander("Qué puedes hacer", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            feature_card("Planificar viaje", "Busca una ruta compatible y revisa el acceso al punto de recogida antes de reservar.", ["Viaje"])
        with c2:
            feature_card("Completar servicios", "Añade parking, moto compartida, locker o preferencias de accesibilidad desde una misma vista.", ["Servicios"])

    with st.expander("Disponibilidad operativa", expanded=False):
        cols = st.columns(2)
        for idx, (name, parking) in enumerate(data.parkings.items()):
            with cols[idx % 2]:
                availability_card(
                    name,
                    parking["ocupacion"],
                    f"{parking['plazas_libres']} plazas libres · {parking['reservas_30m']} reservas próximas",
                    f"{parking['accesibles_libres']} accesibles libres · {parking['cargadores_libres']} cargadores libres · actualizado {parking['ultima_actualizacion']}",
                    parking["estado"],
                    "pink",
                )


def _driver_request_matches(my_routes: pd.DataFrame, passengers: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, route in my_routes.iterrows():
        for request_id, passenger in passengers.iterrows():
            if passenger["turno"] != route["turno"]:
                continue
            origin_score = 42 if passenger["origen"] == route["origen"] else 18
            zone_score = 26 if passenger["zona_destino"] == route["zona_destino"] else 12
            time_gap = minutes_between(route["hora_llegada"], passenger["llegada_deseada"])
            time_score = max(0, 24 - time_gap * 2)
            seats_score = 8 if route["plazas_disponibles"] > 0 else 0
            score = min(100, int(origin_score + zone_score + time_score + seats_score))
            if score < 45:
                continue
            rows.append(
                {
                    "request_id": int(request_id),
                    "route_id": int(route["id"]),
                    "pasajero": passenger["pasajero"],
                    "origen": passenger["origen"],
                    "turno": passenger["turno"],
                    "llegada_deseada": passenger["llegada_deseada"],
                    "ruta_publicada": f"{route['origen']} -> {route['zona_destino']}",
                    "plazas_disponibles": int(route["plazas_disponibles"]),
                    "coincidencia": score,
                    "estado": passenger["estado"],
                }
            )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["coincidencia", "plazas_disponibles"], ascending=False)


def _requested_routes_for_driver(my_routes: pd.DataFrame, passengers: pd.DataFrame) -> pd.DataFrame:
    normal_turns = set(my_routes["turno"])
    normal_origins = set(my_routes["origen"])
    filtered = passengers[
        passengers["turno"].isin(normal_turns)
        & (passengers["origen"].isin(normal_origins) | passengers["estado"].isin(["Match propuesto", "Pendiente"]))
    ].copy()
    if filtered.empty:
        return filtered
    filtered["ruta_solicitada"] = filtered["origen"] + " -> " + filtered["zona_destino"]
    filtered["encaja_con_ruta_habitual"] = filtered["origen"].isin(normal_origins).map({True: "Origen habitual", False: "Turno habitual"})
    return filtered[["pasajero", "ruta_solicitada", "turno", "llegada_deseada", "preferencia", "necesidad", "encaja_con_ruta_habitual", "estado"]]


def render_driver_home(data: AppData) -> None:
    page_title("Panel del conductor", "Publica rutas recurrentes, gestiona plazas y accede a incentivos por ocupación.")
    my_routes = data.trips[data.trips["conductor"].isin(["Marta G.", "Laura P.", "Carlos R."])].head(5)
    driver_matches = _driver_request_matches(my_routes, data.passengers)
    requested_routes = _requested_routes_for_driver(my_routes, data.passengers)
    with st.expander("Resumen del conductor", expanded=True):
        cols = st.columns(2)
        with cols[0]:
            metric_card("Rutas activas", "5", "Esta semana")
        with cols[1]:
            metric_card("Ocupación media", "3,1", "Objetivo: 3+")
    with st.expander("Mis rutas y solicitudes compatibles", expanded=True):
        st.markdown("#### Mayores coincidencias para aceptar")
        accepted_requests = st.session_state.setdefault("driver_accepted_requests", [])
        if driver_matches.empty:
            st.info("No hay solicitudes compatibles con tus rutas publicadas ahora mismo.")
        else:
            for _, match in driver_matches.head(4).iterrows():
                accepted = int(match["request_id"]) in accepted_requests
                left, right = st.columns([3, 1])
                with left:
                    st.markdown(
                        f"""
                        <div class="card-flat">
                            <div class="card-title">{match['pasajero']} - {match['coincidencia']}% de coincidencia</div>
                            <p>{match['origen']} - llegada deseada {match['llegada_deseada']} - {match['turno']}</p>
                            <p class="muted">Ruta publicada: <strong>{match['ruta_publicada']}</strong> - Plazas libres: <strong>{match['plazas_disponibles']}</strong> - Estado: {match['estado']}</p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with right:
                    if accepted:
                        st.success("Aceptada")
                    elif st.button("Aceptar", key=f"driver_accept_{match['request_id']}_{match['route_id']}", type="primary"):
                        accepted_requests.append(int(match["request_id"]))
                        st.rerun()

        st.markdown("#### Rutas solicitadas según tus rutas habituales")
        if requested_routes.empty:
            st.info("No hay rutas solicitadas que encajen con tus rutas habituales.")
        else:
            st.dataframe(requested_routes.head(8), use_container_width=True, hide_index=True)
    with st.expander("Ingresos e incentivos", expanded=False):
        cols = st.columns(2)
        with cols[0]:
            metric_card("Ingresos estimados", "42 €", "Compensación semanal")
        with cols[1]:
            metric_card("Bonificaciones", "18 €", "Parking + paquetes")


def render_search_trip(data: AppData) -> None:
    page_title("Planificar viaje como pasajero", "El resultado prioriza compatibilidad, proximidad al pickup, turno laboral y experiencia multimodal.")
    with st.form("passenger_search"):
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            origin = st.selectbox("Municipio de origen", [x for x in data.municipalities if x != "Almussafes"], index=0)
            passengers = st.number_input("Pasajeros", min_value=1, max_value=4, value=1)
        with col2:
            shift = st.selectbox("Turno", ["Cualquiera", "Turno mañana", "Turno central", "Turno tarde"])
            desired_arrival = st.time_input("Hora deseada de llegada", value=time(7, 40))
        with col3:
            zone = st.selectbox("Zona destino", ["Cualquiera"] + sorted(data.trips["zona_destino"].unique().tolist()))
            preference = st.selectbox("Preferencia", ["Menor precio", "Menor desvío", "Mejor valoración", "Vehículo eléctrico/híbrido"])
        with col4:
            max_pickup = st.slider("Radio máximo al pickup", 0.5, 5.0, 2.5, 0.5)
            reduced_mobility = st.checkbox("Movilidad reducida")
            visual_alert = st.checkbox("Alerta visual")
            transcription = st.checkbox("Transcripción del chat")
        with col5:
            recurrence = st.selectbox("Recurrencia", ["Viaje puntual", "Lunes a viernes", "2-3 días por semana"])
            locker_need = st.checkbox("Quiero usar locker")
            moto_needed = st.checkbox("Necesito última milla en moto")
            only_hot = st.checkbox("Priorizar rutas calientes")
        search = st.form_submit_button("Buscar viajes compatibles")

    if not search:
        st.info("Completa el formulario y pulsa buscar para ver recomendaciones disponibles.")
        return

    trips = data.trips.copy()
    trips = trips[trips["plazas_disponibles"] >= passengers]
    if reduced_mobility:
        trips = trips[trips["accesible"]]
    if moto_needed:
        trips = trips[trips["moto_destino"]]
    if only_hot:
        trips = trips[trips["ruta_caliente"]]
    if shift != "Cualquiera":
        trips = trips[trips["turno"] == shift]
    if zone != "Cualquiera":
        trips = trips[trips["zona_destino"] == zone]

    exact = trips[trips["origen"] == origin]
    source = exact if not exact.empty else trips
    if exact.empty:
        st.warning("No hay un coche que salga exactamente desde tu punto. Te recomendamos desplazarte hasta el punto de recogida más cercano.")

    matches = calculate_matches(source, data.municipalities, origin, desired_arrival.strftime("%H:%M"), passengers, preference)
    matches = matches[matches["pickup_km"] <= max_pickup].head(5)
    if matches.empty:
        st.error("No hay viajes compatibles con esos filtros. El equipo operativo vería esta demanda como no cubierta.")
        return

    for _, row in matches.iterrows():
        left, right = st.columns([2.15, 1])
        with left:
            trip_card(row, "passenger")
        with right:
            mode, instruction, minutes = access_recommendation(row["pickup_km"], row["origen"], row["conductor"])
            journey_card(mode, instruction, row["pickup_km"], minutes, row["parking"])

    if visual_alert:
        st.markdown("<div class='success-card'><strong>Alerta visual:</strong> nuevo viaje compatible resaltado y listo para reserva.</div>", unsafe_allow_html=True)
    if transcription:
        st.info("Transcripción activada: el chat conductor-pasajero se mostrará con texto y confirmación visual.")
    if locker_need:
        st.info("Locker sugerido: Locker Almussafes Industrial, coordinado con llegada al parking de destino.")
    st.caption(f"Recurrencia seleccionada: {recurrence}. Se aplicarán reservas recurrentes y reglas de cancelación asociadas.")


def render_matching(data: AppData) -> None:
    page_title("Matching inteligente", "Priorización basada en proximidad, horario, plazas, valoración, ocupación y preferencias.")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        origin = st.selectbox("Origen", [x for x in data.municipalities if x != "Almussafes"], index=1, key="match_origin")
    with c2:
        arrival = st.time_input("Llegada deseada", value=time(7, 40), key="match_arrival")
    with c3:
        passengers = st.number_input("Pasajeros", 1, 4, 1, key="match_passengers")
    with c4:
        preference = st.selectbox("Preferencia", ["Menor precio", "Menor desvío", "Mejor valoración", "Vehículo eléctrico/híbrido"], key="match_pref")

    matches = calculate_matches(data.trips, data.municipalities, origin, arrival.strftime("%H:%M"), passengers, preference).head(6)
    selected_route_id = st.session_state.get("match_route_id")
    match_ids = [int(route_id) for route_id in matches["id"].tolist()]
    if selected_route_id is not None and int(selected_route_id) not in match_ids:
        st.session_state.pop("match_route_id", None)
        selected_route_id = None

    if selected_route_id is not None:
        route_id = int(selected_route_id)
        selected = matches[matches["id"] == route_id]
        if selected.empty:
            st.session_state.pop("match_route_id", None)
            st.rerun()

        row = selected.iloc[0]
        segments = route_segment_estimates(row, data.parkings, data.municipalities["Almussafes"])
        reserved_ids = st.session_state.setdefault("match_reserved_route_ids", [])
        is_reserved = route_id in reserved_ids
        top_left, top_center, top_right = st.columns([1, 2, 1])
        with top_left:
            if st.button("Volver a ofertas", key="match_back_to_offers"):
                st.session_state.pop("match_route_id", None)
                st.rerun()
        with top_center:
            st.markdown(
                f"""
                <div class="card-flat">
                    <div class="card-title">Trayecto con {row['conductor']}</div>
                    <p class="muted">{row['origen']} a Almussafes - {segments['total_km']} km - {segments['total_minutes']} min - parking {row['parking']}</p>
                    <p class="muted">Andando {segments['access_km'] if segments['access_transport'] == 'a pie' else 0} km · Moto {(segments['access_km'] if segments['access_transport'] != 'a pie' else 0) + (segments['last_mile_km'] if segments['last_mile_transport'] == 'Moto compartida' else 0):.1f} km · Coche {segments['car_total_km']} km</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with top_right:
            if is_reserved:
                st.success("Reserva confirmada")
            elif st.button("Reservar trayecto", key=f"match_reserve_button_{route_id}", type="primary"):
                reserved_ids.append(route_id)
                st.rerun()

        if is_reserved:
            st.success(f"Ya has reservado el trayecto con {row['conductor']}.")

        render_route_map(
            selected,
            data.municipalities,
            data.parkings,
            data.moto_hubs,
            map_key=f"match_route_map_{route_id}",
        )
        return
    with st.expander("Criterios del algoritmo", expanded=True):
        st.markdown("Proximidad al punto de recogida, horario, plazas, valoración, ocupación, ruta caliente, parking, moto disponible y preferencia del usuario.")
    labels = ["Mejor match", "Segundo match", "Alternativa cercana"]
    for idx, (_, row) in enumerate(matches.head(3).iterrows()):
        left, right = st.columns([.9, 2.1])
        with left:
            metric_card(labels[idx], f"{row['score']}/100", row["origen"])
            st.progress(int(row["score"]))
        with right:
            st.markdown(
                f"""
                <div class="card">
                    <div>{badge('Alta compatibilidad') if row['score'] >= 80 else badge('Alternativa cercana', 'blue')}{badge('Ruta caliente', 'orange') if row['ruta_caliente'] else ''}</div>
                    <div class="card-title">{row['conductor']} · {row['origen']} → Almussafes</div>
                    <p>{row['reason']}</p>
                    <p class="muted">Plazas {row['plazas_disponibles']} · Valoración {row['valoracion']:.1f}/5 · Ocupación {row['ocupacion_actual']}/{row['capacidad']} · {row['tipo_coche']}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Ver trayecto en mapa", key=f"match_route_map_button_{row['id']}"):
                st.session_state["match_route_id"] = int(row["id"])
                st.rerun()

    with st.expander("Ver tabla comparativa", expanded=False):
        st.dataframe(
            matches[["conductor", "origen", "hora_salida", "hora_llegada", "plazas_disponibles", "pickup_km", "score", "parking"]],
            use_container_width=True,
            hide_index=True,
        )


def render_user_map(data: AppData) -> None:
    page_title("Mapa de rutas", "Pulsa una línea para ver salida, plazas y cómo llegar al punto de recogida.")
    c1, c2 = st.columns(2)
    with c1:
        origin = st.selectbox("Filtrar origen", ["Todos"] + [x for x in data.municipalities if x != "Almussafes"], key="map_origin")
    with c2:
        shift = st.selectbox("Filtrar turno", ["Todos", "Turno mañana", "Turno central", "Turno tarde"], key="map_shift")
    trips = data.trips.copy()
    if origin != "Todos":
        trips = trips[trips["origen"] == origin]
    if shift != "Todos":
        trips = trips[trips["turno"] == shift]
    render_route_map(trips, data.municipalities, data.parkings, data.moto_hubs, map_key=f"passenger_route_map_{origin}_{shift}_{len(trips)}")


def render_user_services(data: AppData) -> None:
    option = st.radio("Servicio", ["Parking y motos", "Paquetería y lockers"], horizontal=True, key="services_menu")
    if option == "Parking y motos":
        render_multimodal(data)
    else:
        render_packages(data)


def render_publish_trip(data: AppData) -> None:
    page_title("Publicar viaje como conductor", "Formulario operativo para crear una ruta recurrente y publicarla en la red.")
    with st.form("publish_driver_trip"):
        c1, c2, c3 = st.columns(3)
        with c1:
            name = st.text_input("Nombre", value="Elena V.")
            origin = st.selectbox("Municipio de salida", [x for x in data.municipalities if x != "Almussafes"], index=0)
            departure = st.time_input("Hora de salida", value=time(7, 5))
            pickup = st.selectbox("Punto de recogida", ["Estación", "Ayuntamiento", "Parking intermodal", "Avenida principal"])
        with c2:
            shift = st.selectbox("Turno asociado", ["Turno mañana", "Turno central", "Turno tarde"])
            seats = st.number_input("Plazas disponibles", 1, 6, 3)
            vehicle = st.selectbox("Tipo de vehículo", ["eléctrico", "híbrido", "diésel", "gasolina"])
            auto_confirm = st.checkbox("Confirmación automática", value=True)
            packages = st.checkbox("Acepta transportar paquetes", value=True)
        with c3:
            zone = st.selectbox("Zona de destino", sorted(data.trips["zona_destino"].unique().tolist()))
            accessible = st.checkbox("Acepta necesidades de accesibilidad", value=True)
            parking = st.selectbox("Parking preferido", list(data.parkings.keys()))
            recurrence = st.selectbox("Recurrencia", ["L-V", "Martes y jueves", "Viaje puntual"])
            incentives = st.checkbox("Activar incentivos alta ocupación", value=True)
        publish = st.form_submit_button("Publicar viaje")

    if publish:
        lat, lon = data.municipalities[origin]
        dest_lat, dest_lon = data.municipalities["Almussafes"]
        distance = haversine_km(lat, lon, dest_lat, dest_lon) * 1.18
        arrival = datetime.combine(datetime.today(), departure) + timedelta(minutes=int(distance / 55 * 60 + 8))
        co2_per_passenger = 0.12 * distance
        impact = co2_per_passenger * seats
        st.success("Viaje publicado correctamente.")
        st.markdown(
            f"""
            <div class="card">
                <div>{badge('Parking incluido')}{badge('3+ ocupantes') if seats >= 3 else ''}{badge('Acepta paquetes') if packages else ''}{badge('Accesible', 'purple') if accessible else ''}</div>
                <div class="card-title">{name} · {origin} → {zone}</div>
                <p>Salida <strong>{departure.strftime('%H:%M')}</strong> · Llegada estimada <strong>{arrival.strftime('%H:%M')}</strong> · Turno <strong>{shift}</strong> · Vehículo <strong>{vehicle}</strong></p>
                <p>Punto de recogida: <strong>{origin} · {pickup}</strong> · Plazas publicadas: <strong>{seats}</strong> · Parking: <strong>{parking}</strong></p>
                <p>Impacto si se completa: <strong>{impact:.1f} kg de CO2 evitado</strong> ({co2_per_passenger:.1f} kg x {seats} pasajeros)</p>
                <p class="muted">Confirmación: {'automática' if auto_confirm else 'manual'} · Recurrencia: {recurrence} · Bonificación: {'20% de descuento de parking + prioridad en matching' if seats >= 3 and incentives else 'sin bonificación automática en esta configuración'}.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_driver_seats(data: AppData) -> None:
    page_title("Mis plazas y reservas", "Solicitudes pendientes y ocupación actual del vehículo.")
    rows = data.passengers.head(7).copy()
    rows["Conductor sugerido"] = ["Marta G.", "Laura P.", "Carlos R.", "Amparo S.", "Noelia C.", "Javier M.", "Pau L."]
    st.dataframe(rows, use_container_width=True, hide_index=True)
    if st.button("Confirmar solicitudes seleccionadas"):
        st.success("Solicitudes confirmadas. Los pasajeros recibirán confirmación y punto de recogida.")


def render_multimodal(data: AppData) -> None:
    page_title("Parking y motos compartidas", "Integración multimodal para parkings, bonificaciones y última milla.")
    with st.expander("Parkings disponibles", expanded=True):
        cols = st.columns(2)
        for idx, (name, parking) in enumerate(data.parkings.items()):
            with cols[idx % 2]:
                availability_card(
                    name,
                    parking["ocupacion"],
                    f"{parking['plazas_libres']} libres de {parking['plazas_totales']} · descuento {parking['descuento']}",
                    f"{parking['reservas_30m']} reservas próximas · {parking['accesibles_libres']} accesibles · {parking['cargadores_libres']} cargadores",
                    parking["estado"],
                    "pink",
                )

    with st.expander("Motos compartidas", expanded=False):
        for hub, info in data.moto_hubs.items():
            matricula = info.get("matricula", "pendiente")
            parking_moto = info.get("parking", info.get("zona", hub))
            plaza_parking = info.get("plaza_parking", "pendiente")
            left, right = st.columns([3, 1])
            with left:
                st.markdown(
                    f"""
                    <div class="card-flat">
                        <div class="card-title">{hub}</div>
                        <p>Moto asignada: <strong>{matricula}</strong> - Plaza <strong>{plaza_parking}</strong> en <strong>{parking_moto}</strong></p>
                        <p>{info['zona']} · <strong>{info['motos_disponibles']} disponibles</strong> / {info['motos_totales']}</p>
                        <p class="muted">Reservadas {info['reservadas']} · mantenimiento {info['mantenimiento']} · batería {info['bateria']}% · reposición {info['sla_reposicion']}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with right:
                if st.button("Reservar", key=f"user_moto_{hub}"):
                    st.success(
                        f"Moto reservada en {hub}. Matricula: {matricula}. "
                        f"Parking: {parking_moto}. Plaza: {plaza_parking}."
                    )

    with st.expander("Flujo recomendado", expanded=False):
        st.markdown(
            """
            <div class="soft-panel">
                <div class="journey-step"><strong>1.</strong> Comparte coche hasta un parking asociado.</div>
                <div class="journey-step"><strong>2.</strong> Aplica descuento si llegan 3 o más ocupantes.</div>
                <div class="journey-step"><strong>3.</strong> Reserva una moto si el destino final queda alejado.</div>
                <div class="journey-step"><strong>4.</strong> La app registra impacto, ocupación y bonificación.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_packages(data: AppData) -> None:
    page_title("Paquetería y lockers", "Logística colaborativa ligada a rutas recurrentes y puntos verificados.")
    send, carry = st.tabs(["Enviar paquete", "Transportar paquete"])
    with send:
        with st.form("package_send"):
            c1, c2, c3 = st.columns(3)
            with c1:
                origin = st.selectbox("Origen del paquete", [x for x in data.municipalities if x != "Almussafes"])
                destination = st.selectbox("Destino", ["Área industrial de Almussafes", "Almussafes centro"])
            with c2:
                size = st.selectbox("Tamaño", ["pequeño", "mediano", "grande"])
                urgency = st.selectbox("Urgencia", ["hoy", "mañana", "esta semana"])
            with c3:
                locker = st.selectbox("Locker de entrega", data.lockers, index=3)
                price = {"pequeño": 2.0, "mediano": 3.5, "grande": 5.5}[size] + {"hoy": 1.5, "mañana": 0.8, "esta semana": 0.0}[urgency]
                st.metric("Precio estimado", f"{price:.2f} €")
            submit = st.form_submit_button("Buscar conductores")
        if submit:
            compatible = data.trips[data.trips["acepta_paquetes"]].head(6)
            for _, row in compatible.iterrows():
                st.markdown(
                    f"""
                    <div class="card-flat">
                        <div>{badge('Acepta paquetes')}{badge('Locker integrado', 'purple')}</div>
                        <div class="card-title">{row['conductor']} · {row['origen']} → Almussafes</div>
                        <p class="muted">Entrega sugerida en {locker} · Precio {price:.2f} € · Salida {row['hora_salida']}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    with carry:
        compatible = data.trips[data.trips["acepta_paquetes"]].head(8)
        for idx, (_, row) in enumerate(compatible.iterrows()):
            comp = 1.5 + min(row["distancia_km"] / 20, 3)
            st.markdown(
                f"""
                <div class="card-flat">
                    <div class="card-title">{row['origen']} → Almussafes · {row['conductor']}</div>
                    <p>Espacio: <strong>{'mediano' if row['plazas_disponibles'] >= 2 else 'pequeño'}</strong> · Compensación: <strong>{comp:.2f} €</strong></p>
                    <p class="muted">Recogida: {data.lockers[idx % len(data.lockers)]} · Entrega: Locker Almussafes Industrial</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
    st.subheader("Disponibilidad de lockers")
    st.dataframe(data.locker_activity, use_container_width=True, hide_index=True)
    st.warning("Servicio sujeto a condiciones de responsabilidad, trazabilidad, verificación de identidad y límites de contenido transportable.")


def render_driver_packages(data: AppData) -> None:
    page_title("Paquetes asignables a mi ruta", "Compensación adicional por transportar paquetes entre lockers verificados.")
    rows = pd.DataFrame(
        {
            "Locker origen": ["Locker Valencia Sur", "Locker Silla Intermodal", "Locker Torrent Avinguda"],
            "Locker destino": ["Locker Almussafes Industrial", "Locker Almussafes Industrial", "Locker Almussafes Industrial"],
            "Tamaño": ["pequeño", "mediano", "pequeño"],
            "Compensación": ["2,20 €", "3,10 €", "2,00 €"],
            "Estado": ["Disponible", "Reservado", "Disponible"],
        }
    )
    st.dataframe(rows, use_container_width=True, hide_index=True)


def render_driver_incentives(data: AppData) -> None:
    page_title("Bonificaciones del conductor", "Incentivos por ocupación, vehículo eficiente, puntualidad y paquetes.")
    cols = st.columns(4)
    with cols[0]:
        metric_card("Parking 3+", "18 €", "Acumulado mensual")
    with cols[1]:
        metric_card("Vehículo eficiente", "12 €", "Eléctrico/híbrido")
    with cols[2]:
        metric_card("Puntualidad", "96%", "Llegadas en ventana")
    with cols[3]:
        metric_card("Paquetes", "8 €", "Compensación extra")
    st.markdown("<div class='success-card'><strong>Siguiente incentivo:</strong> completa dos viajes con 3 ocupantes para desbloquear prioridad en rutas calientes.</div>", unsafe_allow_html=True)


def render_accessibility(data: AppData) -> None:
    page_title("Accesibilidad", "Preferencias de inclusión integradas en búsqueda, matching y comunicación.")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        visual = st.toggle("Activar alerta visual", value=True)
    with c2:
        transcription = st.toggle("Activar transcripción", value=True)
    with c3:
        accessible_points = st.toggle("Solo puntos accesibles", value=False)
    with c4:
        compatible = st.toggle("Conductores compatibles", value=True)

    features = [
        ("Chat transcrito", "Mensajes de conductor y pasajero disponibles como texto y confirmación visual."),
        ("Alertas visuales", "Cambios de estado destacados en tarjetas de alta visibilidad."),
        ("Puntos accesibles", "Prioridad para parkings y recogidas con itinerario accesible."),
        ("Conductores compatibles", "Filtro de conductores que aceptan movilidad reducida."),
    ]
    cols = st.columns(4)
    for idx, (title, body) in enumerate(features):
        with cols[idx]:
            feature_card(title, body, ["Accesibilidad"])
    if visual:
        st.markdown("<div class='success-card'><strong>Nuevo viaje compatible detectado:</strong> Laura P. sale desde Silla a las 07:18 con punto accesible y moto en destino.</div>", unsafe_allow_html=True)
    if transcription:
        st.info("Transcripción activa para confirmaciones, cambios de ruta y mensajes de llegada.")
    if compatible:
        df = data.trips[data.trips["accesible"]][["conductor", "origen", "hora_salida", "parking", "valoracion"]].head(10)
        st.dataframe(df, use_container_width=True, hide_index=True)
    if accessible_points:
        st.info("Se muestran únicamente Parking Almussafes Norte, Área Industrial Sur y Disuasorio Silla.")
