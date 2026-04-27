from __future__ import annotations

import math
import random
from typing import Any

import pandas as pd

from config import DIAS_MES, HUB, NOMBRES_TRABAJADORES, TARIFAS
from datos_geo import distancia_km


def es_laborable(dia: int) -> bool:
    return (dia - 1) % 7 < 5


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*[max(0, min(255, v)) for v in rgb])


def _color_unidad(base: str, indice: int, total: int) -> str:
    if total <= 1:
        return base
    r, g, b = _hex_to_rgb(base)
    factor = 0.72 + (indice / max(1, total - 1)) * 0.42
    return _rgb_to_hex((int(r * factor), int(g * factor), int(b * factor)))


def _hora_texto(hora: float | None) -> str:
    if hora is None:
        return ""
    hora = max(0, min(23.99, hora))
    h = int(hora)
    m = int(round((hora - h) * 60))
    if m == 60:
        h += 1
        m = 0
    return f"{h:02d}:{m:02d}"


def _saltar_pausa(hora: float) -> float:
    if 15 <= hora < 16:
        return 16.0
    return hora


def _horas_trabajo_entre(inicio: float, fin: float) -> float:
    fin = max(inicio, fin)
    pausa = max(0.0, min(fin, 16.0) - max(inicio, 15.0))
    return max(0.0, fin - inicio - pausa)


def _horas_texto(horas: float) -> str:
    minutos = int(round(max(0.0, horas) * 60))
    return f"{minutos // 60}h {minutos % 60:02d}m"


def _hora_decimal_texto(hora: float) -> str:
    return _hora_texto(hora)


def _planificar_turno(horas_operativas: float, fin_operativo: float | None = None) -> dict[str, Any]:
    inicio = 8.0
    descanso = horas_operativas > 5
    fin = fin_operativo if fin_operativo is not None else inicio + horas_operativas + (1.0 if descanso else 0.0)
    if descanso and fin >= 16:
        descanso_txt = "15:00-16:00"
    elif descanso:
        descanso_txt = "al finalizar ruta"
    else:
        descanso_txt = ""
    return {
        "turno_inicio": _hora_decimal_texto(inicio),
        "turno_fin": _hora_decimal_texto(fin),
        "descanso": descanso_txt,
        "horas_trabajadas": round(horas_operativas, 2),
        "horas_trabajadas_txt": _horas_texto(horas_operativas),
    }


def generar_pedidos(portales: list[dict[str, Any]], cfg: dict) -> list[dict[str, Any]]:
    rng = random.Random(cfg["semilla"])
    pedidos = []
    tipos = ["sobre", "pm", "xl"]
    pesos = [cfg["ratio_sobre"], cfg["ratio_pm"], cfg["ratio_xl"]]
    destinos = ["residencial", "oficina", "comercio", "locker"]
    pesos_destino = [0.60, 0.10, 0.10, 0.20]

    for dia in range(1, DIAS_MES + 1):
        if not es_laborable(dia):
            continue
        n = rng.randint(int(cfg["demanda_min"]), int(cfg["demanda_max"]))
        urgentes = int(round(n * cfg["ratio_urgente"]))
        for i in range(n):
            portal = rng.choice(portales)
            tipo = rng.choices(tipos, weights=pesos, k=1)[0]
            urgente = i < urgentes
            deadline = 10 if urgente and rng.random() < 0.5 else 12 if urgente else None
            margen = rng.choice([3, 4])
            peso_kg = {"sobre": rng.uniform(0.05, 0.4), "pm": rng.uniform(0.5, 8.0), "xl": rng.uniform(8.0, 25.0)}[tipo]
            volumen_l = {"sobre": rng.uniform(0.1, 1.0), "pm": rng.uniform(2.0, 35.0), "xl": rng.uniform(40.0, 140.0)}[tipo]
            pedidos.append(
                {
                    "id": len(pedidos) + 1,
                    "dia_entrada": dia,
                    "dia_limite": dia if urgente else min(DIAS_MES, dia + margen),
                    "deadline_hora": deadline,
                    "servicio": "urgente" if urgente else "estandar",
                    "tipo": tipo,
                    "peso_kg": round(peso_kg, 2),
                    "volumen_l": round(volumen_l, 1),
                    "portal_id": portal["id"],
                    "calle": portal["calle"],
                    "numero": portal["numero"],
                    "lat": portal["lat"],
                    "lon": portal["lon"],
                    "destino": rng.choices(destinos, weights=pesos_destino, k=1)[0],
                    "entregado": False,
                    "dia_entrega": None,
                    "hora_entrega": None,
                    "hora_entrega_txt": "",
                    "vehiculo": None,
                    "vehiculo_nombre": "",
                    "vehiculo_tipo": "",
                    "repartidor": "",
                    "sla_ok": False,
                    "fallo_1": False,
                    "primera_ocasion_ok": False,
                    "intentos": 0,
                    "ingreso": 0.0,
                    "origen_carga": "Hub",
                    "traspaso_id": "",
                    "orden_ruta": 0,
                }
            )
    rng.shuffle(pedidos)
    return pedidos


def _productividad(spec: dict, tipo: str, cfg: dict, rng: random.Random, hora_pico: bool = True) -> float:
    if spec["nombre"].startswith("Furgoneta") and tipo == "xl":
        base = rng.uniform(spec.get("productividad_xl_min", 10), spec.get("productividad_xl_max", 12))
    else:
        base = rng.uniform(spec["productividad_min"], spec["productividad_max"])
    if hora_pico:
        base *= 1.12
    return base


def _productividad_media(spec: dict, tipo: str) -> float:
    if spec["nombre"].startswith("Furgoneta") and tipo == "xl":
        return (spec.get("productividad_xl_min", 10) + spec.get("productividad_xl_max", 12)) / 2
    return (spec["productividad_min"] + spec["productividad_max"]) / 2


def _productividad_maxima(spec: dict, tipo: str) -> float:
    if spec["nombre"].startswith("Furgoneta") and tipo == "xl":
        return float(spec.get("productividad_xl_max", 12))
    return float(spec["productividad_max"])


def _tiempo_servicio_horas(spec: dict, cfg: dict) -> float:
    minutos = cfg.get("tiempo_entrega_furgoneta_min", 2.0) if spec["modo"] == "drive" else cfg.get("tiempo_entrega_min", 1.0)
    return max(0.1, float(minutos)) / 60


def _tiempo_entrega_estimado_horas(spec: dict, tipo: str, cfg: dict, rng: random.Random, urgente: bool) -> float:
    if cfg.get("modo_productividad", "rango") == "rango":
        prod = min(
            _productividad(spec, tipo, cfg, rng, hora_pico=urgente),
            _productividad_maxima(spec, tipo),
        )
        return max(1 / max(1, prod), _tiempo_servicio_horas(spec, cfg))
    return _tiempo_servicio_horas(spec, cfg)


def _tiempo_asignacion_estimado_horas(spec: dict, tipo: str, cfg: dict, rng: random.Random, urgente: bool) -> float:
    desplazamiento_medio = {"drive": 0.025, "bike": 0.035, "walk": 0.045}.get(spec["modo"], 0.035)
    if cfg.get("modo_productividad", "rango") == "rango":
        return max(1 / max(1, _productividad_media(spec, tipo)), _tiempo_servicio_horas(spec, cfg)) + desplazamiento_medio
    base = _tiempo_entrega_estimado_horas(spec, tipo, cfg, rng, urgente)
    desplazamiento_realista = {"drive": 0.018, "bike": 0.026, "walk": 0.038}.get(spec["modo"], 0.03)
    return base + desplazamiento_realista


def _factor_modo(spec: dict) -> float:
    return 1.22 if spec["modo"] == "drive" else 1.12 if spec["modo"] == "bike" else 1.05


def _velocidad_ajustada(spec: dict, hora: float) -> float:
    velocidad = float(spec["velocidad_kmh"])
    if 8 <= hora < 10 or 16 <= hora < 18:
        velocidad *= 0.85
    return max(3, velocidad)


def _tiempo_viaje_horas(origen: tuple[float, float], destino: tuple[float, float], spec: dict, hora: float) -> float:
    km = distancia_km(origen, destino) * _factor_modo(spec)
    return km / _velocidad_ajustada(spec, hora)


def _max_repartos_dia(spec: dict) -> int:
    """Maximo fisico diario segun productividad por hora y jornada de 8h."""
    return int(spec["productividad_max"] * 8)


def _capacidad_paquetes(spec: dict, tipo: str) -> int:
    if tipo == "xl":
        return int(spec.get("cap_xl", 0))
    if tipo == "sobre":
        return int(spec.get("cap_sobre", 0))
    return int(spec.get("cap_pm", 0))


def _capacidad_mixta(spec: dict) -> int:
    valores = [int(spec.get("cap_sobre", 0)), int(spec.get("cap_pm", 0))]
    return max(1, min(v for v in valores if v > 0) if any(v > 0 for v in valores) else 1)


def _capacidad_operativa(spec: dict, pedidos: list[dict[str, Any]] | None = None) -> int:
    if pedidos and any(p["tipo"] == "xl" for p in pedidos):
        return max(1, int(spec.get("cap_xl", 0)))
    return _capacidad_mixta(spec)


def _capacidad_pm_operativa(spec: dict) -> int:
    return _capacidad_mixta(spec)


