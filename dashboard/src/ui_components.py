"""UI modular components, KPI cards, property inspector, and 5-state renderers.
Built with clean typography, progressive disclosure, and WCAG 2.2 accessibility
compatible with both Light and Dark themes.
"""
from typing import Dict, Any, List, Optional
import math
import pandas as pd
import streamlit as st
import src.config as cfg


def apply_filters(df: pd.DataFrame, filters: Dict[str, Any]) -> pd.DataFrame:
    """Applies multi-dimensional vector filtering on normalized property DataFrame."""
    if df is None or df.empty:
        return pd.DataFrame()

    mask = pd.Series(True, index=df.index)

    # 1. Budget Range
    min_price = filters.get("min_price")
    max_price = filters.get("max_price")
    if min_price is not None:
        mask &= (df["costo_total_ars"] >= min_price)
    if max_price is not None:
        mask &= (df["costo_total_ars"] <= max_price)

    # 2. Price Status Semaphore
    selected_statuses = filters.get("selected_price_statuses")
    if selected_statuses is not None:
        mask &= df["price_status_key"].isin(selected_statuses)

    # 3. Neighborhoods
    selected_barrios = filters.get("selected_barrios")
    if selected_barrios:
        mask &= df["barrio"].isin(selected_barrios)

    # 4. Rooms (Ambientes)
    min_ambientes = filters.get("min_ambientes")
    if min_ambientes and min_ambientes > 1:
        mask &= (df["ambientes"] >= min_ambientes)

    # 5. Pets & Garage
    if filters.get("apto_mascotas"):
        mask &= (df["apto_mascotas"] == 1)
    if filters.get("con_cochera"):
        mask &= (df["cocheras"] >= 1)

    # 6. Granular Amenities
    for amen in ["has_parrilla", "has_pileta", "has_gimnasio", "has_sum_coworking", "has_seguridad", "has_balcon_terraza"]:
        if filters.get(amen) and amen in df.columns:
            mask &= (df[amen] == 1)

    # 7. Environment & Habitability
    max_ruido = filters.get("max_ruido")
    if max_ruido is not None and "ruido_db_promedio" in df.columns:
        mask &= (df["ruido_db_promedio"] <= max_ruido)

    min_subte = filters.get("min_subte")
    if min_subte is not None and min_subte > 0 and "lineas_subte_600m" in df.columns:
        mask &= (df["lineas_subte_600m"] >= min_subte)

    max_dist_escuela = filters.get("max_dist_escuela")
    if max_dist_escuela is not None and "distancia_escuela_m" in df.columns:
        mask &= (df["distancia_escuela_m"] <= max_dist_escuela)

    selected_clusters = filters.get("selected_clusters")
    if selected_clusters and "cluster_label" in df.columns:
        mask &= df["cluster_label"].isin(selected_clusters)

    return df[mask].reset_index(drop=True)


