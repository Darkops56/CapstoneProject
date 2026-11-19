"""Main Streamlit Entrypoint for the Interactive Property Map Dashboard.
Split-Screen portal layout with PyDeck WebGL, Google Drive ingestion,
and responsive multi-feature filtering.
"""
import sys
import os
from pathlib import Path

# Ensure dashboard directory and parent are on sys.path for robust imports
DASHBOARD_DIR = os.path.dirname(os.path.abspath(__file__))
if DASHBOARD_DIR not in sys.path:
    sys.path.insert(0, DASHBOARD_DIR)

import streamlit as st
import pandas as pd
import numpy as np

import src.config as cfg
import src.data_loader as loader
import src.normalizer as norm
import src.map_view as map_view
import src.ui_components as ui


st.set_page_config(
    page_title="Observatorio Inmobiliario CABA | Zonaprop Maps",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for compact top margin and viewport-friendly layout
st.markdown(
    """
    <style>
    /* Erradicar el margen superior excesivo de Streamlit */
    .block-container {
        padding-top: 1.2rem !important;
        padding-bottom: 1.0rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }
    header[data-testid="stHeader"] {
        background: transparent !important;
        height: 2rem !important;
    }
    /* Estilizar contenedor del mapa */
    div[data-testid="pydeck-map-container"] {
        border-radius: 10px;
        overflow: hidden;
        border: 1px solid #334155;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=900, max_entries=4, show_spinner=False)
def get_cached_normalized_data():
    """Cached loader and normalizer pipeline to prevent disk/API re-reading on reruns."""
    raw_df, source_meta = loader.load_dataset()
    clean_df, norm_meta = norm.normalize_schema(raw_df)
    return clean_df, source_meta, norm_meta


def main():
    # 1. Initialize session state
    if "selected_listing_id" not in st.session_state:
        st.session_state["selected_listing_id"] = None
    if "current_page" not in st.session_state:
        st.session_state["current_page"] = 1

    # 2. Data Loading & Schema Normalization (T=0 Bootstrap)
    with st.spinner("Cargando datos de propiedades..."):
        clean_df, source_meta, norm_meta = get_cached_normalized_data()

    # 3. State Check: Error State
    if clean_df.empty or norm_meta.get("status") == "SCHEMA_INVALID":
        reason = source_meta.get("reason") or norm_meta.get("reason", "ERR_DATA_INIT_FAILED")
        if reason == "ERR_GDRIVE_NOT_CONFIGURED":
            st.markdown(
                """
                <div data-testid="ui-state-error" style="padding: 24px; background-color: #0f172a; border: 1px solid #38bdf8; border-radius: 8px; color: #f1f5f9;">
                    <h3 style="color: #38bdf8; margin-top: 0;">☁️ Conexión con Google Drive Requerida</h3>
                    <p style="color: #94a3b8;">El Observatorio Inmobiliario está configurado para consumir <strong>únicamente datos en vivo desde Google Drive</strong> (sin respaldo de archivos locales).</p>
                    <p style="color: #e2e8f0;">Por favor, configure al menos una de las siguientes opciones en <code>.streamlit/secrets.toml</code> o variables de entorno del despliegue:</p>
                    <ul style="color: #cbd5e1; line-height: 1.8;">
                        <li><code>gdrive_csv_url</code>: Enlace público o de descarga directa al CSV mensual enriquecido.</li>
                        <li><code>gdrive_file_id</code>: ID del archivo en Google Drive.</li>
                        <li><code>gdrive_folder_id</code>: ID de la carpeta en Google Drive (junto con credenciales de Service Account).</li>
                    </ul>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            error_detail = source_meta.get("message") or "No se pudieron cargar los datos desde Google Drive."
            st.markdown(
                f"""
                <div data-testid="ui-state-error" style="padding: 24px; background-color: #450a0a; border: 1px solid #ef4444; border-radius: 8px; color: #fecaca;">
                    <h3 style="color: #f87171; margin-top: 0;">⚠️ Error al obtener datos desde Google Drive</h3>
                    <p>Código canónico: <code>{reason}</code></p>
                    <p>Detalle: {error_detail}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        return

    # 4. Render Sidebar Filters
    sidebar_filters = ui.render_sidebar_filters(clean_df, norm_meta)

    # 5. Fast Preliminary Filter for Dynamic KPIs
    # Read selection state keys for top controls if present
    profile_val = st.session_state.get("profile_select", "FAMILIA")
    cb_b = st.session_state.get("cb_bajo", True)
    cb_j = st.session_state.get("cb_justo", True)
    cb_s = st.session_state.get("cb_sobre", True)
    active_statuses = []
    if cb_b:
        active_statuses.append("BAJO_PRECIO")
    if cb_j:
        active_statuses.append("PRECIO_JUSTO")
    if cb_s:
        active_statuses.append("SOBREPRECIO")

    prelim_filters = {
        **sidebar_filters,
        "selected_price_statuses": active_statuses,
    }
    df_prelim = ui.apply_filters(clean_df, prelim_filters)
    active_count = len(df_prelim)
    active_median = float(df_prelim["costo_total_ars"].median()) if not df_prelim.empty else float("nan")
    active_opps = float((df_prelim["price_status_key"] == "BAJO_PRECIO").mean() * 100.0) if not df_prelim.empty else 0.0

    # Top Control Bar with dynamic KPIs
    top_controls = ui.render_header_and_controls(
        total_count=active_count,
        median_price=active_median,
        pct_opportunities=active_opps,
        source_meta=source_meta,
    )

    # Merge top controls and sidebar filters
    combined_filters = {**sidebar_filters, **top_controls}

    # 6. Final Filtered DataFrame
    df_filtered = ui.apply_filters(clean_df, combined_filters)

    # 7. State Check: Empty State
    if df_filtered.empty:
        ui.render_empty_state()
        return

    # 8. Split-Screen Body Layout: Map (60%) | Detail / Cards (40%)
    col_map, col_details = st.columns([60, 40], gap="medium")

    with col_map:
        st.markdown("<div style='font-size: 14px; font-weight: 600; margin-bottom: 6px;'>Vista Cartográfica CABA</div>", unsafe_allow_html=True)

        # High-Contrast Map Legend (Compatible with Dark & Light Themes)
        color_mode = top_controls["color_mode"]
        if color_mode == "PRECIO":
            legend_html = """
            <div data-testid="map-legend" style="display: flex; gap: 16px; font-size: 12px; margin-bottom: 8px; background: rgba(15, 23, 42, 0.9); padding: 6px 14px; border-radius: 8px; border: 1px solid #334155; width: fit-content; color: #f8fafc;">
                <span><span style="color: #0F766E; font-size: 15px;">●</span> <b>Oportunidad</b> (≤ -5%)</span>
                <span><span style="color: #D97706; font-size: 15px;">●</span> <b>Precio Justo</b> (-5% a +10%)</span>
                <span><span style="color: #DC2626; font-size: 15px;">●</span> <b>Sobreprecio</b> (> +10%)</span>
            </div>
            """
        else:
            legend_html = """
            <div data-testid="map-legend" style="display: flex; gap: 16px; font-size: 12px; margin-bottom: 8px; background: rgba(15, 23, 42, 0.9); padding: 6px 14px; border-radius: 8px; border: 1px solid #334155; width: fit-content; color: #f8fafc;">
                <span><span style="color: #10B981; font-size: 15px;">●</span> Altamente Recom.</span>
                <span><span style="color: #3B82F6; font-size: 15px;">●</span> Recomendada</span>
                <span><span style="color: #EAB308; font-size: 15px;">●</span> Evaluar</span>
                <span><span style="color: #EF4444; font-size: 15px;">●</span> Descartar</span>
            </div>
            """
        st.markdown(legend_html, unsafe_allow_html=True)

        deck = map_view.build_pydeck_chart(
            df=df_filtered,
            profile=top_controls["profile"],
            color_mode=top_controls["color_mode"],
            selected_listing_id=st.session_state["selected_listing_id"],
        )

        # PyDeck WebGL Render container with fixed 650px height
        st.markdown('<div data-testid="pydeck-map-container">', unsafe_allow_html=True)
        pydeck_event = st.pydeck_chart(
            deck,
            on_select="rerun",
            selection_mode="single-object",
            height=650,
        )
        st.markdown("</div>", unsafe_allow_html=True)

        # Capture click event from pydeck selection if available
        if pydeck_event and hasattr(pydeck_event, "selection"):
            indices = pydeck_event.selection.get("indices", {}).get("ScatterplotLayer", [])
            if indices and len(indices) > 0:
                selected_idx = indices[0]
                if selected_idx < len(df_filtered):
                    clicked_id = str(df_filtered.iloc[selected_idx]["listing_id"])
                    if st.session_state["selected_listing_id"] != clicked_id:
                        st.session_state["selected_listing_id"] = clicked_id
                        st.rerun()

    with col_details:
        st.markdown('<div data-testid="property-cards-panel">', unsafe_allow_html=True)

        selected_id = st.session_state.get("selected_listing_id")
        selected_prop = df_filtered[df_filtered["listing_id"].astype(str) == str(selected_id)] if selected_id else None

        if selected_prop is not None and not selected_prop.empty:
            ui.render_property_inspector(selected_prop.iloc[0], top_controls["profile"])
        else:
            ui.render_cards_pagination(df_filtered, top_controls["profile"])

        st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
