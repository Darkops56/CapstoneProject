"""Módulo de curación geoespacial e inferencia de Machine Learning del Actor."""

from functools import lru_cache
from pathlib import Path
from typing import Any
import geopandas as gpd
import joblib
import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

try:
    from actor.src import nlp_parser
    from actor.src import scoring
except (ImportError, ModuleNotFoundError):
    from src import nlp_parser
    from src import scoring

BASE_DIR = Path(__file__).resolve().parent.parent
REF_GEO_DIR = BASE_DIR / "reference_geo"
ARTIFACTS_DIR = BASE_DIR / "artifacts"

EARTH_RADIUS_M = 6371000.0
CABA_LAT_MIN = -34.705
CABA_LAT_MAX = -34.525
CABA_LON_MIN = -58.535
CABA_LON_MAX = -58.345
CABA_CENTER_LAT = -34.6037
CABA_CENTER_LON = -58.3816

REQUIRED_10_FEATURES = [
    "apto_mascotas",
    "score_amenities",
    "m2_totales",
    "ruido_db_promedio",
    "densidad_delitos_500m",
    "distancia_escuela_m",
    "lineas_subte_600m",
    "banos",
    "ambientes",
    "cocheras",
]


@lru_cache(maxsize=1)
def load_geo_cache() -> dict[str, Any]:
    """Carga los artefactos de referencia urbana pre-cacheados en memoria."""
    ruido_path = REF_GEO_DIR / "medicion_ruido.parquet"
    delitos_path = REF_GEO_DIR / "delitos_tree.joblib"
    contexto_path = REF_GEO_DIR / "contexto_urbano.parquet"

    if not ruido_path.exists() or not delitos_path.exists() or not contexto_path.exists():
        # Fallback a generarlo en caso de ejecución fresca en desarrollo local
        try:
            from scripts.prepare_geo_cache import build_geo_cache
            build_geo_cache()
        except ImportError:
            raise FileNotFoundError(
                f"Archivos de referencia geoespacial no encontrados en {REF_GEO_DIR} y no es posible construirlos en este entorno."
            )

    gdf_ruido = gpd.read_parquet(ruido_path)
    delitos_bundle = joblib.load(delitos_path)
    contexto_df = pd.read_parquet(contexto_path)

    # BallTree para escuelas
    esc_df = contexto_df[contexto_df["tipo_referencia"] == "escuela"].dropna(subset=["latitud", "longitud"])
    tree_esc = BallTree(np.radians(esc_df[["latitud", "longitud"]].to_numpy()), metric="haversine")

    # BallTree para subte
    subte_df = contexto_df[contexto_df["tipo_referencia"] == "subte"].dropna(subset=["latitud", "longitud"])
    tree_subte = BallTree(np.radians(subte_df[["latitud", "longitud"]].to_numpy()), metric="haversine")
    subte_lineas = subte_df["linea"].astype(str).str.strip().to_numpy()

    return {
        "gdf_ruido": gdf_ruido,
        "delitos_bundle": delitos_bundle,
        "tree_esc": tree_esc,
        "tree_subte": tree_subte,
        "subte_lineas": subte_lineas,
    }


