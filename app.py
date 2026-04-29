# pip install -r requirements.txt

#p


from __future__ import annotations

import streamlit as st

from modules.data import load_app_data
from modules.theme import apply_theme
from modules.ui import app_shell, compact_header, official_footer, persona_summary, selection_card
from modules.views.tribbu import render_tribbu_workspace
from modules.views.user import render_user_workspace


st.set_page_config(
    page_title="Tribbu | Almussafes",
    page_icon="T",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def main() -> None:
    apply_theme()
    data = load_app_data()

    if "workspace" not in st.session_state:
        app_shell()
        st.markdown('<div class="selector-grid">', unsafe_allow_html=True)
        left, right = st.columns(2)
        with left:
            if selection_card(
                "Soy usuario",
                "Acceso para trabajadores: buscar coche, publicar ruta, gestionar reservas y usar servicios asociados.",
                "Entrar como usuario",
                "choose_user",
            ):
                st.session_state.workspace = "Usuario"
                st.rerun()
        with right:
            if selection_card(
                "Equipo Tribbu",
                "Acceso operativo: demanda, oferta, rutas calientes, parkings, motos, lockers, KPIs y alertas.",
                "Entrar como equipo Tribbu",
                "choose_tribbu",
            ):
                st.session_state.workspace = "Equipo Tribbu"
                st.session_state.persona = "Equipo Tribbu"
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        official_footer()
        return

    workspace = st.session_state.workspace

    if workspace == "Usuario" and "persona" not in st.session_state:
        compact_header("Usuario", "Seleccionar perfil")
        persona_summary("Usuario", "Usuario")
        st.markdown('<div class="selector-grid">', unsafe_allow_html=True)
        left, right = st.columns(2)
        with left:
            if selection_card(
                "Pasajero",
                "Encuentra una ruta compatible, consulta cómo llegar al punto de recogida y reserva servicios de última milla.",
                "Continuar como pasajero",
                "choose_passenger",
            ):
                st.session_state.persona = "Pasajero"
                st.rerun()
        with right:
            if selection_card(
                "Conductor",
                "Publica tu ruta, gestiona plazas y activa incentivos por ocupación o servicios adicionales.",
                "Continuar como conductor",
                "choose_driver",
            ):
                st.session_state.persona = "Conductor"
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        if st.button("Volver al menú inicial", key="back_to_workspace"):
            st.session_state.pop("workspace", None)
            st.session_state.pop("persona", None)
            st.rerun()
        official_footer()
        return

    persona = st.session_state.get("persona", "Equipo Tribbu")
    compact_header(workspace, persona)

    top_left, top_right = st.columns([1, 4])
    with top_left:
        if st.button("Cambiar perfil", key="change_profile"):
            st.session_state.pop("workspace", None)
            st.session_state.pop("persona", None)
            st.rerun()
    with top_right:
        persona_summary(workspace, persona)

    if workspace == "Usuario":
        render_user_workspace(data, persona)
    else:
        render_tribbu_workspace(data, persona)

    official_footer()


if __name__ == "__main__":
    main()
