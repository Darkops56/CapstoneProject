"""Schema normalizer and business rule engine.
Handles column alias reconciliation, geographic boundaries, price semaphores,
and graceful degradation of feature flags.
"""
from typing import Dict, Any, Tuple, List
import numpy as np
import pandas as pd
import src.config as cfg


REQUIRED_COLUMNS = ["listing_id", "latitud", "longitud", "costo_total_ars", "precio_justo_ars"]

GRANULAR_AMENITY_COLS = [
    "has_parrilla",
    "has_pileta",
    "has_gimnasio",
    "has_sum_coworking",
    "has_seguridad",
    "has_balcon_terraza",
    "has_cochera",
]

ALIAS_MAP = {
    "desvio_precio_pct": "pct_sobreprecio",
    "cluster_habitabilidad": "cluster_id",
    "score_soltero": "score_soltero_ejecutivo",
    "calificacion_familia": "recomendacion_familia",
    "calificacion_soltero": "recomendacion_soltero_ejecutivo",
}


def classify_price_status(pct_sobreprecio: float) -> Tuple[str, str, List[int]]:
    """Classifies price deviation into standard categories, accessible label, and RGBA color.
    <= -5.0%: Bajo Precio (Oportunidad)
    -5.0% < x <= 10.0%: Precio Justo (Mercado)
    > 10.0%: Sobreprecio
    """
    if np.isnan(pct_sobreprecio):
        return "DESCONOCIDO", "Sin datos", cfg.COLOR_DEFAULT

    if pct_sobreprecio <= cfg.PRICE_CUT_LOW_PCT:
        return "BAJO_PRECIO", "v Bajo Precio (Oportunidad)", cfg.COLOR_BAJO_PRECIO
    elif pct_sobreprecio <= cfg.PRICE_CUT_HIGH_PCT:
        return "PRECIO_JUSTO", "= Precio Justo", cfg.COLOR_PRECIO_JUSTO
    else:
        return "SOBREPRECIO", "^ Sobreprecio", cfg.COLOR_SOBREPRECIO


def classify_recommendation_color(recommendation: str) -> List[int]:
    """Returns RGBA color based on recommendation category."""
    rec_upper = str(recommendation).strip().upper()
    if "ALTAMENTE" in rec_upper:
        return cfg.COLOR_ALTAMENTE_RECOMENDADA
    elif "RECOMENDADA" in rec_upper:
        return cfg.COLOR_RECOMENDADA
    elif "DESCARTAR" in rec_upper or "SOBREPRECIO ALTO" in rec_upper:
        return cfg.COLOR_DESCARTAR
    else:
        return cfg.COLOR_EVALUAR


