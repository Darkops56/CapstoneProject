"""Suite TDD determinista para el Actor de Apify (Curación + Enriquecimiento Geo + Inferencia)."""

import json
from pathlib import Path
import pytest
import numpy as np
import pandas as pd

from actor.src import pipeline, main


@pytest.fixture
def sample_properties_raw() -> list[dict]:
    fixture_path = Path(__file__).parent / "fixtures" / "sample_zonaprop_raw.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_curation_and_spatial_output_columns(sample_properties_raw):
    """Verifica que curate_and_enrich genere exactamente las 10 features y columnas base."""
    df_curated = pipeline.curate_and_enrich(sample_properties_raw)
    assert isinstance(df_curated, pd.DataFrame)
    assert len(df_curated) > 0

    required_features = [
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
    for col in required_features:
        assert col in df_curated.columns, f"Falta columna requerida: {col}"
        assert not df_curated[col].isna().any(), f"Columna {col} contiene valores NaN"


def test_imputation_on_null_or_outside_coords(sample_properties_raw):
    """Verifica imputación defensiva ante coordenadas nulas o fuera de CABA."""
    df_curated = pipeline.curate_and_enrich(sample_properties_raw)
    # Los items con coordenadas fuera de CABA o nulas deben tener tag de auditoría
    assert "tag_auditoria" in df_curated.columns
    imputed_records = df_curated[df_curated["tag_auditoria"].str.contains("AUDIT_COORD_IMPUTED", na=False)]
    assert len(imputed_records) >= 1
    # Y aun así sus métricas espaciales no deben ser NaN
    assert not imputed_records["ruido_db_promedio"].isna().any()
    assert not imputed_records["densidad_delitos_500m"].isna().any()


def test_inference_and_scoring_bounds(sample_properties_raw):
    """Verifica predicciones de precio justo, cluster y scores acotados en [0, 100]."""
    df_curated = pipeline.curate_and_enrich(sample_properties_raw)
    df_scored = pipeline.predict_and_score(df_curated)

    assert "precio_justo_ars" in df_scored.columns
    assert (df_scored["precio_justo_ars"] > 0).all()

    assert "cluster_habitabilidad" in df_scored.columns
    assert df_scored["cluster_habitabilidad"].isin([0, 1, 2, 3, 4]).all()

    for score_col in ["score_familia", "score_soltero"]:
        assert score_col in df_scored.columns
        assert (df_scored[score_col] >= 0.0).all()
        assert (df_scored[score_col] <= 100.0).all()


def test_run_pipeline_end_to_end(sample_properties_raw):
    """Verifica la función run_pipeline con contrato dict de entrada y salida."""
    results = main.run_pipeline(sample_properties_raw)
    assert isinstance(results, list)
    assert len(results) == len(sample_properties_raw)
    first = results[0]
    assert "precio_justo_ars" in first
    assert "score_familia" in first
    assert "score_soltero" in first


def test_actor_hermetic_isolation():
    """Verifica que actor.src.pipeline no importe etl ni producto2 (aislamiento hermético)."""
    import subprocess
    import sys

    # Subproceso simulando el contenedor de Apify donde etl y producto2 no existen
    code = """
import sys
# Bloquear explícitamente etl y producto2
sys.modules['etl'] = None
sys.modules['etl.etl_pipeline'] = None
sys.modules['producto2'] = None
sys.modules['producto2.inference'] = None

# Intentar importar el pipeline del actor
import actor.src.pipeline as p
assert hasattr(p, 'curate_and_enrich')
assert hasattr(p, 'predict_and_score')
print("HERMETIC_SUCCESS")
"""
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert res.returncode == 0, f"Error de aislamiento hermético:\n{res.stderr}"
    assert "HERMETIC_SUCCESS" in res.stdout


def test_nlp_parser():
    """Verifica utilidades del módulo nlp_parser."""
    from actor.src import nlp_parser

    # Parse price
    ars = nlp_parser.parse_price_ars("1500", "USD", tipo_cambio=1000.0, factor_usd=1.0, sellos=0.0)
    assert ars == 1500000.0

    # Pet friendly
    item_pet = {"detailExtraTopLevel": {"pills": [{"id": "ADMITS_PETS"}]}}
    assert nlp_parser.extract_apto_mascotas(item_pet) == 1

    # Amenities
    item_am = {"featuresListCardSimplified": [{"featureId": "1000068", "featureLabel": "Gimnasio"}]}
    res = nlp_parser.extract_amenities(item_am)
    assert res["has_gimnasio"] == 1


def test_scoring():
    """Verifica utilidades del módulo scoring."""
    from actor.src import scoring

    # Recommendation
    rec = scoring._classify_recommendation(80.0, 2.0)
    assert rec == "ALTAMENTE RECOMENDADA"
    rec_disc = scoring._classify_recommendation(50.0, 25.0)
    assert rec_disc == "DESCARTAR / SOBREPRECIO ALTO"

    # Compute decision score
    score = scoring.compute_decision_score(
        features={"score_amenities": 8.0, "apto_mascotas": 1.0, "cocheras": 1.0, "ambientes": 3.0, "ruido_db_promedio": 60.0},
        cluster_profile_tag="Familiar Tranquilo",
        pct_ahorro=10.0,
        profile="FAMILIA",
    )
    assert 0.0 <= score <= 100.0

