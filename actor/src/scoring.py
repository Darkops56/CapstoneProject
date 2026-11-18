"""Módulo autónomo de inferencia y scoring de decisión para el Actor de Apify.

Este módulo es 100% independiente de producto2 y encapsula la carga de artefactos,
el cálculo del score de decisión corporativa (0-100) y la clasificación de recomendaciones.
"""

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal
import joblib
import numpy as np
import pandas as pd

ProfileType = Literal["FAMILIA", "SOLTERO_EJECUTIVO"]


@lru_cache(maxsize=2)
def load_artifacts(artifacts_dir: Path | str) -> dict[str, Any]:
    """Carga los artefactos serializados .joblib entrenados (K-Means, XGBoost y metadatos)."""
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
    """Calcula Score de Decisión Corporativa (0 a 100)."""
    profile_norm = str(profile).strip().upper()
    if profile_norm not in {"FAMILIA", "SOLTERO_EJECUTIVO"}:
        raise ValueError(f"Perfil no soportado: {profile}. Use 'FAMILIA' o 'SOLTERO_EJECUTIVO'.")

    # 1. Componente económico: ahorro vs precio justo (0..40 pts)
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
        espacio_fit = float(np.clip((ambientes - 1.0) / 3.0, 0.0, 1.0))
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
    """Clasifica la recomendación en 4 categorías canónicas."""
    if decision_score >= 75.0 and pct_sobreprecio <= 5.0:
        return "ALTAMENTE RECOMENDADA"
    if decision_score >= 55.0 and pct_sobreprecio <= 15.0:
        return "RECOMENDADA"
    if pct_sobreprecio > 20.0:
        return "DESCARTAR / SOBREPRECIO ALTO"
    return "EVALUAR / ALTERNATIVA"
