"""Tests unitarios deterministas para el Actor de Entrenamiento Anual y Google Drive Exporter."""

import json
from pathlib import Path
from unittest.mock import MagicMock
import numpy as np
import pandas as pd
import pytest

from actors.trainer.src.train_pipeline import (
    CLUSTER_FEATURES,
    REGRESSION_FEATURES,
    InsufficientDataError,
    MetricRegressionError,
    run_training_pipeline,
    train_kmeans,
    train_xgboost,
)
from actors.trainer.src.gdrive_exporter import (
    export_version_to_gdrive,
    get_manifest_from_drive,
    get_next_manifest_version,
    save_manifest_to_drive,
)


@pytest.fixture
def synthetic_training_df():
    """Genera un dataset sintético determinista con 600 registros para pruebas del trainer."""
    np.random.seed(42)
    n = 600

    m2 = np.random.uniform(30, 150, n)
    ruido = np.random.uniform(55, 80, n)
    delitos = np.random.uniform(100, 2000, n)
    escuela = np.random.uniform(50, 800, n)
    subte = np.random.choice([0, 1, 2, 3], n)
    amenities = np.random.choice([0, 1, 2, 3, 4], n)
    banos = np.random.choice([1, 2, 3], n)
    ambientes = np.random.choice([1, 2, 3, 4], n)
    cocheras = np.random.choice([0, 1], n)

    # Costo sintético fuertemente correlacionado con m2 y ambientes para garantizar R2 alto
    costo = 200000 + (m2 * 6000) + (ambientes * 50000) + (subte * 25000) + np.random.normal(0, 15000, n)

    df = pd.DataFrame({
        "m2_totales": m2,
        "ruido_db_promedio": ruido,
        "densidad_delitos_500m": delitos,
        "distancia_escuela_m": escuela,
        "lineas_subte_600m": subte,
        "score_amenities": amenities,
        "banos": banos,
        "ambientes": ambientes,
        "cocheras": cocheras,
        "costo_total_ars": costo,
    })
    return df


def test_insufficient_data_error_raised():
    """Verifica que si len(df) < min_samples se lance InsufficientDataError (ERR_INSUFFICIENT_DATA)."""
    small_df = pd.DataFrame({"col": [1, 2, 3]})
    with pytest.raises(InsufficientDataError, match="ERR_INSUFFICIENT_DATA"):
        run_training_pipeline(small_df, output_dir=Path("/tmp/dummy"), min_samples=500)


def test_train_pipeline_execution_and_artifacts(synthetic_training_df, tmp_path: Path):
    """Verifica la ejecución exitosa del pipeline completo y la generación de binarios .joblib."""
    artifacts_dir = tmp_path / "artifacts"
    results = run_training_pipeline(
        df=synthetic_training_df,
        output_dir=artifacts_dir,
        min_samples=500,
        min_r2=0.80,
    )

    assert results["status"] == "success"
    assert results["sample_count"] == 600
    assert results["metrics"]["r2"] >= 0.80
    assert (artifacts_dir / "kmeans_model.joblib").exists()
    assert (artifacts_dir / "xgb_price_model.joblib").exists()
    assert (artifacts_dir / "model_metadata.joblib").exists()


def test_metric_regression_error_raised(synthetic_training_df, tmp_path: Path):
    """Verifica que si el umbral exigido es inalcanzable (p. ej. R2 >= 0.999), aborte con MetricRegressionError."""
    artifacts_dir = tmp_path / "artifacts_bad"
    with pytest.raises(MetricRegressionError, match="ERR_METRIC_REGRESSION"):
        run_training_pipeline(
            df=synthetic_training_df,
            output_dir=artifacts_dir,
            min_samples=500,
            min_r2=0.9999,
        )


def test_gdrive_manifest_version_calculation():
    """Verifica el cálculo correcto de la siguiente versión del manifiesto de Drive."""
    empty_manifest = {"versions": {}}
    assert get_next_manifest_version(empty_manifest) == "v1"

    manifest_v1 = {"versions": {"v1": {"status": "production"}}}
    assert get_next_manifest_version(manifest_v1) == "v2"

    manifest_v5 = {"versions": {"v1": {}, "v2": {}, "v5": {}}}
    assert get_next_manifest_version(manifest_v5) == "v6"


def test_export_version_dry_run(tmp_path: Path):
    """Verifica que export_version_to_gdrive en dry_run retorne estructura esperada sin llamadas externas."""
    artifacts_dir = tmp_path / "test_artifacts"
    artifacts_dir.mkdir()
    (artifacts_dir / "dummy.joblib").write_bytes(b"data")

    res = export_version_to_gdrive(
        credentials_info=None,
        registry_folder_id="dummy_folder",
        artifacts_dir=artifacts_dir,
        metrics={"r2": 0.85},
        dry_run=True,
    )

    assert res["status"] == "dry_run"
    assert res["version"] == "v1"
    assert "dummy.joblib" in res["uploaded_files"]


def test_load_dataset_from_csv_text_list_and_dedup():
    """Verifica que load_dataset_from_input concatene listas de CSVs desde n8n y deduplique por clave natural."""
    from actors.trainer.src.main import load_dataset_from_input

    csv_1 = (
        "calle_normalizada,m2_cubiertos,ambientes,costo_total_ars\n"
        "av santa fe 1200,45.0,2,450000\n"
        "av cabildo 2100,60.0,3,700000\n"
    )
    csv_2 = (
        "calle_normalizada,m2_cubiertos,ambientes,costo_total_ars\n"
        "av santa fe 1200,45.0,2,520000\n"
    )
    df = load_dataset_from_input({"trainingDataCsvText": [csv_1, csv_2]})
    assert len(df) == 2
    santa_fe = df[df["calle_normalizada"] == "av santa fe 1200"].iloc[0]
    assert santa_fe["costo_total_ars"] == 520000