def render_header_and_controls(
    total_count: int,
    median_price: float,
    pct_opportunities: float,
    source_meta: Dict[str, Any],
    crime_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Renders top bar with profile selector, color mode, price checkboxes, crime heatmap toggle, and KPIs."""
    col_title, col_profile, col_color, col_price = st.columns([2.2, 1.8, 1.8, 4.2], gap="small")

    with col_title:
        st.markdown("<h3 style='margin: 0; padding: 0;'>Observatorio CABA</h3>", unsafe_allow_html=True)
        file_desc = source_meta.get("file_name") or "Conectado"
        source_label = f"☁️ Google Drive ({file_desc})"
        st.markdown(
            f'<span data-testid="data-source-badge" style="background-color: #0F766E; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">{source_label}</span>',
            unsafe_allow_html=True,
        )

    with col_profile:
        profile = st.selectbox(
            "Perfil Activo",
            options=["FAMILIA", "SOLTERO_EJECUTIVO"],
            format_func=lambda x: "👨‍👩‍👧 Familia" if x == "FAMILIA" else "💼 Soltero Ejecutivo",
            key="profile_select",
        )

    with col_color:
        color_mode = st.selectbox(
            "Colorear por",
            options=["PRECIO", "RECOMENDACION"],
            format_func=lambda x: "💰 Semáforo Precio" if x == "PRECIO" else "⭐ Recomendación",
            key="color_mode_select",
        )

    with col_price:
        st.markdown("<div style='font-size: 14px; font-weight: 500; margin-bottom: 2px;'>Condición de Precio</div>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        with c1:
            cb_bajo = st.checkbox("🟢 Oportunidad", value=True, key="cb_bajo")
        with c2:
            cb_justo = st.checkbox("🟡 Justo", value=True, key="cb_justo")
        with c3:
            cb_sobre = st.checkbox("🔴 Sobreprecio", value=True, key="cb_sobre")

        selected_statuses = []
        if cb_bajo:
            selected_statuses.append("BAJO_PRECIO")
        if cb_justo:
            selected_statuses.append("PRECIO_JUSTO")
        if cb_sobre:
            selected_statuses.append("SOBREPRECIO")

    # Crime Heatmap Top Control Strip (uncompressed, full labels visible)
    avail_metrics = (crime_meta or {}).get("available_crime_metrics", [])
    crime_status = (crime_meta or {}).get("crime_heatmap_status", "INFO_CRIME_HEATMAP_UNAVAILABLE")
    heatmap_disabled = len(avail_metrics) == 0

    hm_col_toggle, hm_col_metric = st.columns([2.6, 7.4], gap="small")
    with hm_col_toggle:
        st.markdown('<div data-testid="crime-heatmap-toggle">', unsafe_allow_html=True)
        show_crime_heatmap = st.toggle(
            "🔥 Mapa de Calor: Delitos",
            value=False,
            disabled=heatmap_disabled,
            key="show_crime_heatmap_toggle",
        )
        st.markdown("</div>", unsafe_allow_html=True)

    crime_metric = avail_metrics[0] if avail_metrics else "VOLUMEN"
    with hm_col_metric:
        if heatmap_disabled:
            st.markdown(
                f'<span data-testid="crime-heatmap-status" style="font-size: 12px; color: #94a3b8;">Capa delictiva no disponible ({crime_status})</span>',
                unsafe_allow_html=True,
            )
        elif show_crime_heatmap:
            if len(avail_metrics) > 1:
                crime_metric = st.radio(
                    "Métrica de Delitos",
                    options=avail_metrics,
                    format_func=lambda x: "Volumen (delitos 500m)" if x == "VOLUMEN" else "Gravedad ponderada (500m)",
                    horizontal=True,
                    label_visibility="collapsed",
                    key="crime_metric_select",
                )
            else:
                metric_lbl = "Volumen" if crime_metric == "VOLUMEN" else "Gravedad"
                st.markdown(
                    f'<span data-testid="crime-heatmap-status" style="font-size: 12px; color: #f59e0b;">Solo {metric_lbl} disponible ({crime_status})</span>',
                    unsafe_allow_html=True,
                )

    # KPI Strip
    kpi1, kpi2, kpi3 = st.columns(3)
    with kpi1:
        st.metric(label="Propiedades Visibles", value=f"{total_count:,}")
    with kpi2:
        st.metric(label="Mediana Costo Total", value=f"${median_price:,.0f} ARS" if not math.isnan(median_price) else "$0 ARS")
    with kpi3:
        st.metric(label="Oportunidades (Ahorro)", value=f"{pct_opportunities:.1f}%")

    st.markdown("<hr style='margin: 8px 0 12px 0; border: none; border-top: 1px solid #334155;'/>", unsafe_allow_html=True)

    return {
        "profile": profile,
        "color_mode": color_mode,
        "selected_price_statuses": selected_statuses,
        "show_crime_heatmap": show_crime_heatmap,
        "crime_metric": crime_metric,
    }


def render_sidebar_filters(df: pd.DataFrame, meta: Dict[str, Any]) -> Dict[str, Any]:
    """Renders collapsible sidebar filters with progressive disclosure."""
    st.sidebar.header("Filtros de Propiedades")

    # 1. Budget Filter
    step = 50000
    min_cost = float(df["costo_total_ars"].min()) if not df.empty else 0.0
    max_cost = float(df["costo_total_ars"].max()) if not df.empty else 2000000.0
    slider_min = int(math.floor(min_cost / step) * step)
    slider_max = int(math.ceil(max_cost / step) * step)
    if slider_max <= slider_min:
        slider_max = slider_min + step
    price_range = st.sidebar.slider(
        "Presupuesto Mensual Total (ARS)",
        min_value=slider_min,
        max_value=slider_max,
        value=(slider_min, slider_max),
        step=step,
    )

    # 2. Neighborhoods
    all_barrios = sorted(df["barrio"].dropna().unique().tolist()) if not df.empty else []
    selected_barrios = st.sidebar.multiselect("Barrios", options=all_barrios, default=[])

    # 3. Ambientes
    min_ambientes = st.sidebar.number_input("Ambientes Mínimos", min_value=1, max_value=6, value=1, step=1)

    # 4. Features & Amenities
    st.sidebar.subheader("Amenities & Features")
    col_f1, col_f2 = st.sidebar.columns(2)
    with col_f1:
        apto_mascotas = st.checkbox("🐾 Mascotas", value=False)
        has_parrilla = st.checkbox("🥩 Parrilla", value=False)
        has_gimnasio = st.checkbox("🏋️ Gimnasio", value=False)
    with col_f2:
        con_cochera = st.checkbox("🚗 Cochera", value=False)
        has_pileta = st.checkbox("🏊 Pileta", value=False)
        has_seguridad = st.checkbox("🛡️ Seguridad", value=False)

    # 5. Progressive Disclosure: Urban Environment
    with st.sidebar.expander("Calidad Urbana & Entorno (GCBA)", expanded=False):
        max_ruido = st.slider("Ruido Máximo Diurno (dBA)", min_value=50, max_value=85, value=85, step=1)
        min_subte = st.slider("Líneas de Subte a 600m", min_value=0, max_value=5, value=0, step=1)
        max_dist_escuela = st.slider("Distancia Máx. Escuela (m)", min_value=100, max_value=3000, value=3000, step=100)

        all_clusters = sorted(df["cluster_label"].dropna().unique().tolist()) if "cluster_label" in df.columns else []
        selected_clusters = st.multiselect("Clúster de Habitabilidad", options=all_clusters, default=[])

    return {
        "min_price": price_range[0],
        "max_price": price_range[1],
        "selected_barrios": selected_barrios,
        "min_ambientes": min_ambientes,
        "apto_mascotas": apto_mascotas,
        "con_cochera": con_cochera,
        "has_parrilla": has_parrilla,
        "has_pileta": has_pileta,
        "has_gimnasio": has_gimnasio,
        "has_seguridad": has_seguridad,
        "max_ruido": max_ruido,
        "min_subte": min_subte,
        "max_dist_escuela": max_dist_escuela,
        "selected_clusters": selected_clusters,
    }


def render_property_inspector(row: pd.Series, profile: str) -> None:
    """Renders detailed property inspection view with robust dark/light contrast."""
    st.markdown("#### Ficha Detallada de la Propiedad")

    score_col = "score_familia" if profile == "FAMILIA" else "score_soltero_ejecutivo"
    rec_col = "recomendacion_familia" if profile == "FAMILIA" else "recomendacion_soltero_ejecutivo"

    score_val = float(row.get(score_col, 50.0))
    rec_val = str(row.get(rec_col, "EVALUAR / ALTERNATIVA"))
    desvio = float(row.get("pct_sobreprecio", 0.0))
    status_label = str(row.get("price_status_label", ""))

    badge_bg = "#0F766E" if desvio <= -5.0 else ("#D97706" if desvio <= 10.0 else "#DC2626")

    st.markdown(
        f"""
        <div style="background-color: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 16px; margin-bottom: 16px; color: #f8fafc;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h3 style="margin: 0; color: #ffffff; font-size: 18px;">{row.get('barrio', 'Propiedad')}</h3>
                <span style="background-color: {badge_bg}; color: #ffffff; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: bold;">{status_label} ({desvio:+.1f}%)</span>
            </div>
            <p style="margin: 4px 0 12px 0; color: #94a3b8; font-size: 13px;">ID Publicación: {row.get('listing_id', 'N/A')}</p>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 14px;">
                <div><b style="color: #94a3b8;">Costo Total:</b> <span style="color: #38bdf8; font-weight: bold;">${float(row.get('costo_total_ars', 0)):,.0f} ARS</span></div>
                <div><b style="color: #94a3b8;">Precio Justo:</b> <span style="color: #e2e8f0;">${float(row.get('precio_justo_ars', 0)):,.0f} ARS</span></div>
                <div><b style="color: #94a3b8;">Ambientes:</b> <span style="color: #e2e8f0;">{int(row.get('ambientes', 1))} amb.</span></div>
                <div><b style="color: #94a3b8;">M2 Totales:</b> <span style="color: #e2e8f0;">{float(row.get('m2_totales', 0)):.0f} m²</span></div>
                <div><b style="color: #94a3b8;">Cocheras:</b> <span style="color: #e2e8f0;">{int(row.get('cocheras', 0))}</span></div>
                <div><b style="color: #94a3b8;">Mascotas:</b> <span style="color: #e2e8f0;">{'Sí 🐾' if row.get('apto_mascotas') == 1 else 'No'}</span></div>
            </div>
            <hr style="margin: 12px 0; border: none; border-top: 1px solid #334155;"/>
            <div style="margin-bottom: 8px;">
                <b style="color: #94a3b8;">Score {profile}:</b> <span style="font-size: 16px; font-weight: bold; color: #34d399;">{score_val:.1f} / 100</span>
                <br/><span style="font-size: 12px; color: #cbd5e1;">Dictamen: <b style="color: #ffffff;">{rec_val}</b></span>
            </div>
            <div style="font-size: 12px; color: #94a3b8;">
                <b>Entorno GCBA:</b> Ruido {float(row.get('ruido_db_promedio', 65)):.1f} dBA · Subte {int(row.get('lineas_subte_600m', 0))} líneas · Escuela {float(row.get('distancia_escuela_m', 500)):.0f} m
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("Volver al Listado", key="btn_back_to_list"):
        st.session_state["selected_listing_id"] = None
        st.rerun()


def render_property_card(row: pd.Series, profile: str) -> None:
    """Renders a single compact card with high-contrast text and solid styling."""
    score_col = "score_familia" if profile == "FAMILIA" else "score_soltero_ejecutivo"
    rec_col = "recomendacion_familia" if profile == "FAMILIA" else "recomendacion_soltero_ejecutivo"

    score_val = float(row.get(score_col, 50.0))
    rec_val = str(row.get(rec_col, "EVALUAR / ALTERNATIVA"))
    desvio = float(row.get("pct_sobreprecio", 0.0))
    status_label = str(row.get("price_status_label", ""))
    badge_bg = "#0F766E" if desvio <= -5.0 else ("#D97706" if desvio <= 10.0 else "#DC2626")

    col_info, col_action = st.columns([4.2, 0.8])
    with col_info:
        st.markdown(
            f"""
            <div style="border: 1px solid #334155; border-radius: 8px; padding: 10px 12px; margin-bottom: 8px; background-color: #1e293b; color: #f8fafc;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <b style="font-size: 14px; color: #ffffff;">{row.get('barrio', 'Propiedad')}</b>
                    <span style="background-color: {badge_bg}; color: #ffffff; padding: 2px 7px; border-radius: 8px; font-size: 11px; font-weight: 600;">{status_label}</span>
                </div>
                <div style="font-size: 14px; margin: 5px 0;">
                    <b style="color: #38bdf8;">${float(row.get('costo_total_ars', 0)):,.0f} ARS</b>
                    <span style="color: #94a3b8; font-size: 12px;"> · {int(row.get('ambientes', 1))} amb · {float(row.get('m2_totales', 0)):.0f} m²</span>
                </div>
                <div style="font-size: 12px; color: #cbd5e1;">
                    Score: <b style="color: #34d399;">{score_val:.0f}/100</b> <span style="color: #94a3b8;">({rec_val})</span> · {'🐾 Mascotas' if row.get('apto_mascotas')==1 else 'Sin mascotas'} · {'🚗 Cochera' if row.get('cocheras', 0)>=1 else 'Sin cochera'}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_action:
        if st.button("Ver", key=f"sel_{row['listing_id']}"):
            st.session_state["selected_listing_id"] = str(row["listing_id"])
            st.rerun()


def render_cards_pagination(df_filtered: pd.DataFrame, profile: str) -> None:
    """Renders strictly paginated list of cards (12 per page) inside an independently scrollable container."""
    if df_filtered.empty:
        return

    score_col = "score_familia" if profile == "FAMILIA" else "score_soltero_ejecutivo"
    sorted_df = df_filtered.sort_values(by=score_col, ascending=False).reset_index(drop=True)

    total_items = len(sorted_df)
    total_pages = max(1, math.ceil(total_items / cfg.PAGE_SIZE))

    current_page = st.session_state.get("current_page", 1)
    if current_page > total_pages:
        current_page = 1
        st.session_state["current_page"] = 1

    start_idx = (current_page - 1) * cfg.PAGE_SIZE
    end_idx = min(start_idx + cfg.PAGE_SIZE, total_items)

    st.markdown(f"<div style='font-size: 14px; font-weight: 600; margin-bottom: 8px;'>Listado de Inmuebles ({start_idx + 1}–{end_idx} de {total_items})</div>", unsafe_allow_html=True)

    # Native scrollable container with fixed height so the main page never scrolls
    with st.container(height=580):
        page_items = sorted_df.iloc[start_idx:end_idx]
        for _, row in page_items.iterrows():
            render_property_card(row, profile)

    # Pagination controls
    col_prev, col_num, col_next = st.columns([1, 2, 1])
    with col_prev:
        if current_page > 1:
            if st.button("◀ Anterior", key="btn_prev_page"):
                st.session_state["current_page"] = current_page - 1
                st.rerun()
    with col_num:
        st.markdown(f"<div style='text-align: center; padding-top: 6px; font-size: 13px; color: #94a3b8;'>Página {current_page} de {total_pages}</div>", unsafe_allow_html=True)
    with col_next:
        if current_page < total_pages:
            if st.button("Siguiente ▶", key="btn_next_page"):
                st.session_state["current_page"] = current_page + 1
                st.rerun()


def render_empty_state() -> None:
    """Renders accessible empty state when 0 properties match the filters."""
    st.markdown(
        """
        <div data-testid="ui-state-empty" style="text-align: center; padding: 40px 20px; background-color: #1e293b; border: 2px dashed #475569; border-radius: 12px; margin: 20px 0; color: #f8fafc;">
            <div style="font-size: 40px; margin-bottom: 12px;">🔍</div>
            <h3 style="color: #ffffff; margin-bottom: 8px;">No se encontraron propiedades</h3>
            <p style="color: #94a3b8; font-size: 14px; max-width: 480px; margin: 0 auto 20px auto;">
                Ninguna propiedad coincide con la combinación de filtros actual (código <code>EMPTY_FILTER_RESULTS</code>). Intente flexibilizar el presupuesto o desactivar filtros de amenities.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Restablecer Filtros", key="reset-filters-btn"):
        st.session_state["selected_listing_id"] = None
        st.session_state["current_page"] = 1
        st.rerun()
