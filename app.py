from __future__ import annotations

import math
import zipfile
from io import BytesIO
from xml.sax.saxutils import escape

import pandas as pd
import streamlit as st

from config import DIAS_MES, HUB, POSTCODE, config_default
from datos_geo import cargar_portales_46007
from mapa import pintar_mapa
from simulacion import (
    desglose_costes_df,
    desglose_energia_df,
    eventos_vehiculos_df,
    optimizar_mes,
    productividad_personas_df,
    resumen_kpis_df,
    resumen_cargas_hub_df,
    resumen_diario_df,
    resumen_flota_df,
    resumen_personas_dia_df,
    resumen_personas_hora_df,
    resumen_pedidos_df,
    resumen_traspasos_df,
    resumen_vehiculos_df,
)


st.set_page_config(page_title="Simulador Encicle 46007", layout="wide")


def dinero(valor: float) -> str:
    return f"{valor:,.0f} EUR".replace(",", ".")


def pct(valor: float) -> str:
    return f"{valor:.1f}%"


def tabla(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    salida = df.copy()
    for col in salida.select_dtypes(include=["float", "float64", "float32"]).columns:
        salida[col] = salida[col].round(2)
    return salida


def selector_dia(resultado: dict, key: str, etiqueta: str = "Dia operativo") -> int:
    dias = [d["dia"] for d in resultado["diarios"] if d["laborable"]]
    idx_key = f"{key}_idx"
    if idx_key not in st.session_state:
        st.session_state[idx_key] = 0
    st.session_state[idx_key] = max(0, min(st.session_state[idx_key], len(dias) - 1))
    c1, c2, c3 = st.columns([1, 2, 1])
    if c1.button("-", key=f"{key}_menos", use_container_width=True):
        st.session_state[idx_key] = max(0, st.session_state[idx_key] - 1)
    if c3.button("+", key=f"{key}_mas", use_container_width=True):
        st.session_state[idx_key] = min(len(dias) - 1, st.session_state[idx_key] + 1)
    dia = dias[st.session_state[idx_key]]
    c2.markdown(
        f"<div style='border:1px solid #d1d5db;border-radius:6px;padding:7px 10px;text-align:center;background:#f8fafc'>"
        f"<span style='font-size:12px;color:#64748b'>{etiqueta}</span><br><strong>Dia {dia}</strong></div>",
        unsafe_allow_html=True,
    )
    return dia


def init_state():
    if "cfg" not in st.session_state:
        st.session_state.cfg = config_default()
    if "resultado" not in st.session_state:
        st.session_state.resultado = None


def panel_manual():
    st.subheader("Manual de uso")
    st.write(
        "Esta app simula un mes operativo de reparto de Encicle en el codigo postal 46007 de Valencia. "
        "El objetivo es recomendar una flota y una operativa que minimicen coste, manteniendo el Scorecard minimo configurado."
    )
    st.markdown(
        """
**Flujo recomendado**
1. Entra en **Configuracion** y revisa demanda, servicio, hub, vehiculos, velocidades y preferencias.
2. Pulsa **Simular y optimizar mes**. La app carga portales reales del CP 46007 y evalua flotas candidatas.
3. Revisa **Simulacion mensual** para ver entregas, pendientes, flota recomendada, horas y resumen diario.
4. En **Pedidos y traspasos** consulta cada pedido entregado, su repartidor, vehiculo, origen de carga y SLA.
5. En **Vehiculos** revisa la evolucion de carga P/M y XL despues de cada entrega, carga o traspaso.
6. En **Personas** comprueba horas trabajadas, descansos y ocupacion de cada persona.
7. En **Mapa de rutas** visualiza rutas, traspasos, cargas en hub y vueltas reales al hub.
8. En **Economia y KPI** revisa balance, energia, cargas, coste por paquete y KPIs de servicio.
9. En **Exportacion** marca las tablas que quieres y descarga un Excel con una hoja por tabla.
"""
    )
    st.info(
        "Los tiempos de trabajo se calculan en horas y minutos reales. "
        "Si una persona supera 5h, la app registra descanso; la pausa operativa 15-16h se respeta en la simulacion."
    )
    st.caption(
        "El modo rapido esta pensado para Render gratuito: evita recalculos pesados y reserva el trazado calle a calle para el dia visible en el mapa."
    )


def panel_configuracion():
    cfg = st.session_state.cfg
    st.subheader("Configuracion operativa")
    st.info(
        f"Zona fija: codigo postal {POSTCODE}. Hub fijo: {HUB['nombre']} "
        f"({HUB['lat']:.5f}, {HUB['lon']:.5f})."
    )
    c1, c2, c3 = st.columns(3)
    cfg["demanda_min"] = c1.number_input("Paquetes/dia minimo", 250, 800, int(cfg["demanda_min"]))
    cfg["demanda_max"] = c2.number_input("Paquetes/dia maximo", 250, 900, int(cfg["demanda_max"]))
    cfg["ratio_urgente"] = c3.slider("Urgentes", 0.0, 0.5, float(cfg["ratio_urgente"]), 0.01)

    c1, c2, c3 = st.columns(3)
    cfg["ratio_sobre"] = c1.slider("Sobres", 0.0, 1.0, float(cfg["ratio_sobre"]), 0.01)
    cfg["ratio_pm"] = c2.slider("P/M", 0.0, 1.0, float(cfg["ratio_pm"]), 0.01)
    cfg["ratio_xl"] = c3.slider("XL", 0.0, 1.0, float(cfg["ratio_xl"]), 0.01)
    total = cfg["ratio_sobre"] + cfg["ratio_pm"] + cfg["ratio_xl"]
    if abs(total - 1) > 0.01:
        st.warning("La suma de tipos de paquete deberia ser 100%.")

    st.subheader("Servicio, hub y KPI")
    c1, c2, c3, c4 = st.columns(4)
    cfg["prob_fallo_1"] = c1.slider("Prob. fallo primera entrega", 0.0, 0.15, float(cfg["prob_fallo_1"]), 0.005)
    cfg["score_digitalizacion"] = c2.slider("Digitalizacion", 0.0, 100.0, float(cfg["score_digitalizacion"]), 1.0)
    cfg["objetivo_gls"] = c3.slider("Objetivo Scorecard Encicle", 80.0, 100.0, float(cfg["objetivo_gls"]), 0.5)
    cfg["semilla"] = c4.number_input("Semilla simulacion", 1, 99999, int(cfg["semilla"]))

    c1, c2, c3, c4 = st.columns(4)
    cfg["alquiler_m2"] = c1.number_input("Alquiler hub EUR/m2", 8.0, 30.0, float(cfg["alquiler_m2"]), 0.5)
    cfg["m2_hub"] = c2.number_input("Tamano hub m2", 40, 150, int(cfg["m2_hub"]))
    cfg["capacidad_hub"] = c3.number_input("Capacidad hub paquetes", 500, 10000, int(cfg["capacidad_hub"]), 100)
    cfg["modo_optimizacion"] = c4.selectbox("Modo optimizacion", ["rapido", "equilibrado", "preciso"], index=["rapido", "equilibrado", "preciso"].index(cfg["modo_optimizacion"]))

    cfg["usar_traspaso_furgoneta"] = st.toggle(
        "Permitir traspaso de paquetes desde furgoneta nodriza a riders",
        value=bool(cfg.get("usar_traspaso_furgoneta", True)),
        help="Si esta activo, la furgoneta puede aprovisionar a bicis, triciclos, remolques y andarines durante la ruta. Si esta desactivado, cada repartidor carga solo en el hub.",
    )
    c1, c2, c3 = st.columns(3)
    cfg["modo_productividad"] = c1.selectbox(
        "Calculo de productividad",
        ["rango", "ruta_distancia"],
        index=["rango", "ruta_distancia"].index(cfg.get("modo_productividad", "rango")),
        help="rango usa paquetes/hora por vehiculo. ruta_distancia calcula distancia, velocidad y tiempo de entrega, respetando tambien el maximo de entregas/hora.",
    )
    cfg["tiempo_entrega_min"] = c2.number_input("Min/entrega no furgoneta", 0.2, 10.0, float(cfg.get("tiempo_entrega_min", 1.0)), 0.1)
    cfg["tiempo_entrega_furgoneta_min"] = c3.number_input("Min/entrega furgoneta", 0.2, 12.0, float(cfg.get("tiempo_entrega_furgoneta_min", 2.0)), 0.1)

    with st.expander("Vehiculos y parametros editables"):
        for clave, spec in cfg["vehiculos"].items():
            st.markdown(f"**{spec['nombre']}**")
            c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
            spec["alquiler_mes"] = c1.number_input(f"Alquiler {clave}", 0.0, 2000.0, float(spec["alquiler_mes"]), 10.0)
            spec["energia_100km"] = c2.number_input(f"EUR/100km {clave}", 0.0, 10.0, float(spec["energia_100km"]), 0.05)
            spec["productividad_min"] = c3.number_input(f"Prod min {clave}", 1, 40, int(spec["productividad_min"]))
            spec["productividad_max"] = c4.number_input(f"Prod max {clave}", 1, 45, int(spec["productividad_max"]))
            spec["cap_pm"] = c5.number_input(f"Cap P/M {clave}", 0, 200, int(spec["cap_pm"]))
            spec["velocidad_kmh"] = c6.number_input(f"Vel. media km/h {clave}", 1.0, 80.0, float(spec["velocidad_kmh"]), 0.5)
            spec["preferencia"] = c7.select_slider(
                f"Preferencia {clave}",
                options=[1, 2, 3, 4, 5],
                value=int(spec.get("preferencia", 3)),
                format_func=lambda v: "★" * v + "☆" * (5 - v),
                help="1 penaliza este vehiculo en la optimizacion; 5 lo favorece si cumple coste y servicio.",
            )

    c1, c2 = st.columns([1, 4])
    if c1.button("Restaurar valores"):
        st.session_state.cfg = config_default()
        st.rerun()
    if c2.button("Simular y optimizar mes", type="primary", use_container_width=True):
        with st.spinner("Cargando portales reales del CP 46007..."):
            portales = cargar_portales_46007()
        barra = st.progress(0.0)

        def progreso(v):
            barra.progress(v)

        with st.spinner("Optimizando flota y simulando mes tipo..."):
            st.session_state.resultado = optimizar_mes(portales, cfg, progreso)
        barra.progress(1.0)
        st.success("Simulacion completada.")


def panel_resumen():
    resultado = st.session_state.resultado
    if not resultado:
        st.info("Ejecuta la simulacion desde Configuracion.")
        return
    cfg = st.session_state.cfg
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Scorecard Encicle", pct(resultado["score"]))
    c2.metric("Beneficio mensual", dinero(resultado["beneficio"]))
    c3.metric("Coste mensual", dinero(resultado["coste_total"]))
    c4.metric("Ingresos", dinero(resultado["ingresos"]))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Entregas", f"{resultado['entregados']:,}".replace(",", "."))
    c2.metric("Tasa entrega total", pct(resultado.get("tasa_entrega_total", 0)))
    c3.metric("SLA urgente", pct(resultado["kpis"]["sla"]))
    c4.metric("Traspasos furgoneta", f"{len(resultado['traspasos']):,}".replace(",", "."))
    c1, c2, c3 = st.columns(3)
    c1.metric("Pico repartidores/dia", resultado.get("pico_trabajadores_reparto", 0))
    c2.metric("Utilizacion personal", pct(resultado.get("utilizacion_personal_global", 0)))
    c3.metric("Horas trabajadas reparto", f"{resultado.get('horas_pagadas_reparto_total', 0):.2f}")
    if resultado.get("rutas_sobre_8h", 0):
        st.warning(f"Hay {resultado['rutas_sobre_8h']} rutas estimadas por encima de 8h. Revisa flota o modo de productividad.")

    st.subheader("Flota mensual recomendada")
    st.dataframe(tabla(resumen_flota_df(resultado, cfg)), use_container_width=True, hide_index=True)

    st.subheader("Resumen diario")
    df = resumen_diario_df(resultado)
    st.dataframe(tabla(df), use_container_width=True, hide_index=True)
    st.line_chart(df[df["laborable"]][["paquetes_disponibles", "urgentes_disponibles", "entregados", "pendientes"]])

    st.subheader("Detalle del dia")
    dia_detalle = selector_dia(resultado, "dia_resumen_mensual", "Dia a revisar")
    detalle_dia = df[df["dia"] == dia_detalle]
    if not detalle_dia.empty:
        st.dataframe(tabla(detalle_dia), use_container_width=True, hide_index=True)
    rutas_dia = resultado["rutas_por_dia"].get(dia_detalle, [])
    if rutas_dia:
        filas_rutas = [
            {
                "vehiculo": r["vehiculo"],
                "persona": r["trabajador"],
                "paradas": len(r["paradas"]),
                "km": r["km"],
                "horas_trabajadas": r.get("horas_pagadas", r["horas"]),
                "inicio": r.get("turno_inicio", "08:00"),
                "fin": r.get("turno_fin", r.get("fin_operativo_txt", "")),
                "descanso": r.get("descanso", ""),
                "recargas_paquetes": r.get("recargas_paquetes", 0),
            }
            for r in rutas_dia
        ]
        st.dataframe(tabla(pd.DataFrame(filas_rutas)), use_container_width=True, hide_index=True)

    st.subheader("Equipo operativo")
    st.write(", ".join(resultado["trabajadores"]))
    estrategia = "con furgoneta nodriza" if cfg.get("usar_traspaso_furgoneta", True) else "sin traspasos, carga solo en hub"
    st.caption(f"Estrategia: {estrategia}. Candidatos de flota evaluados: {resultado['evaluados']}. Mes tipo de {DIAS_MES} dias empezando en lunes; se opera de lunes a viernes.")


def panel_pedidos_traspasos():
    resultado = st.session_state.resultado
    if not resultado:
        st.info("Ejecuta la simulacion para consultar pedidos y traspasos.")
        return

    dia = selector_dia(resultado, "dia_tabla_pedidos")

    st.subheader("Resumen de pedidos entregados")
    st.caption(
        "Cada fila representa un pedido cobrado: repartidor, vehiculo, hora real de entrega, "
        "si salio del hub o si se cargo por traspaso desde furgoneta, SLA e intento."
    )
    pedidos_df = resumen_pedidos_df(resultado, dia)
    st.dataframe(tabla(pedidos_df), use_container_width=True, hide_index=True)

    st.subheader("Traspasos desde furgoneta")
    st.caption("Eventos de aprovisionamiento: hora, vehiculo receptor, ubicacion y paquetes P/M transferidos. Los XL permanecen en furgoneta.")
    traspasos_df = resumen_traspasos_df(resultado, dia)
    if traspasos_df.empty:
        st.info("No hubo traspasos este dia. Los repartidores cargaron en el hub o la opcion estaba desactivada.")
    else:
        st.dataframe(tabla(traspasos_df), use_container_width=True, hide_index=True)

    st.subheader("Cargas en hub")
    st.caption("Incluye la carga inicial de cada vehiculo y las recargas durante el dia, incluidas las cargas de furgoneta nodriza antes de un traspaso.")
    cargas_df = resumen_cargas_hub_df(resultado, dia)
    if cargas_df.empty:
        st.info("No hay cargas de hub registradas para este dia.")
    else:
        st.dataframe(tabla(cargas_df), use_container_width=True, hide_index=True)


def panel_mapa():
    resultado = st.session_state.resultado
    if not resultado:
        st.info("Ejecuta la simulacion para ver rutas.")
        return
    cfg = st.session_state.cfg
    with st.spinner("Cargando portales 46007 y preparando mapa..."):
        portales = cargar_portales_46007()

    dia = selector_dia(resultado, "dia_mapa", "Dia a visualizar")
    rutas = resultado["rutas_por_dia"].get(dia, [])
    opciones = {r["vehiculo"]: r["vehiculo_id"] for r in rutas}
    seleccion = st.multiselect("Vehiculos visibles", list(opciones.keys()), default=list(opciones.keys()))
    visibles = [opciones[n] for n in seleccion]
    c1, c2 = st.columns(2)
    cfg["vista_mapa"] = c1.selectbox("Vista", ["claro", "satelite"], index=0 if cfg["vista_mapa"] == "claro" else 1)
    usar_red_real = c2.toggle(
        "Trazar sobre red viaria real",
        value=False,
        help="Desactivado por defecto para que el mapa cargue al instante. Activalo para recalcular trazados calle a calle con OSMnx.",
    )
    st.caption("El mapa rapido aparece automaticamente. Si activas red viaria real, se recalculan las rutas con OSMnx y puede tardar mas en Render gratuito.")
    with st.spinner("Dibujando mapa de rutas..."):
        pintar_mapa(portales, resultado, dia, visibles, cfg["vista_mapa"], usar_red_real)

    rows = []
    for r in rutas:
        rows.append(
            {
                "vehiculo": r["vehiculo"],
                "repartidor": r["trabajador"],
                "paradas": len(r["paradas"]),
                "max_repartos_dia": r.get("max_repartos_dia", ""),
                "km": round(r["km"], 2),
                "recargas_paquetes": r["recargas_paquetes"],
                "horas": round(r["horas"], 2),
                "horas_trabajadas": round(r.get("horas_pagadas", r["horas"]), 2),
            }
        )
    st.dataframe(tabla(pd.DataFrame(rows)), use_container_width=True, hide_index=True)


def panel_vehiculos():
    resultado = st.session_state.resultado
    if not resultado:
        st.info("Ejecuta la simulacion para consultar vehiculos.")
        return
    cfg = st.session_state.cfg
    dia = selector_dia(resultado, "dia_vehiculos")

    st.subheader("Resumen mensual por vehiculo")
    st.caption("Datos propios de cada unidad: kilometros, energia, cargas de bateria, cargas de paquetes y traspasos.")
    vehiculos_df = resumen_vehiculos_df(resultado, cfg)
    st.dataframe(tabla(vehiculos_df), use_container_width=True, hide_index=True)

    if vehiculos_df.empty:
        return
    vehiculo_label = st.selectbox("Ver evolucion de una unidad", vehiculos_df["vehiculo"].tolist())
    vehiculo_id = vehiculos_df.loc[vehiculos_df["vehiculo"] == vehiculo_label, "vehiculo_id"].iloc[0]
    eventos_df = eventos_vehiculos_df(resultado, dia, vehiculo_id)
    st.subheader("Evolucion de carga tras cada evento")
    st.caption("La carga nunca supera la capacidad registrada. P/M y XL se controlan por separado; las entregas, hub y traspasos dejan inventario antes/despues.")
    st.dataframe(tabla(eventos_df), use_container_width=True, hide_index=True)

    st.subheader("Todos los eventos del dia")
    st.dataframe(tabla(eventos_vehiculos_df(resultado, dia)), use_container_width=True, hide_index=True)


def panel_personas():
    resultado = st.session_state.resultado
    if not resultado:
        st.info("Ejecuta la simulacion para consultar personas.")
        return
    dia = selector_dia(resultado, "dia_personas")

    st.subheader("Jornada por persona")
    st.caption("Las horas se calculan con horas y minutos reales. El hub se modela con 1 trabajador fijo diario.")
    personas_df = resumen_personas_dia_df(resultado, dia)
    if not personas_df.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("Personas operativas", len(personas_df))
        c2.metric("Horas operativas", f"{personas_df['horas_operativas'].sum():.1f}")
        c3.metric("Utilizacion jornada", f"{personas_df['horas_operativas'].sum() / max(0.01, personas_df['horas_trabajadas'].sum()) * 100:.1f}%")
    st.dataframe(tabla(personas_df), use_container_width=True, hide_index=True)

    st.subheader("Actividad por horas")
    st.caption("Resumen horario de kilometros, repartos, cargas y traspasos por persona.")
    st.dataframe(tabla(resumen_personas_hora_df(resultado, dia)), use_container_width=True, hide_index=True)


def panel_economia_kpi():
    resultado = st.session_state.resultado
    if not resultado:
        st.info("Ejecuta la simulacion desde Configuracion.")
        return
    cfg = st.session_state.cfg
    st.subheader("Balance economico")
    st.caption("Los costes se muestran en positivo. Los ingresos aparecen como partida separada para que el margen quede claro.")
    st.dataframe(tabla(desglose_costes_df(resultado, cfg)), use_container_width=True, hide_index=True)

    st.subheader("Energia y cargas por vehiculo")
    st.caption("Desglose operativo de km, coste de energia por 100 km, cargas de bateria y coste asociado por unidad.")
    st.dataframe(tabla(desglose_energia_df(resultado, cfg)), use_container_width=True, hide_index=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Coste/paquete", f"{resultado['coste_total'] / max(1, resultado['entregados']):.2f} EUR")
    c2.metric("Ingreso/paquete", f"{resultado['ingresos'] / max(1, resultado['entregados']):.2f} EUR")
    c3.metric("Km totales", f"{resultado['km_total']:.1f}")
    c4.metric("Energia EUR estimada", f"{resultado['coste_energia']:.2f}")

    st.subheader("Scorecard Encicle")
    kpis = resultado["kpis"]
    kpi_df = pd.DataFrame(
        [
            {"KPI": "Efectividad 1a entrega", "Peso": "40%", "Valor": kpis["efectividad"]},
            {"KPI": "Cumplimiento ventana SLA urgente", "Peso": "30%", "Valor": kpis["sla"]},
            {"KPI": "Digitalizacion y trazabilidad", "Peso": "20%", "Valor": kpis["digitalizacion"]},
            {"KPI": "Ratio emisiones cero", "Peso": "10%", "Valor": kpis["cero_emisiones"]},
        ]
    )
    st.dataframe(tabla(kpi_df), use_container_width=True, hide_index=True)
    st.subheader("KPIs operativos ampliados")
    st.dataframe(tabla(resumen_kpis_df(resultado, cfg)), use_container_width=True, hide_index=True)
    st.subheader("Productividad por persona")
    st.caption("Paquetes entregados por hora trabajada, kilometros y actividad mensual por repartidor.")
    st.dataframe(tabla(productividad_personas_df(resultado)), use_container_width=True, hide_index=True)
    color = "green" if resultado["score"] >= cfg["objetivo_gls"] else "red"
    st.markdown(f"<h2 style='color:{color}'>Score final: {resultado['score']:.1f}%</h2>", unsafe_allow_html=True)
    if resultado["score"] >= cfg["objetivo_gls"]:
        st.success("La flota recomendada cumple la restriccion minima Encicle y minimiza coste entre los candidatos evaluados.")
    else:
        st.error("No se encontro una flota que alcance el objetivo Encicle con los limites actuales.")


def panel_incidencias():
    resultado = st.session_state.resultado
    if not resultado:
        st.info("Ejecuta la simulacion desde Configuracion.")
        return
    st.subheader("Incidencias simuladas")
    if not resultado["incidencias"]:
        st.success("No se han registrado incidencias relevantes.")
        return
    st.dataframe(tabla(pd.DataFrame(resultado["incidencias"])), use_container_width=True, hide_index=True)


def tablas_exportables(resultado: dict, cfg: dict) -> dict[str, pd.DataFrame]:
    return {
        "Resumen diario": resumen_diario_df(resultado),
        "Flota mensual": resumen_flota_df(resultado, cfg),
        "Pedidos entregados": resumen_pedidos_df(resultado),
        "Traspasos": resumen_traspasos_df(resultado),
        "Cargas hub": resumen_cargas_hub_df(resultado),
        "Vehiculos": resumen_vehiculos_df(resultado, cfg),
        "Eventos vehiculos": eventos_vehiculos_df(resultado),
        "Personas dia": resumen_personas_dia_df(resultado),
        "Personas hora": resumen_personas_hora_df(resultado),
        "Productividad personas": productividad_personas_df(resultado),
        "Costes": desglose_costes_df(resultado, cfg),
        "Energia y cargas": desglose_energia_df(resultado, cfg),
        "KPIs": resumen_kpis_df(resultado, cfg),
        "Incidencias": pd.DataFrame(resultado.get("incidencias", [])),
    }


def crear_excel(tablas: dict[str, pd.DataFrame]) -> bytes:
    buffer = BytesIO()
    nombres = [nombre[:31] for nombre in tablas]
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _xlsx_content_types(len(tablas)))
        zf.writestr("_rels/.rels", _xlsx_root_rels())
        zf.writestr("xl/workbook.xml", _xlsx_workbook(nombres))
        zf.writestr("xl/_rels/workbook.xml.rels", _xlsx_workbook_rels(len(tablas)))
        for idx, df in enumerate(tablas.values(), start=1):
            zf.writestr(f"xl/worksheets/sheet{idx}.xml", _xlsx_sheet(tabla(df)))
    return buffer.getvalue()


def _xlsx_col(idx: int) -> str:
    letras = ""
    while idx:
        idx, rem = divmod(idx - 1, 26)
        letras = chr(65 + rem) + letras
    return letras


def _xlsx_cell(ref: str, value) -> str:
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))) or pd.isna(value):
        return f'<c r="{ref}"/>'
    if isinstance(value, bool):
        return f'<c r="{ref}" t="b"><v>{1 if value else 0}</v></c>'
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f'<c r="{ref}"><v>{value}</v></c>'
    text = escape(str(value))
    return f'<c r="{ref}" t="inlineStr"><is><t>{text}</t></is></c>'


