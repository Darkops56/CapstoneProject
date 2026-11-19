"""UI modular components, KPI cards, property inspector, and 5-state renderers.
Built with clean typography, progressive disclosure, and WCAG 2.2 accessibility.
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
    if selected_statuses:
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
) -> Dict[str, Any]:
    """Renders single-row top bar with profile selector, price semaphores, color mode, and KPIs."""
    col_title, col_profile, col_color, col_price = st.columns([3, 2, 2, 3], gap="medium")

    with col_title:
        st.markdown("### Observatorio CABA")
        source_label = "Google Drive (Actual)" if source_meta.get("reason") == "SOURCE_GDRIVE_LATEST" else "Datos Locales (Offline)"
        badge_color = "#0F766E" if "GDRIVE" in source_meta.get("reason", "") else "#64748B"
        st.markdown(
            f'<span data-testid="data-source-badge" style="background-color: {badge_color}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;">{source_label}</span>',
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
        status_opts = ["BAJO_PRECIO", "PRECIO_JUSTO", "SOBREPRECIO"]
        selected_statuses = st.multiselect(
            "Condición de Precio",
            options=status_opts,
            default=status_opts,
            format_func=lambda x: "🟢 Oportunidad (≤ -5%)" if x == "BAJO_PRECIO" else ("🟡 Precio Justo" if x == "PRECIO_JUSTO" else "🔴 Sobreprecio (> +10%)"),
            key="status_multiselect",
        )

    # KPI Strip
    kpi1, kpi2, kpi3 = st.columns(3)
    with kpi1:
        st.metric(label="Propiedades Visibles", value=f"{total_count:,}")
    with kpi2:
        st.metric(label="Mediana Costo Total", value=f"${median_price:,.0f} ARS")
    with kpi3:
        st.metric(label="Oportunidades (Ahorro)", value=f"{pct_opportunities:.1f}%")

    st.markdown("---")

    return {
        "profile": profile,
        "color_mode": color_mode,
        "selected_price_statuses": selected_statuses,
    }


def render_sidebar_filters(df: pd.DataFrame, meta: Dict[str, Any]) -> Dict[str, Any]:
    """Renders collapsible sidebar filters with progressive disclosure."""
    st.sidebar.header("Filtros de Propiedades")

    # 1. Budget Filter
    min_cost = float(df["costo_total_ars"].min()) if not df.empty else 0.0
    max_cost = float(df["costo_total_ars"].max()) if not df.empty else 2000000.0
    price_range = st.sidebar.slider(
        "Presupuesto Mensual Total (ARS)",
        min_value=int(min_cost),
        max_value=int(max_cost),
        value=(int(min_cost), int(max_cost)),
        step=50000,
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
    """Renders detailed property inspection view."""
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
        <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 16px; margin-bottom: 16px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h3 style="margin: 0; color: #0f172a;">{row.get('barrio', 'Propiedad')}</h3>
                <span style="background-color: {badge_bg}; color: white; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: bold;">{status_label} ({desvio:+.1f}%)</span>
            </div>
            <p style="margin: 4px 0 12px 0; color: #64748b; font-size: 13px;">ID Publicación: {row.get('listing_id', 'N/A')}</p>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 14px;">
                <div><b>Costo Total:</b> ${float(row.get('costo_total_ars', 0)):,.0f} ARS</div>
                <div><b>Precio Justo Teórico:</b> ${float(row.get('precio_justo_ars', 0)):,.0f} ARS</div>
                <div><b>Ambientes:</b> {int(row.get('ambientes', 1))} amb.</div>
                <div><b>M2 Totales:</b> {float(row.get('m2_totales', 0)):.0f} m²</div>
                <div><b>Cocheras:</b> {int(row.get('cocheras', 0))}</div>
                <div><b>Apto Mascotas:</b> {'Sí 🐾' if row.get('apto_mascotas') == 1 else 'No'}</div>
            </div>
            <hr style="margin: 12px 0; border: none; border-top: 1px solid #e2e8f0;"/>
            <div style="margin-bottom: 8px;">
                <b>Score {profile} (0-100):</b> <span style="font-size: 16px; font-weight: bold; color: #0f766e;">{score_val:.1f} / 100</span>
                <br/><span style="font-size: 12px; color: #475569;">Dictamen: <b>{rec_val}</b></span>
            </div>
            <div style="font-size: 12px; color: #475569;">
                <b>Entorno GCBA:</b> Ruido {float(row.get('ruido_db_promedio', 65)):.1f} dBA | Subte {int(row.get('lineas_subte_600m', 0))} líneas | Escuela {float(row.get('distancia_escuela_m', 500)):.0f} m
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("Volver al Listado", key="btn_back_to_list"):
        st.session_state["selected_listing_id"] = None
        st.rerun()


def render_property_card(row: pd.Series, profile: str) -> None:
    """Renders a single compact card in the listing panel."""
    score_col = "score_familia" if profile == "FAMILIA" else "score_soltero_ejecutivo"
    rec_col = "recomendacion_familia" if profile == "FAMILIA" else "recomendacion_soltero_ejecutivo"

    score_val = float(row.get(score_col, 50.0))
    rec_val = str(row.get(rec_col, "EVALUAR / ALTERNATIVA"))
    desvio = float(row.get("pct_sobreprecio", 0.0))
    status_label = str(row.get("price_status_label", ""))
    badge_bg = "#0F766E" if desvio <= -5.0 else ("#D97706" if desvio <= 10.0 else "#DC2626")

    col_info, col_action = st.columns([4, 1])
    with col_info:
        st.markdown(
            f"""
            <div style="border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px; margin-bottom: 8px; background: white;">
                <div style="display: flex; justify-content: space-between;">
                    <b style="font-size: 14px; color: #0f172a;">{row.get('barrio', 'Propiedad')}</b>
                    <span style="background: {badge_bg}; color: white; padding: 2px 6px; border-radius: 8px; font-size: 11px;">{status_label}</span>
                </div>
                <div style="font-size: 13px; margin: 4px 0;">
                    <b>${float(row.get('costo_total_ars', 0)):,.0f} ARS</b> · {int(row.get('ambientes', 1))} amb · {float(row.get('m2_totales', 0)):.0f} m²
                </div>
                <div style="font-size: 11px; color: #64748b;">
                    Score: <b>{score_val:.0f}/100</b> ({rec_val}) · {'🐾 Mascotas' if row.get('apto_mascotas')==1 else 'Sin mascotas'} · {'🚗 Cochera' if row.get('cocheras', 0)>=1 else 'Sin cochera'}
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
    """Renders strictly paginated list of cards (12 per page) ordered by score descending."""
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

    st.markdown(f"**Listado de Inmuebles** ({start_idx + 1}–{end_idx} de {total_items})")

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
        st.markdown(f"<div style='text-align: center; padding-top: 6px; font-size: 13px;'>Página {current_page} de {total_pages}</div>", unsafe_allow_html=True)
    with col_next:
        if current_page < total_pages:
            if st.button("Siguiente ▶", key="btn_next_page"):
                st.session_state["current_page"] = current_page + 1
                st.rerun()


def render_empty_state() -> None:
    """Renders accessible empty state when 0 properties match the filters."""
    st.markdown(
        """
        <div data-testid="ui-state-empty" style="text-align: center; padding: 40px 20px; background-color: #f8fafc; border: 2px dashed #cbd5e1; border-radius: 12px; margin: 20px 0;">
            <div style="font-size: 40px; margin-bottom: 12px;">🔍</div>
            <h3 style="color: #1e293b; margin-bottom: 8px;">No se encontraron propiedades</h3>
            <p style="color: #64748b; font-size: 14px; max-width: 480px; margin: 0 auto 20px auto;">
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
