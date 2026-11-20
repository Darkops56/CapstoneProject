"""Tests TDD para Scoring de Inferencia: Score de Decisión, artefactos .joblib e inferencia."""

import numpy as np
import pandas as pd
import pytest

from config import settings as config
from mlops import inference


def test_decision_score_bounds_and_monotonicity():
    """El Score de Decisión debe mantenerse en [0, 100] y premiar mayor ahorro."""
    feat = {
        "apto_mascotas": 1,
        "score_amenities": 7.5,
        "m2_totales": 85.0,
        "ruido_db_promedio": 62.5,
        "densidad_delitos_500m": 400.0,
        "distancia_escuela_m": 120.0,
        "lineas_subte_600m": 2.0,
        "banos": 2.0,
        "ambientes": 3.0,
        "cocheras": 1.0,
    }
    s_ahorro = inference.compute_decision_score(feat, "Zona Familiar Tranquila", pct_ahorro=18.0, profile="FAMILIA")
    s_sobreprecio = inference.compute_decision_score(feat, "Zona Familiar Tranquila", pct_ahorro=-18.0, profile="FAMILIA")
    assert 0.0 <= s_sobreprecio < s_ahorro <= 100.0

    s_exec_hub = inference.compute_decision_score(feat, "Hub Ejecutivo Conectado", pct_ahorro=5.0, profile="SOLTERO_EJECUTIVO")
    s_exec_noisy = inference.compute_decision_score(feat, "Zona Ruidosa/Alta Densidad", pct_ahorro=5.0, profile="SOLTERO_EJECUTIVO")
    assert 0.0 <= s_exec_noisy < s_exec_hub <= 100.0


def test_inference_end_to_end_from_joblib():
    """Verifica carga de .joblib e inferencia individual y batch tras entrenamiento."""
    req_files = [
        config.PRODUCTO2_ARTIFACTS_DIR / "kmeans_model.joblib",
        config.PRODUCTO2_ARTIFACTS_DIR / "xgb_price_model.joblib",
        config.PRODUCTO2_ARTIFACTS_DIR / "model_metadata.joblib",
    ]
    if not all(p.exists() for p in req_files):
        pytest.skip("Artefactos de Producto 2 aún no entrenados.")

    sample = {
        "apto_mascotas": 1,
        "score_amenities": 6.0,
        "m2_totales": 70.0,
        "ruido_db_promedio": 62.5,
        "densidad_delitos_500m": 550.0,
        "distancia_escuela_m": 150.0,
        "lineas_subte_600m": 1.0,
        "banos": 1.0,
        "ambientes": 3.0,
        "cocheras": 1.0,
    }
    res_fam = inference.predict_property(sample, profile="FAMILIA", precio_publicado_ars=1_200_000.0)
    assert res_fam["precio_justo_ars"] > 0
    assert 0.0 <= res_fam["decision_score_0_100"] <= 100.0
    assert isinstance(res_fam["cluster_label"], str) and len(res_fam["cluster_label"]) > 0

    df_batch = pd.DataFrame([sample, {**sample, "m2_totales": 40.0, "ambientes": 2.0}])
    out_batch = inference.predict_batch(df_batch, profile="SOLTERO_EJECUTIVO", published_price_col=None)
    assert len(out_batch) == 2
    assert {"cluster_id", "cluster_label", "precio_justo_ars", "decision_score_0_100"}.issubset(out_batch.columns)