def _xlsx_sheet(df: pd.DataFrame) -> str:
    df = df if df is not None else pd.DataFrame()
    headers = list(df.columns)
    rows_xml = []
    all_rows = [headers] + df.astype(object).where(pd.notnull(df), None).values.tolist()
    for r_idx, row in enumerate(all_rows, start=1):
        cells = []
        for c_idx, value in enumerate(row, start=1):
            cells.append(_xlsx_cell(f"{_xlsx_col(c_idx)}{r_idx}", value))
        rows_xml.append(f'<row r="{r_idx}">{"".join(cells)}</row>')
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' + "".join(rows_xml) + "</sheetData></worksheet>"


def _xlsx_content_types(num_sheets: int) -> str:
    sheets = "".join(
        f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for i in range(1, num_sheets + 1)
    )
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>' + sheets + "</Types>"


def _xlsx_root_rels() -> str:
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'


def _xlsx_workbook(nombres: list[str]) -> str:
    sheets = "".join(
        f'<sheet name="{escape(nombre)}" sheetId="{idx}" r:id="rId{idx}"/>'
        for idx, nombre in enumerate(nombres, start=1)
    )
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>' + sheets + "</sheets></workbook>"


def _xlsx_workbook_rels(num_sheets: int) -> str:
    rels = "".join(
        f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
        for i in range(1, num_sheets + 1)
    )
    return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + rels + "</Relationships>"


