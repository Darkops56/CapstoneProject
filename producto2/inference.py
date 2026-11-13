"""Módulo de inferencia y scoring de decisión corporativa (Producto 2)."""

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import joblib
import numpy as np
import pandas as pd

from config import settings as config

ProfileType = Literal["FAMILIA", "SOLTERO_EJECUTIVO"]

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


@lru_cache(maxsize=2)
def load_artifacts(artifacts_dir: Path | str = config.PRODUCTO2_ARTIFACTS_DIR) -> dict[str, Any]:
    """Carga los artefactos .joblib entrenados (K-Means, XGBoost y metadatos)."""
    adir = Path(artifacts_dir)
    return {
        "kmeans_pipeline": joblib.load(adir / "kmeans_model.joblib"),
        "xgb_model": joblib.load(adir / "xgb_price_model.joblib"),
        "metadata": joblib.load(adir / "model_metadata.joblib"),
    }


def compute_decision_score(
    features: dict[str, float] | pd.Series,
    cluster_profile_tag: str,
    pct_ahorro: float,
    profile: ProfileType = "FAMILIA",
) -> float:
    """
    Calcula Score de Decisión (0 a 100) combinando:
    - Ahorro respecto al precio justo teórico (40 pts máx)
    - Adecuación de clúster urbano al perfil (25 pts máx)
    - Amenidades, mascotas y atributos clave del perfil (35 pts máx)
    """
    profile_norm = str(profile).strip().upper()
    if profile_norm not in {"FAMILIA", "SOLTERO_EJECUTIVO"}:
        raise ValueError(f"Perfil no soportado: {profile}. Use 'FAMILIA' o 'SOLTERO_EJECUTIVO'.")

    # 1. Componente económico: ahorro vs precio justo (0..40 pts; 0% ahorro = 20 pts, +25% ahorro = 40 pts, -25% = 0 pts)
    ahorro_clipped = float(np.clip(pct_ahorro, -25.0, 25.0))
    score_economico = ((ahorro_clipped + 25.0) / 50.0) * 40.0

    # 2. Componente clúster de habitabilidad (0..25 pts)
    tag = cluster_profile_tag.lower()
    if profile_norm == "FAMILIA":
        if "familiar" in tag or "tranquil" in tag:
            score_cluster = 25.0
        elif "conectado" in tag or "equilibrad" in tag:
            score_cluster = 16.0
        else:
            score_cluster = 8.0
    else:  # SOLTERO_EJECUTIVO
        if "conectado" in tag or "ejecutivo" in tag or "hub" in tag:
            score_cluster = 25.0
        elif "equilibrad" in tag or "familiar" in tag or "tranquil" in tag:
            score_cluster = 16.0
        else:
            score_cluster = 10.0

    # 3. Componente adecuación física + mascotas + amenities (0..35 pts)
    amenities = float(np.clip(float(features.get("score_amenities", 0.0)) / 10.0, 0.0, 1.0))
    mascotas = 1.0 if float(features.get("apto_mascotas", 0.0)) >= 1.0 else 0.0
    cocheras = 1.0 if float(features.get("cocheras", 0.0)) >= 1.0 else 0.0
    ambientes = float(features.get("ambientes", 1.0))
    ruido = float(features.get("ruido_db_promedio", 70.0))
    lineas_subte = float(features.get("lineas_subte_600m", 0.0))
    dist_escuela = float(features.get("distancia_escuela_m", 300.0))

    if profile_norm == "FAMILIA":
        espacio_fit = float(np.clip((ambientes - 1.0) / 3.0, 0.0, 1.0))  # 4+ amb = 1.0
        calma_fit = float(np.clip((75.0 - ruido) / 15.0, 0.0, 1.0))
        escuela_fit = float(np.clip(1.0 - (dist_escuela / 600.0), 0.0, 1.0))
        score_perfil = (
            10.0 * espacio_fit
            + 7.0 * amenities
            + 6.0 * mascotas
            + 5.0 * cocheras
            + 4.0 * calma_fit
            + 3.0 * escuela_fit
        )
    else:  # SOLTERO_EJECUTIVO
        subte_fit = float(np.clip(lineas_subte / 2.0, 0.0, 1.0))
        agil_fit = 1.0 if 1.0 <= ambientes <= 3.0 else 0.6
        score_perfil = (
            12.0 * amenities
            + 11.0 * subte_fit
            + 6.0 * agil_fit
            + 4.0 * mascotas
            + 2.0 * cocheras
        )

    total = score_economico + score_cluster + score_perfil
    return round(float(np.clip(total, 0.0, 100.0)), 2)


