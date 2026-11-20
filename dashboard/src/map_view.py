"""PyDeck WebGL map engine with accessible colors and score-based radius.
Built for high-performance rendering over Carto Positron basemap.
"""
from typing import Optional, Dict, Any
import pandas as pd
import pydeck as pdk
import src.config as cfg


def build_pydeck_chart(
    df: pd.DataFrame,
    profile: str = "FAMILIA",
    color_mode: str = "PRECIO",
    selected_listing_id: Optional[str] = None,
    show_crime_heatmap: bool = False,
    crime_metric: str = "VOLUMEN",
    heatmap_df: Optional[pd.DataFrame] = None,
) -> pdk.Deck:
    """Builds a pydeck Deck object with ScatterplotLayer rendered over Carto Positron."""
    # Determine visual encoding attributes
    radius_col = "radius_familia" if profile == "FAMILIA" else "radius_soltero"

    if color_mode == "PRECIO":
        color_col = "color_precio"
    else:
        color_col = "color_rec_familia" if profile == "FAMILIA" else "color_rec_soltero"

    # Default center of CABA
    if df is not None and not df.empty:
        center_lat = float(df["latitud"].median())
        center_lon = float(df["longitud"].median())
    else:
        center_lat = -34.6037
        center_lon = -58.4200

    view_state = pdk.ViewState(
        latitude=center_lat,
        longitude=center_lon,
        zoom=11.6,
        min_zoom=9.0,
        max_zoom=17.0,
        pitch=0,
        bearing=0,
    )

    # Tooltip with HTML markup using pre-formatted fields
    tooltip = {
        "html": """
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 13px; line-height: 1.4; color: #0f172a; padding: 6px; background-color: #ffffff; border-radius: 8px;">
            <b style="font-size: 14px; color: #0f172a;">{barrio}</b> <span style="color: #64748b;">(ID: {listing_id})</span><br/>
            <hr style="margin: 4px 0; border: none; border-top: 1px solid #e2e8f0;"/>
            <b style="color: #334155;">Costo Total:</b> <span style="color: #0f172a; font-weight: 600;">{costo_total_fmt}</span><br/>
            <b style="color: #334155;">Precio Justo:</b> <span style="color: #0f172a;">{precio_justo_fmt}</span><br/>
            <b style="color: #334155;">Desvío:</b> <b style="color: #0f172a;">{desvio_fmt}</b> ({price_status_label})<br/>
            <b style="color: #334155;">Score:</b> <span style="color: #0f766e; font-weight: 600;">{score_fmt}</span> ({active_rec})<br/>
            <b style="color: #334155;">Ambientes:</b> {ambientes} amb. | <b>Cocheras:</b> {cocheras}<br/>
            <b style="color: #334155;">Mascotas:</b> {mascotas_tag}
        </div>
        """,
        "style": {
            "backgroundColor": "#ffffff",
            "color": "#0f172a",
            "boxShadow": "0 10px 15px -3px rgba(0, 0, 0, 0.2), 0 4px 6px -2px rgba(0, 0, 0, 0.1)",
            "borderRadius": "8px",
            "border": "1px solid #cbd5e1",
            "padding": "4px",
            "zIndex": "1000",
        },
    }

    # Prepare DataFrame copy with tooltip helper columns
    plot_df = df.copy() if df is not None and not df.empty else pd.DataFrame()
    if not plot_df.empty:
        plot_df["active_score"] = plot_df["score_familia"] if profile == "FAMILIA" else plot_df["score_soltero_ejecutivo"]
        plot_df["active_rec"] = plot_df["recomendacion_familia"] if profile == "FAMILIA" else plot_df["recomendacion_soltero_ejecutivo"]
        plot_df["mascotas_tag"] = plot_df["apto_mascotas"].apply(lambda x: "Sí (Apto)" if x == 1 else "No apto")

        # Explicitly format numeric fields for pure JS template interpolation in Deck.gl
        plot_df["costo_total_fmt"] = plot_df["costo_total_ars"].apply(lambda x: f"${x:,.0f} ARS")
        plot_df["precio_justo_fmt"] = plot_df["precio_justo_ars"].apply(lambda x: f"${x:,.0f} ARS")
        plot_df["desvio_fmt"] = plot_df["pct_sobreprecio"].apply(lambda x: f"{x:+.1f}%")
        plot_df["score_fmt"] = plot_df["active_score"].apply(lambda x: f"{x:.1f} / 100")

    scatter_layer = pdk.Layer(
        "ScatterplotLayer",
        id="ScatterplotLayer",
        data=plot_df,
        get_position=["longitud", "latitud"],
        get_fill_color=color_col,
        get_radius=radius_col,
        radius_min_pixels=4,
        radius_max_pixels=18,
        stroked=True,
        get_line_color=cfg.SCATTER_STROKE_COLOR,
        line_width_min_pixels=1,
        pickable=True,
        auto_highlight=True,
        highlight_color=[255, 255, 255, 180],
    )

    layers = []

    if show_crime_heatmap:
        hm_source = heatmap_df if (heatmap_df is not None and not heatmap_df.empty) else plot_df
        if hm_source is not None and not hm_source.empty:
            metric_upper = str(crime_metric).strip().upper()
            preferred_col = "crime_weight_grav" if metric_upper == "GRAVEDAD" else "crime_weight_vol"
            fallback_col = "crime_weight_vol" if preferred_col == "crime_weight_grav" else "crime_weight_grav"

            weight_col = None
            if preferred_col in hm_source.columns:
                weight_col = preferred_col
            elif fallback_col in hm_source.columns:
                weight_col = fallback_col

            if weight_col is not None and "longitud" in hm_source.columns and "latitud" in hm_source.columns:
                hm_slim = pd.DataFrame({
                    "longitud": pd.to_numeric(hm_source["longitud"], errors="coerce").round(5),
                    "latitud": pd.to_numeric(hm_source["latitud"], errors="coerce").round(5),
                    "weight": pd.to_numeric(hm_source[weight_col], errors="coerce").fillna(0.0).clip(0.0, 1.0).round(4),
                }).dropna(subset=["longitud", "latitud"])

                if len(hm_slim) > cfg.CRIME_HEATMAP_MAX_POINTS:
                    hm_slim["lat_bin"] = hm_slim["latitud"].round(4)
                    hm_slim["lon_bin"] = hm_slim["longitud"].round(4)
                    hm_slim = (
                        hm_slim.groupby(["lon_bin", "lat_bin"], as_index=False)["weight"]
                        .mean()
                        .rename(columns={"lon_bin": "longitud", "lat_bin": "latitud"})
                    )
                    hm_slim["weight"] = hm_slim["weight"].round(4)

                if not hm_slim.empty:
                    heatmap_layer = pdk.Layer(
                        "HeatmapLayer",
                        id="CrimeHeatmapLayer",
                        data=hm_slim,
                        get_position=["longitud", "latitud"],
                        get_weight="weight",
                        color_range=cfg.CRIME_HEATMAP_COLOR_RANGE,
                        radius_pixels=cfg.CRIME_HEATMAP_RADIUS_PIXELS,
                        intensity=cfg.CRIME_HEATMAP_INTENSITY,
                        threshold=cfg.CRIME_HEATMAP_THRESHOLD,
                        opacity=cfg.CRIME_HEATMAP_OPACITY,
                        pickable=False,
                    )
                    layers.append(heatmap_layer)

    layers.append(scatter_layer)

    deck = pdk.Deck(
        layers=layers,
        initial_view_state=view_state,
        tooltip=tooltip,
        map_style=cfg.CARTO_POSITRON_STYLE,
    )

    return deck