def normalize_schema(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Normalizes column names, checks required columns, filters CABA bbox,
    and pre-computes visual encoding columns (colors, radii, status tags).
    """
    if df is None or df.empty:
        return pd.DataFrame(), {
            "status": "SCHEMA_INVALID",
            "reason": "ERR_SCHEMA_EMPTY_DATASET",
            "missing_columns": REQUIRED_COLUMNS,
        }

    out = df.copy()

    # 1. Column Alias Reconciliation
    for old_col, new_col in ALIAS_MAP.items():
        if old_col in out.columns and new_col not in out.columns:
            out = out.rename(columns={old_col: new_col})

    # 2. Check for missing required columns
    missing = [c for c in REQUIRED_COLUMNS if c not in out.columns]
    if missing:
        # Check if pct_sobreprecio can be derived or if columns are truly missing
        if "precio_justo_ars" in missing and "costo_total_ars" in out.columns and "pct_sobreprecio" in out.columns:
            # Can reconstruct precio_justo_ars = costo_total / (1 + pct_sobreprecio/100)
            out["precio_justo_ars"] = out["costo_total_ars"] / (1.0 + out["pct_sobreprecio"] / 100.0)
            missing.remove("precio_justo_ars")

    if missing:
        return pd.DataFrame(), {
            "status": "SCHEMA_INVALID",
            "reason": "ERR_SCHEMA_MISSING_REQUIRED_COLUMNS",
            "missing_columns": missing,
        }

    # 3. Numeric Coercion
    out["latitud"] = pd.to_numeric(out["latitud"], errors="coerce")
    out["longitud"] = pd.to_numeric(out["longitud"], errors="coerce")
    out["costo_total_ars"] = pd.to_numeric(out["costo_total_ars"], errors="coerce").fillna(0.0)
    out["precio_justo_ars"] = pd.to_numeric(out["precio_justo_ars"], errors="coerce").fillna(1.0)
    out["precio_justo_ars"] = np.maximum(out["precio_justo_ars"], 1.0)

    # Derive pct_sobreprecio if not present
    if "pct_sobreprecio" not in out.columns:
        out["pct_sobreprecio"] = ((out["costo_total_ars"] - out["precio_justo_ars"]) / out["precio_justo_ars"]) * 100.0
    else:
        out["pct_sobreprecio"] = pd.to_numeric(out["pct_sobreprecio"], errors="coerce").fillna(0.0)

    # Derive default scores if not present
    if "score_familia" not in out.columns:
        out["score_familia"] = 50.0
    if "score_soltero_ejecutivo" not in out.columns:
        out["score_soltero_ejecutivo"] = 50.0

    if "recomendacion_familia" not in out.columns:
        out["recomendacion_familia"] = "EVALUAR / ALTERNATIVA"
    if "recomendacion_soltero_ejecutivo" not in out.columns:
        out["recomendacion_soltero_ejecutivo"] = "EVALUAR / ALTERNATIVA"

    if "barrio" not in out.columns:
        out["barrio"] = "Sin especificar"
    if "ambientes" not in out.columns:
        out["ambientes"] = 1
    if "cocheras" not in out.columns:
        out["cocheras"] = 0
    if "apto_mascotas" not in out.columns:
        out["apto_mascotas"] = 0

    # 4. Filter CABA Bounding Box
    initial_count = len(out)
    valid_coords = (
        out["latitud"].notna() &
        out["longitud"].notna() &
        (out["latitud"] >= cfg.CABA_BBOX["lat_min"]) &
        (out["latitud"] <= cfg.CABA_BBOX["lat_max"]) &
        (out["longitud"] >= cfg.CABA_BBOX["lon_min"]) &
        (out["longitud"] <= cfg.CABA_BBOX["lon_max"])
    )
    dropped_count = int((~valid_coords).sum())
    out = out[valid_coords].reset_index(drop=True)

    if out.empty:
        return pd.DataFrame(), {
            "status": "SCHEMA_INVALID",
            "reason": "ERR_EMPTY_DATASET_AFTER_GEO_CLEAN",
            "dropped_out_of_bounds": dropped_count,
        }

    # 5. Precompute Visual Encodings
    price_classes = [classify_price_status(p) for p in out["pct_sobreprecio"]]
    out["price_status_key"] = [p[0] for p in price_classes]
    out["price_status_label"] = [p[1] for p in price_classes]
    out["color_precio"] = [p[2] for p in price_classes]

    out["color_rec_familia"] = [classify_recommendation_color(r) for r in out["recomendacion_familia"]]
    out["color_rec_soltero"] = [classify_recommendation_color(r) for r in out["recomendacion_soltero_ejecutivo"]]

    # Score-based radius in meters for PyDeck: 35m to 110m
    out["radius_familia"] = 35.0 + (np.clip(out["score_familia"], 0.0, 100.0) / 100.0) * 75.0
    out["radius_soltero"] = 35.0 + (np.clip(out["score_soltero_ejecutivo"], 0.0, 100.0) / 100.0) * 75.0

    # 6. Check Available Amenity Flags
    available_amenities = [col for col in GRANULAR_AMENITY_COLS if col in out.columns]
    amenities_status = (
        "INFO_FULL_AMENITIES_AVAILABLE" if len(available_amenities) > 0
        else "INFO_GRANULAR_AMENITIES_UNAVAILABLE"
    )

    meta = {
        "status": "SCHEMA_VALID",
        "reason": "OK_NORMALIZED",
        "total_input_rows": initial_count,
        "valid_rows": len(out),
        "dropped_out_of_bounds": dropped_count,
        "audit_tag": "AUDIT_OUT_OF_BOUNDS_DROPPED" if dropped_count > 0 else "VALID_COORDS",
        "available_amenities": available_amenities,
        "amenities_status": amenities_status,
    }

    return out, meta
