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

    # Tooltip with HTML markup
    tooltip = {
        "html": """
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 13px; line-height: 1.4; color: #1e293b; padding: 4px;">
            <b style="font-size: 14px; color: #0f172a;">{barrio}</b> <span style="color: #64748b;">(ID: {listing_id})</span><br/>
            <hr style="margin: 4px 0; border: none; border-top: 1px solid #e2e8f0;"/>
            <b>Costo Total:</b> ${costo_total_ars:,.0f} ARS<br/>
            <b>Precio Justo:</b> ${precio_justo_ars:,.0f} ARS<br/>
            <b>Desvío:</b> <b>{pct_sobreprecio:+.1f}%</b> ({price_status_label})<br/>
            <b>Score:</b> {active_score:.1f} / 100 ({active_rec})<br/>
            <b>Ambientes:</b> {ambientes} amb. | <b>Cocheras:</b> {cocheras}<br/>
            <b>Mascotas:</b> {mascotas_tag}
        </div>
        """,
        "style": {
            "backgroundColor": "#ffffff",
            "color": "#1e293b",
            "boxShadow": "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)",
            "borderRadius": "8px",
            "border": "1px solid #cbd5e1",
            "padding": "8px 12px",
            "zIndex": "1000",
        },
    }

    # Prepare DataFrame copy with tooltip helper columns
    plot_df = df.copy() if df is not None and not df.empty else pd.DataFrame()
    if not plot_df.empty:
        plot_df["active_score"] = plot_df["score_familia"] if profile == "FAMILIA" else plot_df["score_soltero_ejecutivo"]
        plot_df["active_rec"] = plot_df["recomendacion_familia"] if profile == "FAMILIA" else plot_df["recomendacion_soltero_ejecutivo"]
        plot_df["mascotas_tag"] = plot_df["apto_mascotas"].apply(lambda x: "Sí (Apto)" if x == 1 else "No apto")

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=plot_df,
        get_position=["longitud", "latitud"],
        get_fill_color=color_col,
        get_radius=radius_col,
        radius_min_pixels=4,
        radius_max_pixels=18,
        pickable=True,
        auto_highlight=True,
        highlight_color=[255, 255, 255, 180],
    )

    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip=tooltip,
        map_style=cfg.CARTO_POSITRON_STYLE,
    )

    return deck