def panel_exportacion():
    resultado = st.session_state.resultado
    if not resultado:
        st.info("Ejecuta la simulacion para poder exportar resultados.")
        return
    cfg = st.session_state.cfg
    st.subheader("Exportacion a Excel")
    st.caption("Marca las tablas que quieres incluir. Se descargara un XLSX con una hoja por tabla seleccionada.")
    disponibles = tablas_exportables(resultado, cfg)
    seleccion = {}
    cols = st.columns(3)
    for idx, nombre in enumerate(disponibles):
        seleccion[nombre] = cols[idx % 3].checkbox(nombre, value=True, key=f"export_{nombre}")
    tablas_sel = {nombre: df for nombre, df in disponibles.items() if seleccion[nombre]}
    if not tablas_sel:
        st.warning("Selecciona al menos una tabla.")
        return
    st.download_button(
        "Descargar Excel",
        data=crear_excel(tablas_sel),
        file_name="encicle_simulacion_46007.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=True,
    )


def main():
    init_state()
    st.title("Simulador operativo Encicle - Codigo postal 46007 Valencia")
    st.caption("Optimizacion mensual de flota, rutas y economia usando portales reales del CP 46007 y hub en Joaquin Sorolla.")

    tabs = st.tabs(["Manual", "Configuracion", "Simulacion mensual", "Pedidos y traspasos", "Vehiculos", "Personas", "Mapa de rutas", "Economia y KPI", "Incidencias", "Exportacion"])
    with tabs[0]:
        panel_manual()
    with tabs[1]:
        panel_configuracion()
    with tabs[2]:
        panel_resumen()
    with tabs[3]:
        panel_pedidos_traspasos()
    with tabs[4]:
        panel_vehiculos()
    with tabs[5]:
        panel_personas()
    with tabs[6]:
        panel_mapa()
    with tabs[7]:
        panel_economia_kpi()
    with tabs[8]:
        panel_incidencias()
    with tabs[9]:
        panel_exportacion()


if __name__ == "__main__":
    main()