def _classify_recommendation(decision_score: float, pct_sobreprecio: float) -> str:
    if decision_score >= 75.0 and pct_sobreprecio <= 5.0:
        return "ALTAMENTE RECOMENDADA"
    if decision_score >= 55.0 and pct_sobreprecio <= 15.0:
        return "RECOMENDADA"
    if pct_sobreprecio > 20.0:
        return "DESCARTAR / SOBREPRECIO ALTO"
    return "EVALUAR / ALTERNATIVA"


def predict_batch(
    df: pd.DataFrame,
    profile: ProfileType = "FAMILIA",
    published_price_col: str | None = "costo_total_ars",
    artifacts_dir: Path | str = config.PRODUCTO2_ARTIFACTS_DIR,
) -> pd.DataFrame:
    """Ejecuta inferencia batch (K-Means + XGBoost + Score 0-100) sobre un DataFrame."""
    artifacts = load_artifacts(artifacts_dir)
    meta = artifacts["metadata"]
    reg_features = meta["regression_features"]
    cluster_features = meta["cluster_features"]
    cluster_labels = meta["cluster_labels"]

    missing_reg = [c for c in reg_features if c not in df.columns]
    if missing_reg:
        raise ValueError(f"Faltan features requeridas para inferencia: {missing_reg}")

    X_reg = df[reg_features].astype(float)
    X_clu = df[cluster_features].astype(float)

    cluster_ids = artifacts["kmeans_pipeline"].predict(X_clu)
    precio_justo = np.clip(artifacts["xgb_model"].predict(X_reg), 1.0, None)

    out = df.copy()
    out["cluster_id"] = cluster_ids.astype(int)
    out["cluster_label"] = [cluster_labels[int(cid)] for cid in cluster_ids]
    out["precio_justo_ars"] = np.round(precio_justo, 2)

    if published_price_col and published_price_col in out.columns:
        pub = out[published_price_col].astype(float).to_numpy()
        pct_sobreprecio = ((pub - precio_justo) / precio_justo) * 100.0
        pct_ahorro = -pct_sobreprecio
    else:
        pct_sobreprecio = np.zeros(len(out), dtype=float)
        pct_ahorro = np.zeros(len(out), dtype=float)

    out["pct_sobreprecio"] = np.round(pct_sobreprecio, 2)
    out["pct_ahorro"] = np.round(pct_ahorro, 2)

    scores = [
        compute_decision_score(
            row,
            cluster_profile_tag=str(row["cluster_label"]),
            pct_ahorro=float(row["pct_ahorro"]),
            profile=profile,
        )
        for _, row in out.iterrows()
    ]
    out["decision_score_0_100"] = scores
    out["recomendacion"] = [
        _classify_recommendation(sc, sp) for sc, sp in zip(out["decision_score_0_100"], out["pct_sobreprecio"])
    ]
    return out


def predict_property(
    features: dict[str, float],
    profile: ProfileType = "FAMILIA",
    precio_publicado_ars: float | None = None,
    artifacts_dir: Path | str = config.PRODUCTO2_ARTIFACTS_DIR,
) -> dict[str, Any]:
    """Ejecuta inferencia para una única propiedad en formato diccionario."""
    row = dict(features)
    pub_col = None
    if precio_publicado_ars is not None:
        row["costo_total_ars"] = float(precio_publicado_ars)
        pub_col = "costo_total_ars"

    res_df = predict_batch(
        pd.DataFrame([row]),
        profile=profile,
        published_price_col=pub_col,
        artifacts_dir=artifacts_dir,
    )
    rec = res_df.iloc[0]
    return {
        "profile": profile,
        "cluster_id": int(rec["cluster_id"]),
        "cluster_label": str(rec["cluster_label"]),
        "precio_justo_ars": float(rec["precio_justo_ars"]),
        "pct_sobreprecio": float(rec["pct_sobreprecio"]),
        "pct_ahorro": float(rec["pct_ahorro"]),
        "decision_score_0_100": float(rec["decision_score_0_100"]),
        "recomendacion": str(rec["recomendacion"]),
    }
