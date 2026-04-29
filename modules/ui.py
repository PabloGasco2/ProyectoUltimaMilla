from __future__ import annotations

import pandas as pd
import streamlit as st


def badge(text: str, variant: str = "pink") -> str:
    css = {
        "pink": "badge",
        "purple": "badge badge-purple",
        "blue": "badge badge-blue",
        "orange": "badge badge-orange",
    }.get(variant, "badge")
    return f"<span class='{css}'>{text}</span>"


def app_shell() -> None:
    st.markdown(
        """
        <div class="landing">
            <div class="landing-mark">Almussafes Mobility Hub</div>
            <h1>Tribbu | Almussafes</h1>
            <p>Plataforma de movilidad compartida para trabajadores del Área industrial de Almussafes. Coche compartido, rutas, parking, motos, lockers, accesibilidad e indicadores operativos en una experiencia integrada.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def compact_header(workspace: str, persona: str) -> None:
    st.markdown(
        f"""
        <div class="appbar">
            <div class="brand">
                <div class="brand-dot">T</div>
                <div>
                    <div class="brand-title">Tribbu | Almussafes</div>
                    <div class="brand-subtitle">Movilidad compartida para trabajadores</div>
                </div>
            </div>
            <div class="profile-chip">{workspace} · {persona}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def selection_card(title: str, body: str, button_text: str, key: str) -> bool:
    st.markdown(
        f"""
        <div class="select-card">
            <h3>{title}</h3>
            <p>{body}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    return st.button(button_text, key=key, use_container_width=True)


def persona_summary(workspace: str, persona: str) -> None:
    copy = {
        "Pasajero": "Busca un viaje, revisa cómo llegar al punto de recogida y completa el trayecto con parking, moto o locker.",
        "Conductor": "Publica una ruta, gestiona plazas, acepta paquetes y consulta bonificaciones.",
        "Equipo Tribbu": "Supervisa demanda, rutas calientes, operación multimodal, KPIs y alertas de la red.",
    }.get(persona, "Experiencia Tribbu")
    st.markdown(
        f"""
        <div class="persona-banner">
            <div class="persona-kicker">Perfil activo</div>
            <div class="persona-title">{persona}</div>
            <div class="persona-copy">{copy}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def official_footer() -> None:
    st.markdown(
        """
        <div class="footer">
            <div class="footer-grid">
                <div>
                    <strong>Tribbu Mobility S.L.</strong><br>
                    Servicio operativo para empresas y trabajadores<br>
                    CIF: B72941863
                </div>
                <div>
                    <strong>Contacto</strong><br>
                    +34 960 000 000<br>
                    soporte@tribbu.app
                </div>
                <div>
                    <strong>Dirección</strong><br>
                    C/ Colón 1, 46004 Valencia<br>
                    Atención empresas: +34 960 000 001
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def page_title(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div style="margin: 8px 0 16px 0;">
            <div class="persona-kicker">Tribbu Almussafes</div>
            <h2 style="margin: 2px 0 4px 0;">{title}</h2>
            <div class="muted">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def metric_card(label: str, value: str, help_text: str | None = None) -> None:
    helper = f"<div class='muted'>{help_text}</div>" if help_text else ""
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            {helper}
        </div>
        """,
        unsafe_allow_html=True,
    )


def availability_card(
    title: str,
    used_pct: int | float,
    primary_line: str,
    secondary_line: str,
    status: str,
    variant: str = "pink",
) -> None:
    used = max(0, min(int(round(used_pct)), 100))
    st.markdown(
        f"""
        <div class="card">
            <div>{badge(status, variant)}</div>
            <div class="card-title">{title}</div>
            <p>{primary_line}</p>
            <div style="height: 9px; background: #F7F7F8; border-radius: 999px; overflow: hidden; margin: 10px 0;">
                <div style="width: {used}%; height: 9px; background: #111111; border-radius: 999px;"></div>
            </div>
            <p class="muted">{secondary_line}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def feature_card(title: str, body: str, badges: list[str] | None = None) -> None:
    tags = "".join(badge(item) for item in (badges or []))
    st.markdown(
        f"""
        <div class="card">
            <div>{tags}</div>
            <div class="card-title">{title}</div>
            <p class="muted">{body}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def trip_card(row: pd.Series, prefix: str, reserve: bool = True) -> None:
    tags = []
    if row["ruta_caliente"]:
        tags.append(badge("Ruta caliente", "orange"))
    if row["parking"]:
        tags.append(badge("Parking incluido"))
    if row["moto_destino"]:
        tags.append(badge("Moto disponible", "blue"))
    if row["tipo_coche"] in ["eléctrico", "híbrido"]:
        tags.append(badge("Bajas emisiones", "purple"))
    if row["ocupacion_actual"] >= 3:
        tags.append(badge("3+ ocupantes"))
    if "turno" in row:
        tags.append(badge(row["turno"], "blue"))
    co2_passenger = float(row["co2_pasajero"]) if "co2_pasajero" in row else float(row["distancia_km"]) * 0.12
    carried_passengers = int(row["plazas_reservadas"]) if "plazas_reservadas" in row else max(int(row["ocupacion_actual"]) - 1, 0)
    co2_driver = co2_passenger * carried_passengers
    if prefix.startswith("driver"):
        co2_text = f"{co2_driver:.1f} kg ({co2_passenger:.1f} kg x {carried_passengers} pasajeros)"
    else:
        co2_text = f"{co2_passenger:.1f} kg (0,12 kg x {float(row['distancia_km']):.1f} km)"

    st.markdown(
        f"""
        <div class="card">
            <div>{''.join(tags)}</div>
            <div class="card-title">{row['conductor']} · {row['origen']} → Almussafes</div>
            <p class="muted">
                Salida {row['hora_salida']} · Llegada {row['hora_llegada']} · {row['distancia_km']} km · {row['tipo_coche'].capitalize()}
            </p>
            <p>
                <strong>{row['plazas_disponibles']} plazas libres</strong> · <strong>{row['plazas_reservadas'] if 'plazas_reservadas' in row else row['ocupacion_actual']} reservadas</strong> · <strong>{row['precio']:.2f} €</strong> por pasajero ·
                valoración <strong>{row['valoracion']:.1f}/5</strong>
            </p>
            <p class="muted">
                Pickup: <strong>{row['punto_recogida'] if 'punto_recogida' in row else row['origen']}</strong><br>
                Zona destino: <strong>{row['zona_destino'] if 'zona_destino' in row else 'Área industrial'}</strong><br>
                CO2 evitado: <strong>{co2_text}</strong> · Parking: <strong>{row['parking']}</strong>
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if reserve and st.button("Reservar plaza", key=f"{prefix}_reserve_{row['id']}"):
        st.success(f"Reserva enviada a {row['conductor']}. La plaza queda prebloqueada durante 5 minutos.")


def journey_card(mode: str, instruction: str, distance: float, minutes: int, parking: str) -> None:
    st.markdown(
        f"""
        <div class="soft-panel">
            <div class="card-title">Cómo llegar al punto de recogida</div>
            <div class="journey-step"><strong>1. Primer tramo:</strong> {instruction}</div>
            <div class="journey-step"><strong>2. Coche compartido:</strong> viaje directo hasta {parking}.</div>
            <div class="journey-step"><strong>3. Último tramo:</strong> moto disponible si el destino queda alejado.</div>
            <p class="muted">Modo recomendado: <strong>{mode}</strong> · Distancia al pickup: <strong>{distance:.1f} km</strong> · Tiempo estimado: <strong>{minutes} min</strong></p>
        </div>
        """,
        unsafe_allow_html=True,
    )