def _capacidades_carga(spec: dict) -> dict[str, int]:
    return {
        "pm": max(0, _capacidad_pm_operativa(spec)),
        "xl": max(0, int(spec.get("cap_xl", 0))),
    }


def _inventario_total(inventario: dict[str, int]) -> int:
    return int(inventario.get("pm", 0)) + int(inventario.get("xl", 0))


def _copia_inventario(inventario: dict[str, int]) -> dict[str, int]:
    return {"pm": int(inventario.get("pm", 0)), "xl": int(inventario.get("xl", 0))}


def _inventario_para(inventario_global: dict[str, Any], vehiculo_id: str) -> dict[str, int]:
    inventario = inventario_global.get(vehiculo_id)
    if isinstance(inventario, dict):
        normalizado = {
            "pm": max(0, int(inventario.get("pm", 0))),
            "xl": max(0, int(inventario.get("xl", 0))),
        }
    else:
        normalizado = {"pm": max(0, int(inventario or 0)), "xl": 0}
    inventario_global[vehiculo_id] = normalizado
    return normalizado


def _compartimento_pedido(tipo: str) -> str:
    return "xl" if tipo == "xl" else "pm"


def _label_compartimento(delta_pm: int, delta_xl: int) -> str:
    if delta_pm and delta_xl:
        return "P/M + XL"
    if delta_xl:
        return "XL"
    if delta_pm:
        return "P/M"
    return "Sin cambio"


def _vehiculo_admite(spec: dict, pedido: dict) -> bool:
    return _capacidad_paquetes(spec, pedido["tipo"]) > 0


def _distancia_operativa_km(pedidos: list[dict[str, Any]], factor: float) -> float:
    if not pedidos:
        return 0.0
    hub = (HUB["lat"], HUB["lon"])
    puntos = [(p["lat"], p["lon"]) for p in pedidos]
    centro = (sum(p[0] for p in puntos) / len(puntos), sum(p[1] for p in puntos) / len(puntos))
    radial = distancia_km(hub, centro) * 2
    dispersion = sum(distancia_km(centro, p) for p in puntos) / max(1, len(puntos))
    return max(0.8, (radial + dispersion * len(puntos) * 0.23) * factor)


def _seleccionar_candidatos(cfg: dict) -> list[dict[str, int]]:
    veh = cfg["vehiculos"]
    max_v = int(cfg["max_vehiculos_tipo"])
    candidatos = []
    for furgo in range(1, min(max_v, 4) + 1):
        for bici in range(0, max_v + 1):
            for tri in range(0, min(max_v, 5) + 1):
                for anda in range(0, min(max_v, 6) + 1):
                    for rem in range(0, min(max_v, 5) + 1):
                        flota = {
                            "bicicleta_cargo": bici,
                            "triciclo": tri,
                            "furgoneta": furgo,
                            "andarin": anda,
                            "remolque_bici": rem,
                        }
                        unidades = sum(flota.values())
                        if unidades == 0 or unidades > 18:
                            continue
                        cap_xl_h = furgo * (veh["furgoneta"].get("productividad_xl_min", 10) + veh["furgoneta"].get("productividad_xl_max", 12)) / 2
                        cap_total_h = sum(
                            cant * ((veh[k]["productividad_min"] + veh[k]["productividad_max"]) / 2)
                            for k, cant in flota.items()
                        )
                        if cap_xl_h * 8 < cfg["demanda_max"] * cfg["ratio_xl"] * 0.9:
                            continue
                        if cap_total_h * 8 < cfg["demanda_max"] * 0.92:
                            continue
                        candidatos.append(flota)
    return candidatos[:2200]


def _coste_estimado_flota(flota: dict[str, int], cfg: dict) -> float:
    veh = cfg["vehiculos"]
    dias_laborables = len([d for d in range(1, DIAS_MES + 1) if es_laborable(d)])
    demanda_media = (cfg["demanda_min"] + cfg["demanda_max"]) / 2
    xl_dia = demanda_media * cfg["ratio_xl"]
    total_dia = demanda_media

    cap_total = 0.0
    cap_xl = 0.0
    preferencia_penalty = 0.0
    for tipo, cant in flota.items():
        spec = veh[tipo]
        prod = (spec["productividad_min"] + spec["productividad_max"]) / 2
        cap_total += cant * prod * 8
        preferencia_penalty += cant * (3 - float(spec.get("preferencia", 3))) * 180
        if tipo == "furgoneta":
            prod_xl = (spec.get("productividad_xl_min", 10) + spec.get("productividad_xl_max", 12)) / 2
            cap_xl += cant * prod_xl * 8

    if cap_total < total_dia * 0.96 or cap_xl < xl_dia * 0.95:
        return float("inf")

    alquiler = sum(flota[k] * veh[k]["alquiler_mes"] for k in flota)
    hub = cfg["m2_hub"] * cfg["alquiler_m2"] + cfg["coste_fijo_hub"]
    unidades_activas = max(1, sum(flota.values()))
    horas_operativas = total_dia / max(1, cap_total / (8 * unidades_activas))
    horas_reparto = max(horas_operativas, unidades_activas * 4) * dias_laborables
    coste_laboral = (horas_reparto + 8 * dias_laborables) * cfg["coste_hora"]
    energia = total_dia * dias_laborables * 0.035
    cargas = sum(flota[k] * veh[k].get("cargas_dia", 0) for k in flota) * dias_laborables * cfg["coste_carga"]
    unidades_flota = sum(flota.values())
    penalizacion_exceso = max(0, cap_total / max(1, total_dia) - 1.18) * 520
    penalizacion_unidades = unidades_flota * 180
    return alquiler + hub + coste_laboral + energia + cargas + penalizacion_exceso + penalizacion_unidades + preferencia_penalty


def _ordenar_pedidos(pedidos: list[dict[str, Any]], dia: int) -> list[dict[str, Any]]:
    def clave(p: dict) -> tuple[int, int, int, int]:
        prioridad = 0 if p["servicio"] == "urgente" else 1
        deadline = p["deadline_hora"] or 24
        tipo = 0 if p["tipo"] == "xl" else 1
        vencimiento = max(0, p["dia_limite"] - dia)
        return prioridad, deadline, tipo, vencimiento

    return sorted(pedidos, key=clave)


def _crear_unidades(flota: dict[str, int], cfg: dict) -> list[dict[str, Any]]:
    unidades = []
    idx_global = 0
    for tipo, cant in flota.items():
        for n in range(cant):
            spec = cfg["vehiculos"][tipo]
            color = _color_unidad(spec["color"], n, max(1, cant))
            trabajador = NOMBRES_TRABAJADORES[idx_global % len(NOMBRES_TRABAJADORES)]
            unidades.append(
                {
                    "id": f"{tipo}_{n + 1}",
                    "tipo": tipo,
                    "nombre": f"{spec['nombre']} {n + 1}",
                    "spec": spec,
                    "idx": idx_global + 1,
                    "color": color,
                    "trabajador": trabajador,
                }
            )
            idx_global += 1
    return unidades


