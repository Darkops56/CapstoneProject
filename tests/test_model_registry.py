"""Tests unitarios deterministas para MLOps Model Registry y prevención de regresión de métricas."""

import json
from pathlib import Path
import pytest
from mlops.registry import (
    DEFAULT_MIN_R2,
    MetricRegressionError,
    bump_version,
    extract_r2_metric,
    get_next_version_str,
    load_registry,
    save_registry,
)


@pytest.fixture
def temp_registry_env(tmp_path: Path):
    """Crea un entorno aislado para pruebas de registry sin afectar archivos del repo."""
    reg_file = tmp_path / "registry.json"
    artifacts_src = tmp_path / "src_artifacts"
    artifacts_src.mkdir()
    target_artifacts = tmp_path / "target_artifacts"
    target_artifacts.mkdir()

    # Crear dummies de artefactos .joblib
    (artifacts_src / "kmeans_model.joblib").write_bytes(b"dummy_kmeans")
    (artifacts_src / "xgb_price_model.joblib").write_bytes(b"dummy_xgb")
    (artifacts_src / "model_metadata.joblib").write_bytes(b"dummy_metadata")

    return {
        "reg_file": reg_file,
        "artifacts_src": artifacts_src,
        "target_artifacts": target_artifacts,
    }


def test_registry_initial_state(temp_registry_env):
    """Verifica que un registry inexistente cargue valores por defecto válidos."""
    reg = load_registry(temp_registry_env["reg_file"])
    assert reg["production_version"] == "v1"
    assert reg["min_r2_threshold"] == DEFAULT_MIN_R2
    assert reg["versions"] == {}
    assert get_next_version_str(reg) == "v1"


def test_extract_r2_metric_formats():
    """Valida la extracción de R2 tanto en formato plano como anidado."""
    flat = {"r2": 0.85}
    assert extract_r2_metric(flat) == 0.85

    nested_holdout = {
        "xgboost_regression": {
            "holdout_test_20pct": {"r2": 0.835}
        }
    }
    assert extract_r2_metric(nested_holdout) == 0.835

    nested_cv = {
        "xgboost_regression": {
            "kfold_5_oof_full": {"r2": 0.812}
        }
    }
    assert extract_r2_metric(nested_cv) == 0.812

    with pytest.raises(ValueError, match="No se encontró la métrica 'r2'"):
        extract_r2_metric({"mae": 1000.0})


def test_bump_version_success_and_increment(temp_registry_env):
    """Verifica que bump_version cree v1 y luego v2 de forma incremental y archive la anterior."""
    reg_file = temp_registry_env["reg_file"]
    src_dir = temp_registry_env["artifacts_src"]
    target_dir = temp_registry_env["target_artifacts"]

    metrics_v1 = {"r2": 0.84, "rmse": 120000}
    res_v1 = bump_version(
        metrics=metrics_v1,
        artifacts_src_dir=src_dir,
        target_artifacts_base=target_dir,
        registry_path=reg_file,
    )

    assert res_v1["version"] == "v1"
    assert res_v1["status"] == "production"
    assert (target_dir / "v1" / "kmeans_model.joblib").exists()
    assert (target_dir / "v1" / "xgb_price_model.joblib").exists()
    assert (target_dir / "v1" / "model_metadata.joblib").exists()

    reg_disk_1 = load_registry(reg_file)
    assert reg_disk_1["production_version"] == "v1"
    assert reg_disk_1["versions"]["v1"]["status"] == "production"

    # Segunda versión: bump a v2
    metrics_v2 = {"r2": 0.86, "rmse": 115000}
    res_v2 = bump_version(
        metrics=metrics_v2,
        artifacts_src_dir=src_dir,
        target_artifacts_base=target_dir,
        registry_path=reg_file,
    )

    assert res_v2["version"] == "v2"
    assert res_v2["status"] == "production"
    assert (target_dir / "v2" / "kmeans_model.joblib").exists()

    reg_disk_2 = load_registry(reg_file)
    assert reg_disk_2["production_version"] == "v2"
    assert reg_disk_2["versions"]["v1"]["status"] == "archived"
    assert reg_disk_2["versions"]["v2"]["status"] == "production"


def test_bump_version_metric_regression_guard(temp_registry_env):
    """Verifica que si R2 < 0.80, se dispare MetricRegressionError (ERR_METRIC_REGRESSION) y no cambie producción."""
    reg_file = temp_registry_env["reg_file"]
    src_dir = temp_registry_env["artifacts_src"]
    target_dir = temp_registry_env["target_artifacts"]

    # Registrar v1 válida
    bump_version(
        metrics={"r2": 0.83},
        artifacts_src_dir=src_dir,
        target_artifacts_base=target_dir,
        registry_path=reg_file,
    )

    # Intento de registrar modelo degradado con R2 = 0.72
    bad_metrics = {"r2": 0.72, "rmse": 200000}
    with pytest.raises(MetricRegressionError, match="ERR_METRIC_REGRESSION"):
        bump_version(
            metrics=bad_metrics,
            artifacts_src_dir=src_dir,
            target_artifacts_base=target_dir,
            registry_path=reg_file,
        )

    # Validar que v2 NO fue creada y producción sigue siendo v1
    assert not (target_dir / "v2").exists()
    current_reg = load_registry(reg_file)
    assert current_reg["production_version"] == "v1"
    assert "v2" not in current_reg["versions"]