def curate_and_enrich(properties_raw: list[dict[str, Any]]) -> pd.DataFrame:
    """Realiza la curación tabular y cruce geoespacial rápido con el caché urbano."""
    records = []
    for it in properties_raw:
        loc = it.get("location") or {}
        lat_raw = it.get("list_latitude")
        lon_raw = it.get("list_longitude")
        if lat_raw is None or lon_raw is None:
            lat_raw = loc.get("latitude")
            lon_raw = loc.get("longitude")

        # Parseo numérico defensivo de coordenadas
        try:
            lat_f = float(lat_raw) if lat_raw is not None else np.nan
            lon_f = float(lon_raw) if lon_raw is not None else np.nan
        except (ValueError, TypeError):
            lat_f, lon_f = np.nan, np.nan

        tag_auditoria = []
        is_outside = False
        if np.isnan(lat_f) or np.isnan(lon_f):
            is_outside = True
            tag_auditoria.append("AUDIT_COORD_IMPUTED")
        elif not (CABA_LAT_MIN <= lat_f <= CABA_LAT_MAX and CABA_LON_MIN <= lon_f <= CABA_LON_MAX):
            is_outside = True
            tag_auditoria.append("AUDIT_COORD_IMPUTED")
            tag_auditoria.append("AUDIT_COORD_OUTSIDE_CABA")

        lat_clean = CABA_CENTER_LAT if is_outside else lat_f
        lon_clean = CABA_CENTER_LON if is_outside else lon_f

        # Parseo monetario y atributos
        alquiler_ars = nlp_parser.parse_price_ars(
            it.get("list_price_amount"),
            it.get("list_price_currency"),
        )
        exp_val, exp_src = nlp_parser.extract_expenses_ars(it)
        pet_val = nlp_parser.extract_apto_mascotas(it)
        mf = nlp_parser._parse_main_features(it)
        am = nlp_parser.extract_amenities(it)
        barrio, subzona = nlp_parser._extract_barrio_subzona(it)

        # Imputación de precios si vinieran vacíos
        if np.isnan(alquiler_ars) or alquiler_ars <= 0:
            alquiler_ars = 850000.0
            tag_auditoria.append("AUDIT_PRICE_IMPUTED")
        if np.isnan(exp_val) or exp_val < 0:
            exp_val = 120000.0

        costo_total = alquiler_ars + exp_val

        records.append({
            "listing_id": str(it.get("listingId", "")),
            "latitud": lat_clean,
            "longitud": lon_clean,
            "barrio": barrio,
            "subzona": subzona,
            "moneda_origen": str(it.get("list_price_currency", "ARS")),
            "alquiler_ars": float(alquiler_ars),
            "expensas_ars": float(exp_val),
            "costo_total_ars": float(costo_total),
            "apto_mascotas": float(pet_val),
            "score_amenities": float(am.get("score_amenities", 0.0)),
            "m2_totales": float(mf.get("m2_totales") if not np.isnan(mf.get("m2_totales", np.nan)) else 50.0),
            "banos": float(mf.get("banos") if not np.isnan(mf.get("banos", np.nan)) else 1.0),
            "ambientes": float(mf.get("ambientes") if not np.isnan(mf.get("ambientes", np.nan)) else 2.0),
            "cocheras": float(mf.get("cocheras") if not np.isnan(mf.get("cocheras", np.nan)) else 0.0),
            "tag_auditoria": ";".join(tag_auditoria) if tag_auditoria else "VALID",
        })

    df = pd.DataFrame(records)

    # Cruce Geoespacial con Geo-Caché en memoria
    geo_cache = load_geo_cache()

    # 1. Ruido vía spatial join within
    gdf_props = gpd.GeoDataFrame(
        df[["listing_id", "latitud", "longitud"]].copy(),
        geometry=gpd.points_from_xy(df["longitud"], df["latitud"]),
        crs="EPSG:4326",
    )
    joined_ruido = gpd.sjoin(gdf_props, geo_cache["gdf_ruido"], how="left", predicate="within")
    joined_ruido = joined_ruido.groupby(joined_ruido.index).first()

    ruido_prom = joined_ruido["ruido_db_promedio"].fillna(65.0).to_numpy()
    df["ruido_db_promedio"] = np.round(ruido_prom, 1)

    # 2. Delitos a 500m
    del_bundle = geo_cache["delitos_bundle"]
    prop_rad = np.radians(df[["latitud", "longitud"]].to_numpy())
    del_neighbors = del_bundle["tree"].query_radius(prop_rad, r=500.0 / EARTH_RADIUS_M)
    cant_arr = del_bundle["cantidad"]
    df["densidad_delitos_500m"] = [float(cant_arr[idx].sum()) for idx in del_neighbors]

    # 3. Distancia Escuelas
    esc_dist_rad, _ = geo_cache["tree_esc"].query(prop_rad, k=1)
    df["distancia_escuela_m"] = np.round(esc_dist_rad[:, 0] * EARTH_RADIUS_M, 1)

    # 4. Líneas de Subte a 600m
    subte_neighbors = geo_cache["tree_subte"].query_radius(prop_rad, r=600.0 / EARTH_RADIUS_M)
    subte_lineas = geo_cache["subte_lineas"]
    df["lineas_subte_600m"] = [float(len(set(subte_lineas[idx]))) for idx in subte_neighbors]

    # Asegurar que no haya NaNs en las 10 features
    for feat in REQUIRED_10_FEATURES:
        if df[feat].isna().any():
            df[feat] = df[feat].fillna(df[feat].median() if not np.isnan(df[feat].median()) else 0.0)

    return df


def predict_and_score(
    df_curated: pd.DataFrame,
    artifacts_dir: Path | str | None = None,
) -> pd.DataFrame:
    """Ejecuta los modelos K-Means y XGBoost y calcula los scores de decisión."""
    resolved_dir = Path(artifacts_dir) if artifacts_dir else ARTIFACTS_DIR
    artifacts = scoring.load_artifacts(resolved_dir)
    meta = artifacts["metadata"]
    reg_features = meta["regression_features"]
    cluster_features = meta["cluster_features"]
    cluster_labels = meta["cluster_labels"]

    X_reg = df_curated[reg_features].astype(float)
    X_clu = df_curated[cluster_features].astype(float)

    cluster_ids = artifacts["kmeans_pipeline"].predict(X_clu)
    precio_justo = np.clip(artifacts["xgb_model"].predict(X_reg), 1.0, None)

    out = df_curated.copy()
    out["cluster_habitabilidad"] = cluster_ids.astype(int)
    out["cluster_label"] = [cluster_labels[int(cid)] for cid in cluster_ids]
    out["precio_justo_ars"] = np.round(precio_justo, 2)

    costo_pub = out["costo_total_ars"].to_numpy(dtype=float)
    pct_sobreprecio = ((costo_pub - precio_justo) / precio_justo) * 100.0
    pct_ahorro = -pct_sobreprecio

    out["desvio_precio_pct"] = np.round(pct_sobreprecio, 2)
    out["pct_ahorro"] = np.round(pct_ahorro, 2)

    # Scores para ambos perfiles
    scores_fam = [
        scoring.compute_decision_score(
            row,
            cluster_profile_tag=str(row["cluster_label"]),
            pct_ahorro=float(row["pct_ahorro"]),
            profile="FAMILIA",
        )
        for _, row in out.iterrows()
    ]
    scores_solt = [
        scoring.compute_decision_score(
            row,
            cluster_profile_tag=str(row["cluster_label"]),
            pct_ahorro=float(row["pct_ahorro"]),
            profile="SOLTERO_EJECUTIVO",
        )
        for _, row in out.iterrows()
    ]

    out["score_familia"] = [float(np.clip(s, 0.0, 100.0)) for s in scores_fam]
    out["score_soltero"] = [float(np.clip(s, 0.0, 100.0)) for s in scores_solt]
    out["calificacion_familia"] = [
        scoring._classify_recommendation(sc, sp)
        for sc, sp in zip(out["score_familia"], out["desvio_precio_pct"])
    ]
    out["calificacion_soltero"] = [
        scoring._classify_recommendation(sc, sp)
        for sc, sp in zip(out["score_soltero"], out["desvio_precio_pct"])
    ]

    return out