def _orden_nearest_neighbor(paradas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pendientes = paradas[:]
    actual = (HUB["lat"], HUB["lon"])
    ordenadas = []
    while pendientes:
        siguiente = min(pendientes, key=lambda p: distancia_km(actual, (p["lat"], p["lon"])))
        pendientes.remove(siguiente)
        ordenadas.append(siguiente)
        actual = (siguiente["lat"], siguiente["lon"])
    return ordenadas


def _orden_ruta_operativa(paradas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordenadas = []
    actual = (HUB["lat"], HUB["lon"])
    bloques = [
        [p for p in paradas if p["servicio"] == "urgente" and p.get("deadline_hora") == 10],
        [p for p in paradas if p["servicio"] == "urgente" and p.get("deadline_hora") == 12],
        [p for p in paradas if p["servicio"] != "urgente"],
    ]
    for bloque in bloques:
        pendientes = bloque[:]
        while pendientes:
            siguiente = min(pendientes, key=lambda p: distancia_km(actual, (p["lat"], p["lon"])))
            pendientes.remove(siguiente)
            ordenadas.append(siguiente)
            actual = (siguiente["lat"], siguiente["lon"])
    return ordenadas


def _programar_ruta(
    dia: int,
    unidad: dict[str, Any],
    pedidos: list[dict[str, Any]],
    cfg: dict,
    rng: random.Random,
    traspasos: list[dict[str, Any]],
    cargas_hub: list[dict[str, Any]],
    eventos_vehiculos: list[dict[str, Any]],
    furgo_nodriza: dict[str, Any] | None,
    inventario_global: dict[str, Any],
    disponibilidad_global: dict[str, float],
) -> tuple[float, float, int]:
    if not pedidos:
        return 0.0, 0.0, 0

    ordenados = _orden_ruta_operativa(pedidos)
    spec = unidad["spec"]
    hora = max(8.0, disponibilidad_global.get(unidad["id"], 8.0))
    hora_inicio = hora
    horas_total = 0.0
    recargas = 0
    capacidades = _capacidades_carga(spec)
    capacidad_total = max(1, _inventario_total(capacidades))
    inventario = _inventario_para(inventario_global, unidad["id"])
    origen_carga_activo = {"pm": "Recogido en hub", "xl": "Recogido en hub"}
    traspaso_activo = {"pm": "", "xl": ""}
    km_acum = 0.0
    entregas_acum = 0

    def registrar_evento_para(
        unidad_evento: dict[str, Any],
        evento: str,
        hora_evento: float,
        antes: dict[str, int],
        despues: dict[str, int],
        pedido: dict[str, Any] | None = None,
        detalle: str = "",
        km_delta: float = 0.0,
        km_acumulados: float | None = None,
        entregas_acumuladas: int | None = None,
        lat: float | None = None,
        lon: float | None = None,
    ) -> None:
        cap_evento = _capacidades_carga(unidad_evento["spec"])
        delta_pm = int(despues.get("pm", 0)) - int(antes.get("pm", 0))
        delta_xl = int(despues.get("xl", 0)) - int(antes.get("xl", 0))
        total_antes = _inventario_total(antes)
        total_despues = _inventario_total(despues)
        eventos_vehiculos.append(
            {
                "secuencia_evento": len(eventos_vehiculos) + 1,
                "dia": dia,
                "hora": _hora_texto(hora_evento),
                "hora_decimal": round(hora_evento, 3),
                "vehiculo_id": unidad_evento["id"],
                "vehiculo": unidad_evento["nombre"],
                "tipo_vehiculo": unidad_evento["tipo"],
                "repartidor": unidad_evento["trabajador"],
                "evento": evento,
                "pedido_id": pedido["id"] if pedido else "",
                "tipo_paquete": pedido["tipo"] if pedido else "",
                "compartimento": _label_compartimento(delta_pm, delta_xl),
                "detalle": detalle,
                "lat": pedido["lat"] if pedido else lat,
                "lon": pedido["lon"] if pedido else lon,
                "pm_antes": antes.get("pm", 0),
                "delta_pm": delta_pm,
                "pm_despues": despues.get("pm", 0),
                "cap_pm": cap_evento["pm"],
                "xl_antes": antes.get("xl", 0),
                "delta_xl": delta_xl,
                "xl_despues": despues.get("xl", 0),
                "cap_xl": cap_evento["xl"],
                "carga_antes": total_antes,
                "delta_carga": total_despues - total_antes,
                "carga_despues": total_despues,
                "capacidad": _inventario_total(cap_evento),
                "km_delta": round(km_delta, 3),
                "km_acumulados": round(km_acum if km_acumulados is None else km_acumulados, 3),
                "entregas_acumuladas": entregas_acum if entregas_acumuladas is None else entregas_acumuladas,
            }
        )

    def registrar_carga_hub_para(
        unidad_carga: dict[str, Any],
        hora_evento: float,
        antes: dict[str, int],
        despues: dict[str, int],
        tipo: str,
        detalle_evento: str,
    ) -> None:
        cap_carga = _capacidades_carga(unidad_carga["spec"])
        delta_pm = max(0, int(despues.get("pm", 0)) - int(antes.get("pm", 0)))
        delta_xl = max(0, int(despues.get("xl", 0)) - int(antes.get("xl", 0)))
        paquetes = delta_pm + delta_xl
        if paquetes <= 0:
            return
        cargas_hub.append(
            {
                "carga_id": f"H{dia:02d}-{unidad_carga['id']}-{len(cargas_hub) + 1}",
                "dia": dia,
                "hora": _hora_texto(hora_evento),
                "vehiculo": unidad_carga["nombre"],
                "vehiculo_id": unidad_carga["id"],
                "repartidor": unidad_carga["trabajador"],
                "paquetes": paquetes,
                "paquetes_pm": delta_pm,
                "paquetes_xl": delta_xl,
                "compartimento": _label_compartimento(delta_pm, delta_xl),
                "tipo": tipo,
                "pm_antes": antes.get("pm", 0),
                "pm_despues": despues.get("pm", 0),
                "cap_pm": cap_carga["pm"],
                "xl_antes": antes.get("xl", 0),
                "xl_despues": despues.get("xl", 0),
                "cap_xl": cap_carga["xl"],
                "delta_pm": delta_pm,
                "delta_xl": delta_xl,
                "carga_antes": _inventario_total(antes),
                "carga_despues": _inventario_total(despues),
                "capacidad": _inventario_total(cap_carga),
                "ubicacion": HUB["nombre"],
            }
        )
        registrar_evento_para(
            unidad_carga,
            "Carga en hub",
            hora_evento,
            antes,
            despues,
            detalle=detalle_evento,
            km_acumulados=0.0,
            entregas_acumuladas=0,
            lat=HUB["lat"],
            lon=HUB["lon"],
        )

    pendientes_inicial_pm = sum(1 for p in ordenados if p["tipo"] != "xl")
    pendientes_inicial_xl = sum(1 for p in ordenados if p["tipo"] == "xl")
    antes_inicial = _copia_inventario(inventario)
    if pendientes_inicial_pm and capacidades["pm"] > 0:
        inventario["pm"] = capacidades["pm"]
    if pendientes_inicial_xl and capacidades["xl"] > 0:
        inventario["xl"] = capacidades["xl"]
    despues_inicial = _copia_inventario(inventario)
    if despues_inicial != antes_inicial:
        registrar_carga_hub_para(unidad, hora, antes_inicial, despues_inicial, "Carga inicial", "Carga inicial por compartimentos")
        recargas += 1

    anterior = (HUB["lat"], HUB["lon"])
    siguiente_entrega_permitida = 8.0
    for idx, pedido in enumerate(ordenados, start=1):
        compartimento = _compartimento_pedido(pedido["tipo"])
        if inventario.get(compartimento, 0) <= 0:
            pendientes = sum(1 for p in ordenados[idx - 1:] if _compartimento_pedido(p["tipo"]) == compartimento)
            capacidad_comp = capacidades[compartimento]
            hueco_receptor = max(0, capacidad_comp - inventario.get(compartimento, 0))
            cantidad_objetivo = min(capacidad_comp, hueco_receptor, pendientes)
            if cfg.get("usar_traspaso_furgoneta", True) and unidad["tipo"] != "furgoneta" and furgo_nodriza:
                dador_capacidades = _capacidades_carga(furgo_nodriza["spec"])
                dador_inventario = _inventario_para(inventario_global, furgo_nodriza["id"])
                traspaso_id = f"T{dia:02d}-{unidad['id']}-{idx}"
                if dador_inventario.get("pm", 0) < cantidad_objetivo:
                    antes_dador_hub = _copia_inventario(dador_inventario)
                    carga_necesaria = max(0, dador_capacidades["pm"] - dador_inventario.get("pm", 0))
                    if carga_necesaria > 0:
                        dador_inventario["pm"] = min(dador_capacidades["pm"], dador_inventario.get("pm", 0) + carga_necesaria)
                        despues_dador_hub = _copia_inventario(dador_inventario)
                        carga_h = carga_necesaria * 5 / 3600
                        horas_total += carga_h
                        hora = _saltar_pausa(hora + carga_h)
                        registrar_carga_hub_para(
                            furgo_nodriza,
                            hora,
                            antes_dador_hub,
                            despues_dador_hub,
                            "Carga nodriza P/M para traspaso",
                            f"Carga P/M para aprovisionar a {unidad['nombre']}",
                        )

                cantidad = min(
                    cantidad_objetivo,
                    dador_inventario.get("pm", 0),
                    max(0, capacidades["pm"] - inventario.get("pm", 0)),
                    pendientes,
                )
                if cantidad <= 0:
                    antes_hub = _copia_inventario(inventario)
                    inventario["pm"] = min(capacidades["pm"], inventario.get("pm", 0) + max(0, capacidades["pm"] - inventario.get("pm", 0)))
                    despues_hub = _copia_inventario(inventario)
                    hora = _saltar_pausa(hora + max(0, despues_hub["pm"] - antes_hub["pm"]) * 5 / 3600)
                    registrar_carga_hub_para(unidad, hora, antes_hub, despues_hub, "Recarga durante ruta P/M", "Recarga P/M en hub")
                    origen_carga_activo["pm"] = "Recogido en hub"
                    traspaso_activo["pm"] = ""
                    recargas += 1
                else:
                    transferencia_h = cantidad * 5 / 3600
                    horas_total += transferencia_h
                    hora = _saltar_pausa(hora + transferencia_h)
                    dador_antes_traspaso = _copia_inventario(dador_inventario)
                    receptor_antes_traspaso = _copia_inventario(inventario)
                    dador_inventario["pm"] = max(0, dador_inventario.get("pm", 0) - cantidad)
                    inventario["pm"] = min(capacidades["pm"], inventario.get("pm", 0) + cantidad)
                    dador_despues_traspaso = _copia_inventario(dador_inventario)
                    receptor_despues_traspaso = _copia_inventario(inventario)
                    traspasos.append(
                        {
                            "traspaso_id": traspaso_id,
                            "dia": dia,
                            "hora": _hora_texto(hora),
                            "desde": furgo_nodriza["nombre"],
                            "hacia": unidad["nombre"],
                            "repartidor_dador": furgo_nodriza["trabajador"],
                            "repartidor_receptor": unidad["trabajador"],
                            "paquetes": cantidad,
                            "paquetes_pm": cantidad,
                            "paquetes_xl": 0,
                            "compartimento": "P/M",
                            "lat": pedido["lat"],
                            "lon": pedido["lon"],
                            "ubicacion": f"{pedido['calle']} {pedido['numero']}",
                            "pm_dador_antes": dador_antes_traspaso["pm"],
                            "pm_dador_despues": dador_despues_traspaso["pm"],
                            "capacidad_dador_pm": dador_capacidades["pm"],
                            "xl_dador_antes": dador_antes_traspaso["xl"],
                            "xl_dador_despues": dador_despues_traspaso["xl"],
                            "capacidad_dador_xl": dador_capacidades["xl"],
                            "pm_receptor_antes": receptor_antes_traspaso["pm"],
                            "pm_receptor_despues": receptor_despues_traspaso["pm"],
                            "capacidad_receptor_pm": capacidades["pm"],
                            "xl_receptor_antes": receptor_antes_traspaso["xl"],
                            "xl_receptor_despues": receptor_despues_traspaso["xl"],
                            "capacidad_receptor_xl": capacidades["xl"],
                            "carga_dador_antes": _inventario_total(dador_antes_traspaso),
                            "carga_dador_despues": _inventario_total(dador_despues_traspaso),
                            "capacidad_dador": _inventario_total(dador_capacidades),
                            "carga_receptor_antes": _inventario_total(receptor_antes_traspaso),
                            "carga_receptor_despues": _inventario_total(receptor_despues_traspaso),
                            "capacidad_receptor": capacidad_total,
                            "tiempo_operacion_min": round(cantidad * 5 / 60, 2),
                        }
                    )
                    origen_carga_activo["pm"] = "Traspaso desde furgoneta"
                    traspaso_activo["pm"] = traspaso_id
                    recargas += 1
                    registrar_evento_para(unidad, "Traspaso recibido P/M", hora, receptor_antes_traspaso, receptor_despues_traspaso, detalle=f"Desde {furgo_nodriza['nombre']}", lat=pedido["lat"], lon=pedido["lon"])
                    registrar_evento_para(furgo_nodriza, "Traspaso entregado P/M", hora, dador_antes_traspaso, dador_despues_traspaso, detalle=f"A {unidad['nombre']}", km_acumulados=0.0, entregas_acumuladas=0, lat=pedido["lat"], lon=pedido["lon"])
                    disponibilidad_global[furgo_nodriza["id"]] = max(disponibilidad_global.get(furgo_nodriza["id"], 8.0), hora)
            else:
                antes_hub = _copia_inventario(inventario)
                cantidad = min(capacidad_comp, max(0, capacidad_comp - inventario.get(compartimento, 0)))
                inventario[compartimento] = min(capacidad_comp, inventario.get(compartimento, 0) + cantidad)
                despues_hub = _copia_inventario(inventario)
                origen_carga_activo[compartimento] = "Recogido en hub"
                traspaso_activo[compartimento] = ""
                recargas += 1
                carga_h = cantidad * 5 / 3600
                horas_total += carga_h
                hora = _saltar_pausa(hora + carga_h)
                registrar_carga_hub_para(
                    unidad,
                    hora,
                    antes_hub,
                    despues_hub,
                    f"Recarga durante ruta {_label_compartimento(cantidad if compartimento == 'pm' else 0, cantidad if compartimento == 'xl' else 0)}",
                    "Recarga durante ruta",
                )

        if inventario.get(compartimento, 0) <= 0:
            continue

        punto = (pedido["lat"], pedido["lon"])
        km = distancia_km(anterior, punto) * _factor_modo(spec)
        viaje_h = km / _velocidad_ajustada(spec, hora)

        hora = _saltar_pausa(hora + viaje_h)
        servicio_h = _tiempo_entrega_estimado_horas(spec, pedido["tipo"], cfg, rng, pedido["servicio"] == "urgente")
        if pedido["fallo_1"]:
            servicio_h += rng.uniform(0.4, 1.2) / 60
        hora = _saltar_pausa(hora + servicio_h)
        hora_pre_productividad = hora
        hora = _saltar_pausa(max(hora, siguiente_entrega_permitida))
        espera_productividad_h = max(0.0, hora - hora_pre_productividad)
        horas_total += espera_productividad_h
        intervalo_minimo_h = 1 / max(1, _productividad_maxima(spec, pedido["tipo"]))
        siguiente_entrega_permitida = _saltar_pausa(hora + intervalo_minimo_h)

        antes_entrega = _copia_inventario(inventario)
        inventario[compartimento] = max(0, inventario.get(compartimento, 0) - 1)
        despues_entrega = _copia_inventario(inventario)
        km_acum += km
        entregas_acum += 1
        pedido["hora_entrega"] = round(hora, 3)
        pedido["hora_entrega_txt"] = _hora_texto(hora)
        pedido["vehiculo"] = unidad["id"]
        pedido["vehiculo_nombre"] = unidad["nombre"]
        pedido["vehiculo_tipo"] = unidad["tipo"]
        pedido["repartidor"] = unidad["trabajador"]
        pedido["orden_ruta"] = idx
        pedido["origen_carga"] = origen_carga_activo[compartimento]
        pedido["traspaso_id"] = traspaso_activo[compartimento]
        pedido["compartimento_carga"] = "XL" if compartimento == "xl" else "P/M"
        pedido["pm_antes_entrega"] = antes_entrega["pm"]
        pedido["pm_despues_entrega"] = despues_entrega["pm"]
        pedido["xl_antes_entrega"] = antes_entrega["xl"]
        pedido["xl_despues_entrega"] = despues_entrega["xl"]
        pedido["sla_ok"] = pedido["servicio"] != "urgente" or pedido["hora_entrega"] <= float(pedido["deadline_hora"])
        registrar_evento_para(unidad, "Entrega", hora, antes_entrega, despues_entrega, pedido=pedido, detalle=f"{pedido['calle']} {pedido['numero']}", km_delta=km)

        horas_total += viaje_h + servicio_h
        anterior = punto

    retorno_h = _tiempo_viaje_horas(anterior, (HUB["lat"], HUB["lon"]), spec, hora)
    horas_total += retorno_h
    hora = _saltar_pausa(hora + retorno_h)
    disponibilidad_global[unidad["id"]] = hora
    if cfg.get("modo_productividad", "rango") == "rango":
        horas_productividad = sum(max(1 / max(1, _productividad_media(spec, p["tipo"])), _tiempo_servicio_horas(spec, cfg)) for p in ordenados)
        horas_modelo = max(horas_total, horas_productividad)
    else:
        horas_modelo = horas_total
    return horas_modelo, _distancia_operativa_km(ordenados, 1.25 if spec["modo"] == "drive" else 1.15 if spec["modo"] == "bike" else 1.05), recargas


def simular_con_flota(portales: list[dict[str, Any]], cfg: dict, flota: dict[str, int]) -> dict[str, Any]:
    rng = random.Random(cfg["semilla"] + sum(flota.values()) * 17 + (31 if cfg.get("usar_traspaso_furgoneta", True) else 0))
    pedidos = generar_pedidos(portales, cfg)
    unidades = _crear_unidades(flota, cfg)
    diarios = []
    rutas_por_dia = {}
    traspasos = []
    cargas_hub = []
    eventos_vehiculos = []
    incidencias = []
    entregados = 0
    primera_ok = 0
    sla_urg_ok = 0
    urg_total = 0
    ingresos = 0.0
    energia = 0.0
    km_total = 0.0
    cargas = 0
    horas_operativas_reparto_total = 0.0
    horas_pagadas_reparto_total = 0.0
    rutas_sobre_8h = 0
    km_por_vehiculo: dict[str, float] = {}
    energia_por_vehiculo: dict[str, float] = {}
    cargas_bateria_por_vehiculo: dict[str, int] = {}

    for dia in range(1, DIAS_MES + 1):
        if not es_laborable(dia):
            diarios.append({"dia": dia, "laborable": False, "paquetes_disponibles": 0, "urgentes_disponibles": 0, "entregados": 0, "primera_ocasion": 0, "pendientes": 0, "coste_dia": 0})
            continue

        disponibles = [
            p for p in pedidos
            if not p["entregado"] and p["dia_entrada"] <= dia and p["dia_limite"] >= dia
        ]
        paquetes_disponibles = len(disponibles)
        urgentes_disponibles = len([p for p in disponibles if p["servicio"] == "urgente"])
        disponibles = _ordenar_pedidos(disponibles, dia)
        asignaciones = {u["id"]: [] for u in unidades}
        carga_estimada = {u["id"]: 0.0 for u in unidades}
        ultimo_punto_estimado = {u["id"]: (HUB["lat"], HUB["lon"]) for u in unidades}
        repartos_asignados = {u["id"]: 0 for u in unidades}
        xl_asignados = {u["id"]: 0 for u in unidades}
        entregados_dia = 0
        primera_dia = 0
        urg_dia = 0
        sla_urg_dia = 0
        km_dia = 0.0
        energia_dia = 0.0
        cargas_dia = 0

        for pedido in disponibles:
            mejor = None
            mejor_score = float("inf")
            mejor_extra_h = 0.0
            mejor_punto = (pedido["lat"], pedido["lon"])
            for unidad in unidades:
                if not _vehiculo_admite(unidad["spec"], pedido):
                    continue
                if repartos_asignados[unidad["id"]] >= _max_repartos_dia(unidad["spec"]):
                    continue
                if pedido["tipo"] == "xl" and xl_asignados[unidad["id"]] >= int(unidad["spec"].get("productividad_xl_max", unidad["spec"]["productividad_max"]) * 8):
                    continue
                spec_u = unidad["spec"]
                punto_pedido = (pedido["lat"], pedido["lon"])
                hora_estimada = 8.0 + min(7.5, carga_estimada[unidad["id"]])
                viaje_h = _tiempo_viaje_horas(ultimo_punto_estimado[unidad["id"]], punto_pedido, spec_u, hora_estimada)
                if cfg.get("modo_productividad", "rango") == "rango":
                    servicio_h = max(1 / max(1, _productividad_media(spec_u, pedido["tipo"])), _tiempo_servicio_horas(spec_u, cfg))
                else:
                    servicio_h = _tiempo_servicio_horas(spec_u, cfg)
                intervalo_productivo_h = 1 / max(1, _productividad_maxima(spec_u, pedido["tipo"]))
                extra_h = max(viaje_h + servicio_h, intervalo_productivo_h)
                retorno_h = _tiempo_viaje_horas(punto_pedido, (HUB["lat"], HUB["lon"]), spec_u, hora_estimada + extra_h)
                proyectada_core = carga_estimada[unidad["id"]] + extra_h
                proyectada = proyectada_core + retorno_h * 0.15
                limite_jornada_asignacion = 7.05 if unidad["tipo"] == "furgoneta" else 8.0
                if proyectada > limite_jornada_asignacion:
                    continue
                if pedido["servicio"] == "urgente":
                    limite_urgente = max(0.7, float(pedido["deadline_hora"]) - 8.0)
                    if proyectada_core > limite_urgente:
                        continue

                ya_abierta = repartos_asignados[unidad["id"]] > 0
                apertura_penalty = 0.0 if ya_abierta else 850.0
                tipo_penalty = 0.0
                if pedido["tipo"] != "xl" and unidad["tipo"] == "furgoneta":
                    tipo_penalty = 260.0
                if pedido["tipo"] == "xl" and unidad["tipo"] != "furgoneta":
                    tipo_penalty = 500.0
                preferencia_penalty = (3 - float(spec_u.get("preferencia", 3))) * 35.0

                target_h = min(7.75, limite_jornada_asignacion - 0.05)
                shortfall = max(0.0, target_h - proyectada)
                over_target = max(0.0, proyectada - target_h)
                fill_reward = min(carga_estimada[unidad["id"]], target_h) * (24.0 if ya_abierta else 5.0)
                distance_penalty = viaje_h * 90.0 + retorno_h * 18.0
                near_full_penalty = shortfall * (24.0 if ya_abierta else 35.0) + over_target * 120.0
                score = apertura_penalty + tipo_penalty + preferencia_penalty + distance_penalty + near_full_penalty - fill_reward
                if score < mejor_score:
                    mejor = unidad
                    mejor_score = score
                    mejor_extra_h = extra_h
                    mejor_punto = punto_pedido
            if not mejor:
                continue

            fallo_1 = rng.random() < cfg["prob_fallo_1"]
            segundo_ok = True
            if fallo_1:
                incidencias.append(
                    {
                        "dia": dia,
                        "pedido": pedido["id"],
                        "tipo": "Ausencia cliente en primer intento",
                        "detalle": f"{pedido['calle']} {pedido['numero']}",
                    }
                )
                segundo_ok = rng.random() > cfg["prob_fallo_1"]

            if not segundo_ok:
                pedido["intentos"] = 2
                incidencias.append({"dia": dia, "pedido": pedido["id"], "tipo": "No entregado tras segundo intento", "detalle": f"{pedido['calle']} {pedido['numero']}"})
                continue

            pedido["entregado"] = True
            pedido["dia_entrega"] = dia
            pedido["fallo_1"] = fallo_1
            pedido["primera_ocasion_ok"] = not fallo_1
            pedido["intentos"] = 2 if fallo_1 else 1
            pedido["ingreso"] = TARIFAS[pedido["tipo"]] + (TARIFAS["extra_urgente"] if pedido["servicio"] == "urgente" else 0)
            asignaciones[mejor["id"]].append(pedido)
            carga_estimada[mejor["id"]] += mejor_extra_h
            ultimo_punto_estimado[mejor["id"]] = mejor_punto
            repartos_asignados[mejor["id"]] += 1
            if pedido["tipo"] == "xl":
                xl_asignados[mejor["id"]] += 1
            entregados_dia += 1
            primera_dia += 1 if pedido["primera_ocasion_ok"] else 0
            entregados += 1
            primera_ok += 1 if pedido["primera_ocasion_ok"] else 0
            ingresos += pedido["ingreso"]
            if pedido["servicio"] == "urgente":
                urg_total += 1
                urg_dia += 1

        rutas_dia = []
        furgo_nodriza = next((u for u in unidades if u["tipo"] == "furgoneta"), None)
        inventario_global = {u["id"]: {"pm": 0, "xl": 0} for u in unidades}
        disponibilidad_global = {u["id"]: 8.0 for u in unidades}
        unidades_programacion = sorted(unidades, key=lambda u: 0 if u["tipo"] == "furgoneta" else 1)
        for unidad in unidades_programacion:
            ps = asignaciones[unidad["id"]]
            if not ps:
                continue
            horas, km, recargas = _programar_ruta(
                dia,
                unidad,
                ps,
                cfg,
                rng,
                traspasos,
                cargas_hub,
                eventos_vehiculos,
                furgo_nodriza,
                inventario_global,
                disponibilidad_global,
            )
            cargas_unit = int(unidad["spec"].get("cargas_dia", 0)) if ps else 0
            km_dia += km
            energia_unit = km * unidad["spec"]["energia_100km"] / 100
            energia_dia += energia_unit
            cargas_dia += cargas_unit
            km_por_vehiculo[unidad["id"]] = km_por_vehiculo.get(unidad["id"], 0.0) + km
            energia_por_vehiculo[unidad["id"]] = energia_por_vehiculo.get(unidad["id"], 0.0) + energia_unit
            cargas_bateria_por_vehiculo[unidad["id"]] = cargas_bateria_por_vehiculo.get(unidad["id"], 0) + cargas_unit
            for pedido in ps:
                if pedido["servicio"] == "urgente" and pedido["sla_ok"]:
                    sla_urg_ok += 1
                    sla_urg_dia += 1
            rutas_dia.append(
                {
                    "vehiculo_id": unidad["id"],
                    "vehiculo": unidad["nombre"],
                    "tipo": unidad["tipo"],
                    "trabajador": unidad["trabajador"],
                    "color": unidad["color"],
                    "modo": unidad["spec"]["modo"],
                    "pedidos": [p["id"] for p in ps],
                    "paradas": sorted(ps, key=lambda p: p["orden_ruta"]),
                    "km": km,
                    "recargas_paquetes": recargas,
                    "horas": horas,
                    "horas_pagadas": horas,
                    "max_repartos_dia": _max_repartos_dia(unidad["spec"]),
                    "fin_operativo": disponibilidad_global.get(unidad["id"], 8.0),
                }
            )

        for ruta in rutas_dia:
            ruta["fin_operativo"] = float(disponibilidad_global.get(ruta["vehiculo_id"], ruta.get("fin_operativo", 8.0)))
            ruta["fin_operativo_txt"] = _hora_texto(ruta["fin_operativo"])
            horas_reloj = _horas_trabajo_entre(8.0, ruta["fin_operativo"])
            ruta["horas"] = max(ruta["horas"], horas_reloj)
            if ruta["horas"] > 8.0 or ruta["fin_operativo"] > 19.0:
                rutas_sobre_8h += 1
                incidencias.append(
                    {
                        "dia": dia,
                        "pedido": "",
                        "tipo": "Ruta supera jornada maxima",
                        "detalle": f"{ruta['vehiculo']} estimada en {ruta['horas']:.2f}h y fin {_hora_texto(ruta['fin_operativo'])}",
                    }
                )
            ruta.update(_planificar_turno(ruta["horas"], ruta["fin_operativo"]))
            ruta["horas_pagadas"] = ruta["horas_trabajadas"]

        energia += energia_dia
        km_total += km_dia
        cargas += cargas_dia
        horas_reparto = sum(r["horas"] for r in rutas_dia)
        horas_pagadas_reparto = sum(r["horas_pagadas"] for r in rutas_dia)
        horas_operativas_reparto_total += horas_reparto
        horas_pagadas_reparto_total += horas_pagadas_reparto
        coste_laboral_dia = (horas_pagadas_reparto + 8) * cfg["coste_hora"]
        coste_energia_dia = energia_dia
        coste_cargas_dia = cargas_dia * cfg["coste_carga"]
        diarios.append(
            {
                "dia": dia,
                "laborable": True,
                "paquetes_disponibles": paquetes_disponibles,
                "urgentes_disponibles": urgentes_disponibles,
                "entregados": entregados_dia,
                "primera_ocasion": primera_dia,
                "urgentes": urg_dia,
                "sla_urgentes": sla_urg_dia,
                "km": round(km_dia, 2),
                "horas_reparto": round(horas_reparto, 2),
                "horas_pagadas_reparto": round(horas_pagadas_reparto, 2),
                "utilizacion_personal_pct": round((horas_reparto / max(1, horas_pagadas_reparto)) * 100, 1),
                "trabajadores_reparto": len(rutas_dia),
                "trabajadores_hub": 1,
                "traspasos": len([t for t in traspasos if t["dia"] == dia]),
                "pendientes": len([p for p in pedidos if not p["entregado"] and p["dia_entrada"] <= dia]),
                "coste_dia": round(coste_laboral_dia + coste_energia_dia + coste_cargas_dia, 2),
            }
        )
        rutas_por_dia[dia] = rutas_dia

        for p in pedidos:
            if not p["entregado"] and p["dia_limite"] < dia:
                incidencias.append({"dia": dia, "pedido": p["id"], "tipo": "SLA vencido", "detalle": f"{p['servicio']} {p['calle']} {p['numero']}"})

    dias_laborables = len([d for d in range(1, DIAS_MES + 1) if es_laborable(d)])
    alquiler_flota = sum(flota[k] * cfg["vehiculos"][k]["alquiler_mes"] for k in flota)
    coste_hub_alquiler = cfg["m2_hub"] * cfg["alquiler_m2"]
    coste_hub_fijo = cfg["coste_fijo_hub"]
    alquiler_hub = coste_hub_alquiler + coste_hub_fijo
    coste_laboral_reparto = horas_pagadas_reparto_total * cfg["coste_hora"]
    coste_laboral_hub = 8 * dias_laborables * cfg["coste_hora"]
    coste_laboral = coste_laboral_reparto + coste_laboral_hub
    coste_cargas = cargas * cfg["coste_carga"]
    coste_total = alquiler_flota + alquiler_hub + coste_laboral + energia + coste_cargas
    utilizacion_personal_global = horas_operativas_reparto_total / max(1, horas_pagadas_reparto_total)
    pico_trabajadores_reparto = max((d.get("trabajadores_reparto", 0) for d in diarios), default=0)
    unidades_flota = sum(flota.values())
    penalizacion_utilizacion = max(0.0, 0.93 - utilizacion_personal_global) * 9000
    penalizacion_sobre_8h = rutas_sobre_8h * 15000
    penalizacion_flota = unidades_flota * 260 + pico_trabajadores_reparto * 420
    penalizacion_preferencia = sum(
        flota[tipo] * (3 - float(cfg["vehiculos"][tipo].get("preferencia", 3))) * 220
        for tipo in flota
    )
    objetivo_optimizacion = coste_total + penalizacion_utilizacion + penalizacion_flota + penalizacion_preferencia
    objetivo_optimizacion += penalizacion_sobre_8h
    total_pedidos_mes = len([p for p in pedidos if p["dia_entrada"] <= DIAS_MES])
    tasa_entrega_total = entregados / max(1, total_pedidos_mes) * 100
    efectividad_primera = primera_ok / max(1, total_pedidos_mes) * 100
    sla = sla_urg_ok / max(1, urg_total) * 100
    digital = float(cfg["score_digitalizacion"])
    cero_emisiones = 100.0
    score = efectividad_primera * 0.40 + sla * 0.30 + digital * 0.20 + cero_emisiones * 0.10

    return {
        "flota": flota,
        "pedidos": pedidos,
        "diarios": diarios,
        "rutas_por_dia": rutas_por_dia,
        "traspasos": traspasos,
        "cargas_hub": cargas_hub,
        "eventos_vehiculos": eventos_vehiculos,
        "incidencias": incidencias,
        "ingresos": ingresos,
        "coste_total": coste_total,
        "objetivo_optimizacion": objetivo_optimizacion,
        "beneficio": ingresos - coste_total,
        "alquiler_flota": alquiler_flota,
        "alquiler_hub": alquiler_hub,
        "coste_hub_alquiler": coste_hub_alquiler,
        "coste_hub_fijo": coste_hub_fijo,
        "coste_laboral": coste_laboral,
        "coste_laboral_reparto": coste_laboral_reparto,
        "coste_laboral_hub": coste_laboral_hub,
        "horas_operativas_reparto_total": horas_operativas_reparto_total,
        "horas_pagadas_reparto_total": horas_pagadas_reparto_total,
        "utilizacion_personal_global": utilizacion_personal_global * 100,
        "pico_trabajadores_reparto": pico_trabajadores_reparto,
        "rutas_sobre_8h": rutas_sobre_8h,
        "coste_energia": energia,
        "coste_cargas": coste_cargas,
        "km_total": km_total,
        "kwh_equiv": energia,
        "entregados": entregados,
        "total_pedidos_mes": total_pedidos_mes,
        "tasa_entrega_total": tasa_entrega_total,
        "primera_ocasion": primera_ok,
        "score": score,
        "kpis": {
            "efectividad": efectividad_primera,
            "sla": sla,
            "digitalizacion": digital,
            "cero_emisiones": cero_emisiones,
        },
        "operativa_vehiculos": {
            "km_por_vehiculo": km_por_vehiculo,
            "energia_por_vehiculo": energia_por_vehiculo,
            "cargas_bateria_por_vehiculo": cargas_bateria_por_vehiculo,
        },
    }


def optimizar_mes(portales: list[dict[str, Any]], cfg: dict, progreso=None) -> dict[str, Any]:
    candidatos = _seleccionar_candidatos(cfg)
    candidatos = sorted(candidatos, key=lambda f: _coste_estimado_flota(f, cfg))
    candidatos = [c for c in candidatos if _coste_estimado_flota(c, cfg) < float("inf")]
    if cfg["modo_optimizacion"] == "rapido":
        candidatos = candidatos[:32]
    elif cfg["modo_optimizacion"] == "preciso":
        candidatos = candidatos[:90]
    else:
        candidatos = candidatos[:48]

    mejor = None
    evaluados = 0
    for idx, flota in enumerate(candidatos):
        resultado = simular_con_flota(portales, cfg, flota)
        evaluados += 1
        valido = (
            resultado["score"] >= cfg["objetivo_gls"]
            and resultado["tasa_entrega_total"] >= 98.5
            and resultado.get("rutas_sobre_8h", 0) == 0
        )
        if valido and (mejor is None or resultado["objetivo_optimizacion"] < mejor["objetivo_optimizacion"]):
            mejor = resultado
        if progreso and idx % 10 == 0:
            progreso(min(0.98, idx / max(1, len(candidatos))))

    if mejor is None:
        mejor = max((simular_con_flota(portales, cfg, f) for f in candidatos[:120]), key=lambda r: r["score"])
    mejor["evaluados"] = evaluados
    mejor["trabajadores"] = NOMBRES_TRABAJADORES[: max(3, max(d.get("trabajadores_reparto", 0) for d in mejor["diarios"]) + 1)]
    return mejor


def resumen_diario_df(resultado: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(resultado["diarios"])


def resumen_flota_df(resultado: dict[str, Any], cfg: dict) -> pd.DataFrame:
    rows = []
    for tipo, unidades in resultado["flota"].items():
        if unidades:
            spec = cfg["vehiculos"][tipo]
            rows.append(
                {
                    "vehiculo": spec["nombre"],
                    "unidades_mes": unidades,
                    "alquiler_mes_unit": spec["alquiler_mes"],
                    "coste_alquiler": unidades * spec["alquiler_mes"],
                    "cap_sobre": spec["cap_sobre"],
                    "cap_pm": spec["cap_pm"],
                    "cap_xl": spec["cap_xl"],
                    "velocidad_kmh": spec["velocidad_kmh"],
                    "preferencia_1_5": spec.get("preferencia", 3),
                }
            )
    return pd.DataFrame(rows)


def resumen_pedidos_df(resultado: dict[str, Any], dia: int | None = None) -> pd.DataFrame:
    rows = []
    for p in resultado["pedidos"]:
        if not p["entregado"]:
            continue
        if dia is not None and p["dia_entrega"] != dia:
            continue
        rows.append(
            {
                "pedido_id": p["id"],
                "dia_entrada": p["dia_entrada"],
                "dia_entrega": p["dia_entrega"],
                "hora_entrega": p["hora_entrega_txt"],
                "repartidor": p["repartidor"],
                "vehiculo": p["vehiculo_nombre"],
                "tipo_vehiculo": p["vehiculo_tipo"],
                "origen_carga": p["origen_carga"],
                "traspaso_id": p["traspaso_id"],
                "compartimento_carga": p.get("compartimento_carga", "XL" if p["tipo"] == "xl" else "P/M"),
                "pm_antes_entrega": p.get("pm_antes_entrega", ""),
                "pm_despues_entrega": p.get("pm_despues_entrega", ""),
                "xl_antes_entrega": p.get("xl_antes_entrega", ""),
                "xl_despues_entrega": p.get("xl_despues_entrega", ""),
                "servicio": p["servicio"],
                "deadline": _hora_texto(float(p["deadline_hora"])) if p["deadline_hora"] else f"D+{p['dia_limite'] - p['dia_entrada']}",
                "sla_ok": p["sla_ok"],
                "primera_ocasion": p["primera_ocasion_ok"],
                "intentos": p["intentos"],
                "tipo_paquete": p["tipo"],
                "peso_kg": p["peso_kg"],
                "volumen_l": p["volumen_l"],
                "destino": p["destino"],
                "calle": p["calle"],
                "numero": p["numero"],
                "ingreso_eur": p["ingreso"],
            }
        )
    return pd.DataFrame(rows)


def resumen_traspasos_df(resultado: dict[str, Any], dia: int | None = None) -> pd.DataFrame:
    rows = []
    for t in resultado["traspasos"]:
        if dia is not None and t["dia"] != dia:
            continue
        rows.append(t)
    return pd.DataFrame(rows)


def resumen_cargas_hub_df(resultado: dict[str, Any], dia: int | None = None) -> pd.DataFrame:
    rows = []
    for c in resultado.get("cargas_hub", []):
        if dia is not None and c["dia"] != dia:
            continue
        rows.append(c)
    return pd.DataFrame(rows)


def eventos_vehiculos_df(resultado: dict[str, Any], dia: int | None = None, vehiculo_id: str | None = None) -> pd.DataFrame:
    rows = []
    for e in resultado.get("eventos_vehiculos", []):
        if dia is not None and e["dia"] != dia:
            continue
        if vehiculo_id and e["vehiculo_id"] != vehiculo_id:
            continue
        rows.append(e)
    df = pd.DataFrame(rows)
    if not df.empty:
        orden = ["dia", "hora_decimal", "vehiculo"]
        if "secuencia_evento" in df.columns:
            orden.append("secuencia_evento")
        else:
            orden.append("evento")
        df = df.sort_values(orden)
    return df


def resumen_personas_dia_df(resultado: dict[str, Any], dia: int | None = None) -> pd.DataFrame:
    acumulado: dict[tuple[int, str], dict[str, Any]] = {}
    dias_objetivo = [
        d["dia"]
        for d in resultado.get("diarios", [])
        if d.get("laborable") and (dia is None or d["dia"] == dia)
    ]
    for rutas_dia, rutas in resultado.get("rutas_por_dia", {}).items():
        if dia is not None and rutas_dia != dia:
            continue
        for ruta in rutas:
            key = (rutas_dia, ruta["trabajador"])
            row = acumulado.setdefault(
                key,
                {
                    "dia": rutas_dia,
                    "persona": ruta["trabajador"],
                    "vehiculos": set(),
                    "horas_operativas": 0.0,
                    "horas_trabajadas": 0.0,
                    "turno_inicio": [],
                    "turno_fin": [],
                    "descanso": [],
                    "km": 0.0,
                    "repartos": 0,
                    "traspasos_recibidos": 0,
                },
            )
            row["vehiculos"].add(ruta["vehiculo"])
            row["horas_operativas"] += ruta["horas"]
            row["horas_trabajadas"] += float(ruta.get("horas_trabajadas", ruta.get("horas_pagadas", ruta["horas"])))
            row["turno_inicio"].append(ruta.get("turno_inicio", "08:00"))
            row["turno_fin"].append(ruta.get("turno_fin", _hora_texto(8 + ruta["horas"])))
            if ruta.get("descanso"):
                row["descanso"].append(ruta["descanso"])
            row["km"] += ruta["km"]
            row["repartos"] += len(ruta["paradas"])

    for t in resultado.get("traspasos", []):
        if dia is not None and t["dia"] != dia:
            continue
        key = (t["dia"], t["repartidor_receptor"])
        if key in acumulado:
            acumulado[key]["traspasos_recibidos"] += 1

    rows = []
    for row in acumulado.values():
        horas = row["horas_operativas"]
        row["turno_inicio"] = min(row["turno_inicio"]) if row["turno_inicio"] else "08:00"
        row["turno_fin"] = max(row["turno_fin"]) if row["turno_fin"] else _hora_texto(8 + row["horas_trabajadas"])
        row["descanso"] = ", ".join(sorted(set(row["descanso"])))
        row["ocupacion_turno_pct"] = round(horas / max(0.01, row["horas_trabajadas"]) * 100, 2)
        row["horas_operativas"] = round(horas, 2)
        row["horas_trabajadas"] = round(row["horas_trabajadas"], 2)
        row["horas_trabajadas_txt"] = _horas_texto(row["horas_trabajadas"])
        row["km"] = round(row["km"], 2)
        row["vehiculos"] = ", ".join(sorted(row["vehiculos"]))
        rows.append(row)
    for dia_hub in dias_objetivo:
        rows.append(
            {
                "dia": dia_hub,
                "persona": "Responsable hub",
                "vehiculos": "Hub Joaquin Sorolla",
                "horas_operativas": 8.0,
                "horas_trabajadas": 8.0,
                "horas_trabajadas_txt": "8h 00m",
                "turno_inicio": "06:00",
                "turno_fin": "14:00",
                "descanso": "",
                "ocupacion_turno_pct": 100.0,
                "km": 0.0,
                "repartos": 0,
                "traspasos_recibidos": 0,
            }
        )
    return pd.DataFrame(rows).sort_values(["dia", "persona"]) if rows else pd.DataFrame()


def resumen_personas_hora_df(resultado: dict[str, Any], dia: int | None = None) -> pd.DataFrame:
    rows: dict[tuple[int, int, str], dict[str, Any]] = {}
    for e in resultado.get("eventos_vehiculos", []):
        if dia is not None and e["dia"] != dia:
            continue
        hora = int(float(e["hora_decimal"]))
        key = (e["dia"], hora, e["repartidor"])
        row = rows.setdefault(
            key,
            {
                "dia": e["dia"],
                "hora": f"{hora:02d}:00-{hora + 1:02d}:00",
                "persona": e["repartidor"],
                "km": 0.0,
                "repartos": 0,
                "cargas_hub": 0,
                "traspasos": 0,
                "eventos": 0,
            },
        )
        row["km"] += e.get("km_delta", 0.0)
        row["repartos"] += 1 if e["evento"] == "Entrega" else 0
        row["cargas_hub"] += 1 if e["evento"] == "Carga en hub" else 0
        row["traspasos"] += 1 if "Traspaso" in e["evento"] else 0
        row["eventos"] += 1
    data = list(rows.values())
    for row in data:
        row["km"] = round(row["km"], 2)
    return pd.DataFrame(data).sort_values(["dia", "hora", "persona"]) if data else pd.DataFrame()


def productividad_personas_df(resultado: dict[str, Any]) -> pd.DataFrame:
    personas = resumen_personas_dia_df(resultado)
    if personas.empty:
        return pd.DataFrame()
    rows = []
    for persona, grupo in personas.groupby("persona"):
        if persona == "Responsable hub":
            continue
        horas = float(grupo["horas_trabajadas"].sum())
        repartos = int(grupo["repartos"].sum())
        km = float(grupo["km"].sum())
        dias = int(grupo["dia"].nunique())
        traspasos = int(grupo["traspasos_recibidos"].sum())
        rows.append(
            {
                "persona": persona,
                "dias_activos": dias,
                "horas_trabajadas": round(horas, 2),
                "horas_trabajadas_txt": _horas_texto(horas),
                "paquetes_entregados": repartos,
                "paquetes_por_hora": round(repartos / max(0.01, horas), 2),
                "km_totales": round(km, 2),
                "km_por_hora": round(km / max(0.01, horas), 2),
                "paquetes_por_dia_activo": round(repartos / max(1, dias), 2),
                "traspasos_recibidos": traspasos,
            }
        )
    return pd.DataFrame(rows).sort_values("paquetes_por_hora", ascending=False) if rows else pd.DataFrame()


def resumen_vehiculos_df(resultado: dict[str, Any], cfg: dict) -> pd.DataFrame:
    rows = []
    unidades = {}
    for rutas in resultado.get("rutas_por_dia", {}).values():
        for r in rutas:
            unidades[r["vehiculo_id"]] = r
    for vehiculo_id, ruta in unidades.items():
        cargas_hub = [c for c in resultado.get("cargas_hub", []) if c["vehiculo_id"] == vehiculo_id]
        trasp_rec = [t for t in resultado.get("traspasos", []) if t["hacia"] == ruta["vehiculo"]]
        trasp_dados = [t for t in resultado.get("traspasos", []) if t["desde"] == ruta["vehiculo"]]
        hub_pm = sum(int(c.get("paquetes_pm", 0)) for c in cargas_hub)
        hub_xl = sum(int(c.get("paquetes_xl", 0)) for c in cargas_hub)
        trasp_rec_pm = sum(int(t.get("paquetes_pm", t.get("paquetes", 0))) for t in trasp_rec)
        trasp_dados_pm = sum(int(t.get("paquetes_pm", t.get("paquetes", 0))) for t in trasp_dados)
        entregas_mes = sum(len(r["paradas"]) for rutas in resultado.get("rutas_por_dia", {}).values() for r in rutas if r["vehiculo_id"] == vehiculo_id)
        dias_activos = len([1 for rutas in resultado.get("rutas_por_dia", {}).values() for r in rutas if r["vehiculo_id"] == vehiculo_id])
        max_repartos_dia = int(route_max) if (route_max := ruta.get("max_repartos_dia")) else 0
        rows.append(
            {
                "vehiculo_id": vehiculo_id,
                "vehiculo": ruta["vehiculo"],
                "tipo": ruta["tipo"],
                "repartidor_base": ruta["trabajador"],
                "entregas_mes": entregas_mes,
                "dias_activos": dias_activos,
                "max_repartos_dia": max_repartos_dia,
                "uso_max_diario_medio_pct": round((entregas_mes / max(1, dias_activos * max_repartos_dia)) * 100, 1) if max_repartos_dia else 0,
                "km_mes": round(resultado["operativa_vehiculos"]["km_por_vehiculo"].get(vehiculo_id, 0.0), 2),
                "energia_eur": round(resultado["operativa_vehiculos"]["energia_por_vehiculo"].get(vehiculo_id, 0.0), 2),
                "cargas_bateria": resultado["operativa_vehiculos"]["cargas_bateria_por_vehiculo"].get(vehiculo_id, 0),
                "eventos_carga_hub": len(cargas_hub),
                "paquetes_pm_desde_hub": hub_pm,
                "paquetes_xl_desde_hub": hub_xl,
                "traspasos_recibidos": len(trasp_rec),
                "paquetes_pm_recibidos": trasp_rec_pm,
                "traspasos_dados": len(trasp_dados),
                "paquetes_pm_entregados_a_otros": trasp_dados_pm,
            }
        )
    return pd.DataFrame(rows).sort_values(["tipo", "vehiculo"]) if rows else pd.DataFrame()


def desglose_energia_df(resultado: dict[str, Any], cfg: dict) -> pd.DataFrame:
    rows = []
    unidades = {}
    for rutas in resultado.get("rutas_por_dia", {}).values():
        for r in rutas:
            unidades[r["vehiculo_id"]] = r
    for vehiculo_id, ruta in unidades.items():
        spec = cfg["vehiculos"][ruta["tipo"]]
        km = resultado["operativa_vehiculos"]["km_por_vehiculo"].get(vehiculo_id, 0.0)
        energia = resultado["operativa_vehiculos"]["energia_por_vehiculo"].get(vehiculo_id, 0.0)
        cargas = resultado["operativa_vehiculos"]["cargas_bateria_por_vehiculo"].get(vehiculo_id, 0)
        rows.append(
            {
                "vehiculo": ruta["vehiculo"],
                "tipo": ruta["tipo"],
                "km_mes": round(km, 2),
                "coste_energia_100km": spec["energia_100km"],
                "coste_energia_eur": round(energia, 2),
                "cargas_bateria": cargas,
                "coste_carga_unit": cfg["coste_carga"],
                "coste_cargas_eur": round(cargas * cfg["coste_carga"], 2),
                "coste_total_energia_y_cargas": round(energia + cargas * cfg["coste_carga"], 2),
            }
        )
    return pd.DataFrame(rows).sort_values(["tipo", "vehiculo"]) if rows else pd.DataFrame()


def desglose_costes_df(resultado: dict[str, Any], cfg: dict) -> pd.DataFrame:
    rows = []
    for tipo, unidades in resultado["flota"].items():
        if unidades:
            spec = cfg["vehiculos"][tipo]
            rows.append({"bloque": "Flota", "concepto": f"Alquiler {spec['nombre']}", "cantidad": unidades, "unidad": "vehiculo/mes", "unitario_eur": spec["alquiler_mes"], "importe_eur": unidades * spec["alquiler_mes"]})
    rows.extend(
        [
            {"bloque": "Hub", "concepto": "Alquiler superficie hub", "cantidad": cfg["m2_hub"], "unidad": "m2", "unitario_eur": cfg["alquiler_m2"], "importe_eur": resultado["coste_hub_alquiler"]},
            {"bloque": "Hub", "concepto": "Coste fijo mensual hub", "cantidad": 1, "unidad": "mes", "unitario_eur": resultado["coste_hub_fijo"], "importe_eur": resultado["coste_hub_fijo"]},
            {"bloque": "Personal", "concepto": "Horas trabajadas de reparto", "cantidad": round(resultado["coste_laboral_reparto"] / cfg["coste_hora"], 2), "unidad": "hora", "unitario_eur": cfg["coste_hora"], "importe_eur": resultado["coste_laboral_reparto"]},
            {"bloque": "Personal", "concepto": "Horas operativas de reparto", "cantidad": round(resultado["horas_operativas_reparto_total"], 2), "unidad": "hora", "unitario_eur": 0, "importe_eur": 0},
            {"bloque": "Personal", "concepto": "Personal fijo de hub, 1 trabajador diario", "cantidad": round(resultado["coste_laboral_hub"] / cfg["coste_hora"], 2), "unidad": "hora", "unitario_eur": cfg["coste_hora"], "importe_eur": resultado["coste_laboral_hub"]},
            {"bloque": "Operacion", "concepto": "Energia vehiculos", "cantidad": round(resultado["km_total"], 2), "unidad": "km", "unitario_eur": "", "importe_eur": resultado["coste_energia"]},
            {"bloque": "Operacion", "concepto": "Cargas de bateria", "cantidad": round(resultado["coste_cargas"] / cfg["coste_carga"], 0), "unidad": "carga", "unitario_eur": cfg["coste_carga"], "importe_eur": resultado["coste_cargas"]},
            {"bloque": "Resultado", "concepto": "Ingresos entregas cobradas", "cantidad": resultado["entregados"], "unidad": "pedido", "unitario_eur": round(resultado["ingresos"] / max(1, resultado["entregados"]), 3), "importe_eur": resultado["ingresos"]},
            {"bloque": "Resultado", "concepto": "Coste total", "cantidad": 1, "unidad": "mes", "unitario_eur": resultado["coste_total"], "importe_eur": resultado["coste_total"]},
            {"bloque": "Resultado", "concepto": "Beneficio operativo", "cantidad": 1, "unidad": "mes", "unitario_eur": resultado["beneficio"], "importe_eur": resultado["beneficio"]},
        ]
    )
    return pd.DataFrame(rows)


def resumen_kpis_df(resultado: dict[str, Any], cfg: dict) -> pd.DataFrame:
    rutas = [r for rutas_dia in resultado.get("rutas_por_dia", {}).values() for r in rutas_dia]
    horas_operativas = resultado.get("horas_operativas_reparto_total", 0.0)
    horas_trabajadas = resultado.get("horas_pagadas_reparto_total", 0.0)
    entregados = max(1, resultado.get("entregados", 0))
    rutas_ok = len([r for r in rutas if r.get("horas", 0) <= 8])
    rutas_total = max(1, len(rutas))
    coste_paquete = resultado.get("coste_total", 0.0) / entregados
    ingreso_paquete = resultado.get("ingresos", 0.0) / entregados
    beneficio_paquete = resultado.get("beneficio", 0.0) / entregados
    km_total = max(0.01, resultado.get("km_total", 0.0))
    rows = [
        {"categoria": "Scorecard Encicle", "kpi": "Score final ponderado", "valor": resultado.get("score", 0.0), "unidad": "%", "objetivo": cfg.get("objetivo_gls", 95.0)},
        {"categoria": "Servicio", "kpi": "Tasa de entrega total", "valor": resultado.get("tasa_entrega_total", 0.0), "unidad": "%", "objetivo": 98.5},
        {"categoria": "Servicio", "kpi": "Efectividad primera entrega", "valor": resultado["kpis"].get("efectividad", 0.0), "unidad": "%", "objetivo": 95.0},
        {"categoria": "Servicio", "kpi": "Cumplimiento SLA urgente", "valor": resultado["kpis"].get("sla", 0.0), "unidad": "%", "objetivo": 95.0},
        {"categoria": "Operacion", "kpi": "Utilizacion personal", "valor": resultado.get("utilizacion_personal_global", 0.0), "unidad": "%", "objetivo": 90.0},
        {"categoria": "Operacion", "kpi": "Cumplimiento rutas <= 8h", "valor": rutas_ok / rutas_total * 100, "unidad": "%", "objetivo": 100.0},
        {"categoria": "Operacion", "kpi": "Productividad reparto", "valor": entregados / max(0.01, horas_operativas), "unidad": "paq/h operativa", "objetivo": ""},
        {"categoria": "Operacion", "kpi": "Horas trabajadas no productivas", "valor": max(0.0, horas_trabajadas - horas_operativas), "unidad": "h", "objetivo": "min"},
        {"categoria": "Flota", "kpi": "Pico repartidores diarios", "valor": resultado.get("pico_trabajadores_reparto", 0), "unidad": "personas", "objetivo": "min"},
        {"categoria": "Flota", "kpi": "Entregas por km", "valor": entregados / km_total, "unidad": "paq/km", "objetivo": "max"},
        {"categoria": "Economia", "kpi": "Coste por paquete", "valor": coste_paquete, "unidad": "EUR/paq", "objetivo": "min"},
        {"categoria": "Economia", "kpi": "Ingreso por paquete", "valor": ingreso_paquete, "unidad": "EUR/paq", "objetivo": "max"},
        {"categoria": "Economia", "kpi": "Beneficio por paquete", "valor": beneficio_paquete, "unidad": "EUR/paq", "objetivo": "max"},
        {"categoria": "Sostenibilidad", "kpi": "Ratio cero emisiones", "valor": resultado["kpis"].get("cero_emisiones", 0.0), "unidad": "%", "objetivo": 100.0},
        {"categoria": "Digital", "kpi": "Digitalizacion y trazabilidad", "valor": resultado["kpis"].get("digitalizacion", 0.0), "unidad": "%", "objetivo": 100.0},
    ]
    return pd.DataFrame(rows)
