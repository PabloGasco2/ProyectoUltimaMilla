from __future__ import annotations
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from modules.data import AppData
from modules.logic import impact_metrics
from modules.maps import render_route_map
from modules.theme import ACCENT, AMBER, BG, BLUE, CYAN, DANGER, PANEL, PLOTLY_TEMPLATE, PRIMARY, PRIMARY_DARK, SUCCESS, TEXT
from modules.ui import badge, feature_card, metric_card, page_title


def render_tribbu_workspace(data: AppData, persona: str) -> None:
    section = st.radio(
        "Menú equipo Tribbu",
        ["Resumen", "Mapa", "Demanda", "KPIs", "Servicios", "Alertas"],
        horizontal=True,
        label_visibility="collapsed",
        key="tribbu_menu",
    )
    if section == "Resumen":
        render_executive(data)
    elif section == "Mapa":
        render_map_ops(data)
    elif section == "Demanda":
        render_supply_demand(data)
    elif section == "KPIs":
        render_impact(data)
    elif section == "Servicios":
        service = st.radio("Servicio operativo", ["Parking y motos", "Lockers"], horizontal=True, key="tribbu_services")
        if service == "Parking y motos":
            render_parking_ops(data)
        else:
            render_locker_ops(data)
    elif section == "Alertas":
        render_alerts(data)


def _apply_fig_layout(fig: go.Figure) -> go.Figure:
    fig.update_layout(PLOTLY_TEMPLATE["layout"])
    return fig


def _historical_kpis(data: AppData) -> dict[str, float]:
    daily = data.daily.copy()
    demand = data.demand.copy()
    demand["Gap"] = demand["Solicitudes"] - demand["Oferta"]
    match_rate_today = daily["matches"].iloc[-1] / daily["solicitudes"].iloc[-1] * 100
    match_rate_prev = daily["matches"].iloc[-8:-1].sum() / daily["solicitudes"].iloc[-8:-1].sum() * 100
    return {
        "solicitudes_28d": float(daily["solicitudes"].sum()),
        "matches_28d": float(daily["matches"].sum()),
        "match_rate_today": match_rate_today,
        "match_rate_delta": match_rate_today - match_rate_prev,
        "viajes_28d": float(daily["viajes"].sum()),
        "motos_28d": float(daily["motos"].sum()),
        "paquetes_28d": float(daily["paquetes"].sum()),
        "gap_total": float(demand["Gap"].sum()),
        "gap_alta": float(demand[demand["Prioridad"] == "Alta"]["Gap"].sum()),
    }


