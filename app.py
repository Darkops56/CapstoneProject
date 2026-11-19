"""Main Streamlit Entrypoint for the Interactive Property Map Dashboard.
Split-Screen portal layout with PyDeck WebGL, Google Drive ingestion,
and responsive multi-feature filtering.
"""
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
        st.markdown(
            f"""
            <div data-testid="ui-state-error" style="padding: 24px; background-color: #fef2f2; border: 1px solid #f87171; border-radius: 8px; color: #991b1b;">
                <h3>⚠️ Error al inicializar el catálogo inmobiliario</h3>
                <p>Código canónico: <code>{norm_meta.get('reason', 'ERR_DATA_INIT_FAILED')}</code></p>
                <p>Detalle: No se pudieron cargar los datos obligatorios. Verifique la fuente de datos o el archivo de fallback.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    # 4. Render Sidebar Filters
    sidebar_filters = ui.render_sidebar_filters(clean_df, norm_meta)

    # 5. Preliminary filtering to derive active KPIs
    # Calculate initial stats for top header
    all_median_price = float(clean_df["costo_total_ars"].median())
    all_opps = float((clean_df["price_status_key"] == "BAJO_PRECIO").mean() * 100.0)

    # Top Control Bar
    top_controls = ui.render_header_and_controls(
        total_count=len(clean_df),
        median_price=all_median_price,
        pct_opportunities=all_opps,
        source_meta=source_meta,
    )

    # Merge top controls and sidebar filters
    combined_filters = {**sidebar_filters, **top_controls}

    # 6. Multi-Feature Filtering
    df_filtered = ui.apply_filters(clean_df, combined_filters)

    # 7. State Check: Empty State
    if df_filtered.empty:
        ui.render_empty_state()
        return

    # 8. Split-Screen Body Layout: Map (62%) | Detail / Cards (38%)
    col_map, col_details = st.columns([62, 38], gap="medium")

    with col_map:
        st.markdown("##### Vista Satelital y Distribución CABA")

        # Map Legend
        color_mode = top_controls["color_mode"]
        if color_mode == "PRECIO":
            legend_html = """
            <div data-testid="map-legend" style="display: flex; gap: 16px; font-size: 12px; margin-bottom: 8px; background: white; padding: 6px 12px; border-radius: 6px; border: 1px solid #e2e8f0; width: fit-content;">
                <span><span style="color: #0F766E; font-size: 14px;">●</span> <b>Oportunidad</b> (≤ -5%)</span>
                <span><span style="color: #D97706; font-size: 14px;">●</span> <b>Precio Justo</b> (-5% a +10%)</span>
                <span><span style="color: #DC2626; font-size: 14px;">●</span> <b>Sobreprecio</b> (> +10%)</span>
            </div>
            """
        else:
            legend_html = """
            <div data-testid="map-legend" style="display: flex; gap: 16px; font-size: 12px; margin-bottom: 8px; background: white; padding: 6px 12px; border-radius: 6px; border: 1px solid #e2e8f0; width: fit-content;">
                <span><span style="color: #10B981; font-size: 14px;">●</span> Altamente Recom.</span>
                <span><span style="color: #3B82F6; font-size: 14px;">●</span> Recomendada</span>
                <span><span style="color: #EAB308; font-size: 14px;">●</span> Evaluar</span>
                <span><span style="color: #EF4444; font-size: 14px;">●</span> Descartar</span>
            </div>
            """
        st.markdown(legend_html, unsafe_allow_html=True)

        deck = map_view.build_pydeck_chart(
            df=df_filtered,
            profile=top_controls["profile"],
            color_mode=top_controls["color_mode"],
            selected_listing_id=st.session_state["selected_listing_id"],
        )

        # PyDeck WebGL Render container
        st.markdown('<div data-testid="pydeck-map-container">', unsafe_allow_html=True)
        pydeck_event = st.pydeck_chart(
            deck,
            on_select="rerun",
            selection_mode="single-object",
            use_container_width=True,
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
