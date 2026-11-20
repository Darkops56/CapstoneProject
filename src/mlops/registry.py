"""Model Registry para versionado incremental y validación de métricas de modelos MLOps."""

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parent / "registry.json"
DEFAULT_ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"
DEFAULT_MIN_R2 = 0.80


class MetricRegressionError(ValueError):
    """Excepción canónica lanzada cuando un modelo no cumple los umbrales mínimos de métricas."""

    def __init__(self, message: str = "ERR_METRIC_REGRESSION"):
        super().__init__(message)


def load_registry(registry_path: Path | None = None) -> dict[str, Any]:
    """Carga el archivo registry.json. Si no existe, retorna una estructura inicial."""
    path = registry_path or DEFAULT_REGISTRY_PATH
    if not path.exists():
        return {
            "production_version": "v1",
            "min_r2_threshold": DEFAULT_MIN_R2,
            "versions": {},
        }
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_registry(registry_data: dict[str, Any], registry_path: Path | None = None) -> None:
    """Persiste atómicamente el registry.json."""
    path = registry_path or DEFAULT_REGISTRY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(registry_data, f, ensure_ascii=False, indent=2)
    os.replace(temp_path, path)


def get_next_version_str(registry_data: dict[str, Any]) -> str:
    """Calcula la siguiente versión incremental (v1, v2, v3...)."""
    versions = registry_data.get("versions", {})
    if not versions:
        return "v1"
    version_numbers = []
    for v in versions.keys():
        if v.startswith("v") and v[1:].isdigit():
            version_numbers.append(int(v[1:]))
    if not version_numbers:
        return "v1"
    return f"v{max(version_numbers) + 1}"


def extract_r2_metric(metrics: dict[str, Any]) -> float:
    """Extrae el R2 del diccionario de métricas soportando formato plano o anidado y mayúsculas/minúsculas."""
    for key in ("r2", "R2", "r2_score"):
        if key in metrics:
            return float(metrics[key])
    if "xgboost_regression" in metrics:
        xgb_m = metrics["xgboost_regression"]
        for split in ("holdout_test_20pct", "kfold_5_oof_full"):
            if split in xgb_m and isinstance(xgb_m[split], dict):
                for key in ("r2", "R2", "r2_score"):
                    if key in xgb_m[split]:
                        return float(xgb_m[split][key])
    raise ValueError("No se encontró la métrica 'r2' en el reporte proporcionado.")


def compute_dataset_hash(df: Any) -> str:
    """Calcula el hash SHA-256 determinista de un DataFrame para garantizar idempotencia."""
    cols = sorted(list(df.columns))
    csv_bytes = df[cols].to_csv(index=False).encode("utf-8")
    return hashlib.sha256(csv_bytes).hexdigest()


def deduplicate_annual_dataset(
    df: Any,
    key_cols: tuple[str, ...] = ("calle_normalizada", "m2_cubiertos", "ambientes"),
) -> Any:
    """Deduplica el acumulador anual por clave natural conservando la última observación."""
    available_keys = [c for c in key_cols if c in df.columns]
    if not available_keys:
        return df.drop_duplicates(keep="last").reset_index(drop=True)
    return df.drop_duplicates(subset=available_keys, keep="last").reset_index(drop=True)


def bump_version(
    metrics: dict[str, Any],
    artifacts_src_dir: Path | None = None,
    target_artifacts_base: Path | None = None,
    registry_path: Path | None = None,
    min_r2: float = DEFAULT_MIN_R2,
    dataset_hash: str | None = None,
) -> dict[str, Any]:
    """Valida umbrales, incrementa la versión y archiva artefactos en mlops/artifacts/v(N)/.

    Si `dataset_hash` coincide con el de la versión vigente en producción, omite el bump
    retornando status `SKIP_IDENTICAL_DATASET` para garantizar idempotencia.

    Raises:
        MetricRegressionError: Si el r2 obtenido es menor a min_r2.
    """
    r2_val = extract_r2_metric(metrics)
    if r2_val < min_r2:
        raise MetricRegressionError(
            f"ERR_METRIC_REGRESSION: R2 obtenido ({r2_val:.4f}) es inferior al umbral mínimo ({min_r2:.4f})"
        )

    reg = load_registry(registry_path)

    # Guarda de idempotencia por hash SHA-256 del dataset
    if dataset_hash:
        prod_v = reg.get("production_version")
        prod_record = reg.get("versions", {}).get(prod_v) if prod_v else None
        if isinstance(prod_record, dict) and prod_record.get("dataset_hash") == dataset_hash:
            return {
                "version": prod_v,
                "status": "SKIP_IDENTICAL_DATASET",
                "dataset_hash": dataset_hash,
                "metrics": prod_record.get("metrics", {}),
            }

    next_version = get_next_version_str(reg)

    base_artifacts = target_artifacts_base or DEFAULT_ARTIFACTS_DIR
    version_dir = base_artifacts / next_version
    version_dir.mkdir(parents=True, exist_ok=True)

    copied_files: list[str] = []
    src_dir = artifacts_src_dir or DEFAULT_ARTIFACTS_DIR
    if src_dir.exists():
        for item in src_dir.glob("*.joblib"):
            dest_file = version_dir / item.name
            shutil.copy2(item, dest_file)
            copied_files.append(item.name)

    version_record: dict[str, Any] = {
        "version": next_version,
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "metrics": {
            "r2": r2_val,
            "raw_metrics": metrics,
        },
        "artifacts_dir": str(version_dir),
        "artifacts": copied_files,
        "status": "production",
    }
    if dataset_hash:
        version_record["dataset_hash"] = dataset_hash

    # Marcar versiones anteriores como archived
    for v_key, v_info in reg.get("versions", {}).items():
        if isinstance(v_info, dict):
            v_info["status"] = "archived"

    reg["versions"][next_version] = version_record
    reg["production_version"] = next_version
    save_registry(reg, registry_path)

    return version_record