def render_executive(data: AppData) -> None:
    page_title("Vista ejecutiva de la operación", "Indicadores para gestionar la operación y el crecimiento comercial de Tribbu en Almussafes.")
    metrics = impact_metrics(data.trips)
    history = _historical_kpis(data)
    with st.expander("Indicadores esenciales", expanded=True):
        cols = st.columns(3)
        with cols[0]:
            metric_card("Viajes activos", f"{metrics['active_trips']}")
        with cols[1]:
            metric_card("Ocupación media", f"{metrics['avg_occupancy']:.1f}")
        with cols[2]:
            metric_card("Match rate", f"{metrics['matching_rate']:.0f}%")
    with st.expander("KPIs ampliados de la operación", expanded=True):
        cols = st.columns(4)
        with cols[0]:
            metric_card("Solicitudes 28d", f"{history['solicitudes_28d']:.0f}", "Demanda acumulada")
        with cols[1]:
            metric_card("Matches 28d", f"{history['matches_28d']:.0f}", "Viajes emparejados")
        with cols[2]:
            metric_card("Match hoy", f"{history['match_rate_today']:.0f}%", f"{history['match_rate_delta']:+.1f} pp vs semana previa")
        with cols[3]:
            metric_card("Gap alta prioridad", f"{history['gap_alta']:.0f}", "Solicitudes sin cubrir")
    with st.expander("Propuesta de valor", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            feature_card("Producto operativo", "Búsqueda, publicación, matching, mapa, multimodalidad y reporting en un único flujo comercializable.", ["Operación"])
        with c2:
            feature_card("Operación accionable", "Detección de franjas críticas, rutas calientes, parkings saturados y demanda no cubierta.", ["Operación"])
    hot = data.trips[data.trips["ruta_caliente"]].groupby("origen", as_index=False).agg(
        viajes=("id", "count"),
        solicitudes=("solicitudes_match", "sum"),
        ocupacion=("ocupacion_actual", "mean"),
        plazas_libres=("plazas_disponibles", "sum"),
    )
    hot = hot.sort_values("solicitudes", ascending=False).head(8)
    with st.expander("Rutas calientes", expanded=True):
        fig = px.bar(hot, x="origen", y="solicitudes", color="ocupacion", title="Rutas calientes por solicitudes", color_continuous_scale=[PRIMARY, TEXT])
        st.plotly_chart(_apply_fig_layout(fig), use_container_width=True)
        st.dataframe(
            hot.rename(columns={"origen": "Origen", "viajes": "Viajes", "solicitudes": "Solicitudes", "ocupacion": "Ocupación media", "plazas_libres": "Plazas libres"}),
            use_container_width=True,
            hide_index=True,
        )
    with st.expander("Histórico ejecutivo", expanded=False):
        daily = data.daily.copy()
        daily["match_rate"] = (daily["matches"] / daily["solicitudes"] * 100).round(1)
        fig = px.line(
            daily,
            x="fecha",
            y=["solicitudes", "matches", "viajes"],
            title="Histórico 28 días: solicitudes, matches y viajes activos",
            markers=True,
        )
        st.plotly_chart(_apply_fig_layout(fig), use_container_width=True)
        fig = px.bar(
            daily,
            x="fecha",
            y=["motos", "paquetes"],
            title="Uso histórico de servicios añadidos",
            barmode="group",
            color_discrete_sequence=[PRIMARY, TEXT],
        )
        st.plotly_chart(_apply_fig_layout(fig), use_container_width=True)
        st.dataframe(
            daily.tail(10).rename(
                columns={
                    "fecha": "Fecha",
                    "viajes": "Viajes",
                    "solicitudes": "Solicitudes",
                    "matches": "Matches",
                    "motos": "Motos",
                    "paquetes": "Paquetes",
                    "match_rate": "Match rate",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )


def render_map_ops(data: AppData) -> None:
    page_title("Mapa operativo", "Vista geográfica de rutas, parkings, hubs de moto y destino laboral.")
    c1, c2 = st.columns(2)
    with c1:
        origin = st.selectbox("Origen", ["Todos"] + [x for x in data.municipalities if x != "Almussafes"], key="tribbu_map_origin")
    with c2:
        shift = st.selectbox("Turno", ["Todos", "Turno mañana", "Turno central", "Turno tarde"], key="tribbu_map_shift")
    trips = data.trips.copy()
    if origin != "Todos":
        trips = trips[trips["origen"] == origin]
    if shift != "Todos":
        trips = trips[trips["turno"] == shift]
    render_route_map(trips, data.municipalities, data.parkings, data.moto_hubs, map_key=f"tribbu_route_map_{origin}_{shift}_{len(trips)}")


def render_supply_demand(data: AppData) -> None:
    page_title("Demanda y oferta", "Priorización de municipios donde Tribbu debe activar campañas o incentivos.")
    demand = data.demand.copy()
    demand["Gap"] = demand["Solicitudes"] - demand["Oferta"]
    demand["Cobertura"] = (demand["Oferta"] / demand["Solicitudes"] * 100).round(0)
    by_city = demand.groupby("Municipio", as_index=False).agg(
        Solicitudes=("Solicitudes", "sum"),
        Oferta=("Oferta", "sum"),
        Gap=("Gap", "sum"),
        Cobertura=("Cobertura", "mean"),
    )
    with st.expander("Resumen de cobertura", expanded=True):
        cols = st.columns(2)
        with cols[0]:
            metric_card("Gap operativo", f"{demand['Gap'].sum()}")
        with cols[1]:
            metric_card("Cobertura media", f"{demand['Cobertura'].mean():.0f}%")
    with st.expander("Comparativa por municipio", expanded=True):
        fig = go.Figure()
        fig.add_trace(go.Bar(name="Solicitudes", x=by_city["Municipio"], y=by_city["Solicitudes"], marker_color=PRIMARY))
        fig.add_trace(go.Bar(name="Oferta", x=by_city["Municipio"], y=by_city["Oferta"], marker_color=ACCENT))
        fig.update_layout(title="Comparativa demanda-oferta", barmode="group")
        st.plotly_chart(_apply_fig_layout(fig), use_container_width=True)
        st.dataframe(demand.sort_values("Gap", ascending=False), use_container_width=True, hide_index=True)
    with st.expander("Mapa de calor por turno", expanded=False):
        heat = demand.pivot(index="Municipio", columns="Turno", values="Gap").fillna(0)
        fig = px.imshow(heat, text_auto=True, title="Gap por municipio y turno", color_continuous_scale=[PANEL, PRIMARY, TEXT], aspect="auto")
        st.plotly_chart(_apply_fig_layout(fig), use_container_width=True)
    with st.expander("Recomendaciones", expanded=False):
        recs = [
            ("Torrent", "Activar incentivo conductor 06:45-07:30", "Gap alto y demanda recurrente."),
            ("Gandía", "Crear campaña específica para turnos tempranos", "Trayecto largo con baja oferta."),
            ("Valencia", "Promocionar puntos de recogida Valencia Sur", "Volumen alto y alta elasticidad de precio."),
        ]
        for route, action, reason in recs:
            feature_card(route, f"{action}. {reason}", ["Recomendación"])


def render_impact(data: AppData) -> None:
    page_title("Impacto y KPIs", "Dashboard para medir adopción, eficiencia y sostenibilidad de la operación.")
    metrics = impact_metrics(data.trips)
    history = _historical_kpis(data)
    daily = data.daily.copy()
    daily["match_rate"] = (daily["matches"] / daily["solicitudes"] * 100).round(1)
    passenger_success = data.passengers["estado"].isin(["Confirmado", "Match propuesto"]).mean() * 100
    driver_success = (data.trips["plazas_reservadas"] > 0).mean() * 100
    avg_passengers_vehicle = data.trips["plazas_reservadas"].mean()
    with st.expander("KPIs principales", expanded=True):
        cols = st.columns(3)
        with cols[0]:
            metric_card("Pasajeros con trayecto", f"{passenger_success:.0f}%", "Confirmados o con match propuesto")
        with cols[1]:
            metric_card("Conductores con pasajeros", f"{driver_success:.0f}%", "Rutas publicadas con al menos una reserva")
        with cols[2]:
            metric_card("Media pasajeros/vehículo", f"{avg_passengers_vehicle:.1f}", "Pasajeros reservados por coche")
        cols = st.columns(4)
        with cols[0]:
            metric_card("Viajes 28d", f"{history['viajes_28d']:.0f}")
        with cols[1]:
            metric_card("Motos 28d", f"{history['motos_28d']:.0f}")
        with cols[2]:
            metric_card("Paquetes 28d", f"{history['paquetes_28d']:.0f}")
        with cols[3]:
            metric_card("Gap total", f"{history['gap_total']:.0f}", "Demanda no cubierta")
    with st.expander("Sostenibilidad", expanded=True):
        co2 = data.trips.groupby("origen", as_index=False)["co2_evitado"].sum().sort_values("co2_evitado", ascending=False).head(10)
        fig = px.bar(co2, x="origen", y="co2_evitado", title="CO2 reducido por ruta", color="co2_evitado", color_continuous_scale=[PRIMARY, TEXT])
        st.plotly_chart(_apply_fig_layout(fig), use_container_width=True)
    with st.expander("Evolución de la operación", expanded=False):
        fig = px.line(data.daily, x="fecha", y=["solicitudes", "matches"], title="Evolución de solicitudes y matches", markers=True)
        st.plotly_chart(_apply_fig_layout(fig), use_container_width=True)
    with st.expander("Histórico ampliado de KPIs", expanded=True):
        fig = px.line(daily, x="fecha", y=["solicitudes", "matches", "viajes"], title="Evolución de solicitudes, matches y viajes", markers=True)
        st.plotly_chart(_apply_fig_layout(fig), use_container_width=True)
        fig = px.line(daily, x="fecha", y=["match_rate"], title="Histórico de tasa de match", markers=True)
        st.plotly_chart(_apply_fig_layout(fig), use_container_width=True)
        st.dataframe(daily.tail(14), use_container_width=True, hide_index=True)
    with st.expander("KPIs por turno y prioridad", expanded=False):
        demand = data.demand.copy()
        demand["Gap"] = demand["Solicitudes"] - demand["Oferta"]
        demand["Cobertura"] = (demand["Oferta"] / demand["Solicitudes"] * 100).round(0)
        by_shift = demand.groupby("Turno", as_index=False).agg(
            Solicitudes=("Solicitudes", "sum"),
            Oferta=("Oferta", "sum"),
            Gap=("Gap", "sum"),
            Cobertura=("Cobertura", "mean"),
        )
        fig = px.bar(by_shift, x="Turno", y=["Solicitudes", "Oferta", "Gap"], title="Demanda, oferta y gap por turno", barmode="group", color_discrete_sequence=[TEXT, PRIMARY, AMBER])
        st.plotly_chart(_apply_fig_layout(fig), use_container_width=True)
        st.dataframe(by_shift, use_container_width=True, hide_index=True)
    with st.expander("Mix operativo", expanded=False):
        vehicle = data.trips["tipo_coche"].value_counts().reset_index()
        vehicle.columns = ["Tipo", "Cantidad"]
        fig = px.pie(vehicle, names="Tipo", values="Cantidad", title="Mix de vehículos", color_discrete_sequence=[TEXT, PRIMARY, "#D88BCB", "#8B8B92"])
        st.plotly_chart(_apply_fig_layout(fig), use_container_width=True)
        parking = pd.DataFrame(
            [{"Parking": name, "Ocupación": info["ocupacion"], "Motos": info["motos"]} for name, info in data.parkings.items()]
        )
        fig = px.scatter(parking, x="Ocupación", y="Motos", size="Motos", color="Parking", title="Relación parking-motos", color_discrete_sequence=[TEXT, PRIMARY, "#D88BCB", "#8B8B92"])
        st.plotly_chart(_apply_fig_layout(fig), use_container_width=True)
    st.markdown(
        """
        <div class="soft-panel">
            <div class="card-title">Objetivo operativo recomendado</div>
            <p>Alcanzar ocupación media igual o superior a 3 personas por vehículo, tasa de matching superior al 60% y cobertura de oferta mínima del 70% en rutas calientes.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_parking_ops(data: AppData) -> None:
    page_title("Operación parking + motos", "Control de ocupación, disponibilidad y bonificaciones multimodales.")
    rows = pd.DataFrame(
        [
            {
                "Parking": name,
                "Plazas libres": info["plazas_libres"],
                "Ocupación": info["ocupacion"],
                "Descuento 3+": info["descuento"],
                "Motos": info["motos"],
                "Estado": info["estado"],
                "Accesible": info["accesible"],
            }
            for name, info in data.parkings.items()
        ]
    )
    with st.expander("Disponibilidad de parkings", expanded=True):
        st.dataframe(rows, use_container_width=True, hide_index=True)
    with st.expander("Ocupación", expanded=True):
        fig = px.bar(rows, x="Parking", y="Ocupación", color="Ocupación", title="Ocupación de parkings", color_continuous_scale=[PRIMARY, TEXT])
        st.plotly_chart(_apply_fig_layout(fig), use_container_width=True)
    with st.expander("Hubs de moto", expanded=False):
        hubs = pd.DataFrame([{"Hub": k, **v} for k, v in data.moto_hubs.items()])
        fig = px.bar(hubs, x="Hub", y="motos_disponibles", color="bateria", title="Motos disponibles por hub y batería media", color_continuous_scale=[PRIMARY, TEXT])
        st.plotly_chart(_apply_fig_layout(fig), use_container_width=True)
        st.dataframe(
            hubs[["Hub", "zona", "motos_totales", "motos_disponibles", "reservadas", "mantenimiento", "bateria", "sla_reposicion"]],
            use_container_width=True,
            hide_index=True,
        )


def render_locker_ops(data: AppData) -> None:
    page_title("Lockers y logística colaborativa", "Control de trazabilidad, compensación y puntos de intercambio.")
    rows = data.locker_activity.copy()
    rows["Ocupación"] = ((rows["Capacidad"] - rows["Huecos libres"]) / rows["Capacidad"] * 100).round(0)
    with st.expander("Disponibilidad de lockers", expanded=True):
        st.dataframe(rows, use_container_width=True, hide_index=True)
    with st.expander("Actividad", expanded=True):
        fig = px.bar(rows, x="Locker", y=["Paquetes entrantes", "Paquetes salientes"], title="Actividad de lockers", barmode="group", color_discrete_sequence=[TEXT, PRIMARY])
        st.plotly_chart(_apply_fig_layout(fig), use_container_width=True)
    with st.expander("Ocupación", expanded=False):
        fig = px.bar(rows, x="Locker", y="Ocupación", color="Ocupación", title="Ocupación de lockers", color_continuous_scale=[PRIMARY, TEXT])
        st.plotly_chart(_apply_fig_layout(fig), use_container_width=True)
    st.warning("El servicio de paquetería opera con términos legales, trazabilidad, verificación de identidad y límites de contenido.")


def render_alerts(data: AppData) -> None:
    page_title("Alertas operativas", "Señales accionables para gestionar la red en tiempo real.")
    alerts = [
        ("Alta demanda desde Torrent entre 6:45 y 7:30.", "warning", "Incentivar conductores con salida desde Torrent."),
        ("Baja disponibilidad de plazas desde Gandía.", "error", "Crear campaña de captación en empresas con turno temprano."),
        ("Parking Almussafes Norte cerca del límite de ocupación.", "warning", "Derivar rutas nuevas hacia Área Industrial Sur."),
        ("Ruta Silla-Almussafes con alta tasa de matching.", "success", "Mantener bonificación y ampliar comunicación."),
        ("Usuarios con necesidad de accesibilidad concentrados en Catarroja.", "info", "Priorizar puntos accesibles y conductores compatibles."),
    ]
    for message, level, action in alerts:
        if level == "error":
            st.error(message)
        elif level == "warning":
            st.warning(message)
        elif level == "success":
            st.success(message)
        else:
            st.info(message)
        st.markdown(f"<div class='card-flat'><strong>Acción recomendada:</strong> {action}</div>", unsafe_allow_html=True)
    st.subheader("Conductores mejor valorados")
    top = data.trips.sort_values(["valoracion", "ocupacion_actual"], ascending=False)[["conductor", "origen", "valoracion", "ocupacion_actual", "tipo_coche"]].head(10)
    st.dataframe(top, use_container_width=True, hide_index=True)
