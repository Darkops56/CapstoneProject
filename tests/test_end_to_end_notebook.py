"""Suite determinista (Negative-Path First) para el Notebook Maestro End-to-End y limpieza del repo."""

from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

import scripts.notebook_helpers as nh

REPO_ROOT = Path(__file__).resolve().parent.parent
NOTEBOOK_PATH = REPO_ROOT / "notebooks" / "pipeline_observatorio_caba.ipynb"


def _synthetic_curated_df(n: int = 120, noisy_target: bool = False) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    m2 = rng.uniform(25, 160, size=n)
    amenities = rng.uniform(0, 10, size=n)
    banos = rng.integers(1, 4, size=n)
    ambientes = np.clip((m2 / 25).round().astype(int), 1, 5)
    cocheras = rng.integers(0, 2, size=n)
    ruido = rng.uniform(55, 78, size=n)
    delitos = rng.uniform(200, 1800, size=n)
    escuela = rng.uniform(50, 500, size=n)
    subte = rng.integers(0, 4, size=n)
    mascotas = rng.integers(0, 2, size=n)
    barrios = rng.choice(["Palermo", "Recoleta", "Belgrano", "Caballito", "Almagro"], size=n)

    if noisy_target:
        costo = rng.uniform(500_000, 2_500_000, size=n)
    else:
        costo = (
            300_000
            + m2 * 14_000
            + amenities * 45_000
            + banos * 120_000
            + cocheras * 90_000
            + subte * 25_000
            - delitos * 40
            + rng.normal(0, 60_000, size=n)
        )
        costo = np.clip(costo, 250_000, None)

    return pd.DataFrame(
        {
            "apto_mascotas": mascotas,
            "score_amenities": amenities,
            "m2_totales": m2,
            "ruido_db_promedio": ruido,
            "densidad_delitos_500m": delitos,
            "distancia_escuela_m": escuela,
            "lineas_subte_600m": subte,
            "banos": banos,
            "ambientes": ambientes,
            "cocheras": cocheras,
            "barrio": barrios,
            "costo_total_ars": costo,
        }
    )


# ---------------------------------------------------------------------------
# 1. Creación dinámica de directorios
# ---------------------------------------------------------------------------


def test_ensure_runtime_dirs_creates_all_expected_folders(tmp_path: Path):
    created = nh.ensure_runtime_dirs(tmp_path)
    expected_rel = [
        "Datasets/Originales",
        "Datasets/Curados",
        "etl/output",
        "mlops/artifacts",
        "mlops/figures",
    ]
    for rel in expected_rel:
        assert (tmp_path / rel).is_dir(), f"No se creó el directorio {rel}"
    assert set(created.keys()) >= {
        "datasets_originales",
        "datasets_curados",
        "etl_output",
        "mlops_artifacts",
        "mlops_figures",
    }


# ---------------------------------------------------------------------------
# 2. Ingesta CKAN GCBA (Negative-Path First + Happy Path)
# ---------------------------------------------------------------------------


def test_gcba_download_fails_with_canonical_token_on_http_503(tmp_path: Path):
    mock_resp = MagicMock()
    mock_resp.status_code = 503
    mock_resp.raise_for_status.side_effect = RuntimeError("503 Service Unavailable")

    with patch("scripts.notebook_helpers.requests.get", return_value=mock_resp):
        with pytest.raises(nh.NotebookPipelineError) as exc_info:
            nh.download_gcba_datasets(
                dest_dir=tmp_path,
                catalog=[nh.CKAN_CATALOG[0]],
                skip_if_exists=False,
            )
    assert exc_info.value.razon == nh.ERR_GCBA_DOWNLOAD
    assert nh.ERR_GCBA_DOWNLOAD in str(exc_info.value)


def test_gcba_download_fails_with_schema_token_when_columns_invalid(tmp_path: Path):
    meta_resp = MagicMock()
    meta_resp.status_code = 200
    meta_resp.json.return_value = {
        "success": True,
        "result": {
            "resources": [
                {"name": "delitos_2022", "format": "CSV", "url": "https://gcba.test/delitos.csv"}
            ]
        },
    }
    file_resp = MagicMock()
    file_resp.status_code = 200
    file_resp.content = b"col_invalida_1,col_invalida_2\n1,2\n"

    with patch("scripts.notebook_helpers.requests.get", side_effect=[meta_resp, file_resp]):
        with pytest.raises(nh.NotebookPipelineError) as exc_info:
            nh.download_gcba_datasets(
                dest_dir=tmp_path,
                catalog=[nh.CKAN_CATALOG[0]],
                skip_if_exists=False,
            )
    assert exc_info.value.razon == nh.ERR_GCBA_SCHEMA
    assert list(tmp_path.glob("*")) == [], "Un archivo con esquema inválido no debe quedar persistido."


def test_gcba_download_succeeds_and_validates_csv(tmp_path: Path):
    meta_resp = MagicMock()
    meta_resp.status_code = 200
    meta_resp.json.return_value = {
        "success": True,
        "result": {
            "resources": [
                {"name": "bocas_pdf", "format": "PDF", "url": "https://gcba.test/bocas.pdf"},
                {"name": "bocas_de_subte", "format": "CSV", "url": "https://gcba.test/bocas.csv"},
            ]
        },
    }
    file_resp = MagicMock()
    file_resp.status_code = 200
    file_resp.content = b"long,lat,linea,estacion\n-58.42,-34.60,A,Lima\n"

    with patch("scripts.notebook_helpers.requests.get", side_effect=[meta_resp, file_resp]):
        report = nh.download_gcba_datasets(
            dest_dir=tmp_path,
            catalog=[nh.CKAN_CATALOG[1]],
            skip_if_exists=False,
        )
    assert report["bocas-subte"]["tipo"] == "OK"
    saved = Path(report["bocas-subte"]["path"])
    assert saved.exists() and saved.suffix == ".csv"


# ---------------------------------------------------------------------------
# 3. Ingesta Apify Scraper (Negative-Path First + last_run / run_new)
# ---------------------------------------------------------------------------


def test_apify_rejects_missing_token_without_http_calls(tmp_path: Path):
    with patch("scripts.notebook_helpers.requests.get") as mock_get, patch(
        "scripts.notebook_helpers.requests.post"
    ) as mock_post:
        with pytest.raises(nh.NotebookPipelineError) as exc_info:
            nh.fetch_zonaprop_apify(token="   ", output_path=tmp_path / "raw.json", mode="last_run")
    assert exc_info.value.razon == nh.ERR_MISSING_APIFY_TOKEN
    mock_get.assert_not_called()
    mock_post.assert_not_called()


def test_apify_rejects_invalid_mode(tmp_path: Path):
    with pytest.raises(nh.NotebookPipelineError) as exc_info:
        nh.fetch_zonaprop_apify(token="dummy_tok", output_path=tmp_path / "raw.json", mode="invalid_mode")
    assert exc_info.value.razon == nh.ERR_INVALID_APIFY_MODE


def test_apify_rejects_empty_dataset_with_canonical_token(tmp_path: Path):
    runs_resp = MagicMock(status_code=200)
    runs_resp.json.return_value = {
        "data": {"items": [{"status": "SUCCEEDED", "defaultDatasetId": "ds123"}]}
    }
    items_resp = MagicMock(status_code=200)
    items_resp.json.return_value = []

    with patch("scripts.notebook_helpers.requests.get", side_effect=[runs_resp, items_resp]):
        with pytest.raises(nh.NotebookPipelineError) as exc_info:
            nh.fetch_zonaprop_apify(token="dummy_tok", output_path=tmp_path / "raw.json", mode="last_run")
    assert exc_info.value.razon == nh.ERR_APIFY_SCRAPER_FAILED


def test_apify_last_run_and_run_new_persist_json(tmp_path: Path):
    sample_items = [{"id": "1", "price": "ARS 900.000", "title": "Depto 2 amb Palermo"}]

    # Modo last_run
    runs_resp = MagicMock(status_code=200)
    runs_resp.json.return_value = {
        "data": {"items": [{"status": "SUCCEEDED", "defaultDatasetId": "ds_last"}]}
    }
    items_resp = MagicMock(status_code=200)
    items_resp.json.return_value = sample_items

    out_last = tmp_path / "last.json"
    with patch("scripts.notebook_helpers.requests.get", side_effect=[runs_resp, items_resp]):
        res_last = nh.fetch_zonaprop_apify(token="dummy_tok", output_path=out_last, mode="last_run")
    assert res_last["tipo"] == "OK"
    assert res_last["count"] == 1
    assert json.loads(out_last.read_text(encoding="utf-8")) == sample_items

    # Modo run_new
    post_resp = MagicMock(status_code=201)
    post_resp.json.return_value = {
        "data": {"status": "SUCCEEDED", "defaultDatasetId": "ds_new"}
    }
    items_resp_2 = MagicMock(status_code=200)
    items_resp_2.json.return_value = sample_items

    out_new = tmp_path / "new.json"
    with patch("scripts.notebook_helpers.requests.post", return_value=post_resp), patch(
        "scripts.notebook_helpers.requests.get", return_value=items_resp_2
    ):
        res_new = nh.fetch_zonaprop_apify(
            token="dummy_tok", output_path=out_new, mode="run_new", max_items=50
        )
    assert res_new["tipo"] == "OK"
    assert res_new["count"] == 1
    assert out_new.exists()


# ---------------------------------------------------------------------------
# 4. Evaluación Baseline vs Modelos y Auditoría de Error por Subgrupo
# ---------------------------------------------------------------------------


def test_baseline_vs_models_returns_4_models_and_guards_regression():
    df = _synthetic_curated_df(n=140, noisy_target=False)
    feature_cols = [c for c in df.columns if c not in ("costo_total_ars", "barrio")]

    res = nh.evaluate_baseline_vs_models(df, feature_cols=feature_cols, min_r2_threshold=0.50)
    table = res["comparison_df"]
    assert list(table["model"]) == ["DummyRegressor", "Ridge", "RandomForestRegressor", "XGBoost"]
    for col in ["MAE_ars", "RMSE_ars", "MAPE_pct", "R2"]:
        assert np.isfinite(table[col]).all()
    xgb_r2 = float(table.loc[table["model"] == "XGBoost", "R2"].iloc[0])
    dummy_r2 = float(table.loc[table["model"] == "DummyRegressor", "R2"].iloc[0])
    assert xgb_r2 > dummy_r2

    # Negative path: target puramente aleatorio debe disparar ERR_METRIC_REGRESSION
    df_noise = _synthetic_curated_df(n=100, noisy_target=True)
    with pytest.raises(nh.NotebookPipelineError) as exc_info:
        nh.evaluate_baseline_vs_models(df_noise, feature_cols=feature_cols, min_r2_threshold=0.50)
    assert exc_info.value.razon == nh.ERR_METRIC_REGRESSION


def test_subgroup_error_audit_computes_barrio_and_price_quartiles():
    df = _synthetic_curated_df(n=80, noisy_target=False)
    df["precio_predicho_ars"] = df["costo_total_ars"] * 1.08
    audit = nh.compute_subgroup_error_audit(df)

    assert "by_barrio" in audit and "by_quartile" in audit
    assert len(audit["by_barrio"]) >= 3
    assert len(audit["by_quartile"]) == 4
    for col in ["count", "MAE_ars", "MAPE_pct"]:
        assert col in audit["by_barrio"].columns
        assert col in audit["by_quartile"].columns


# ---------------------------------------------------------------------------
# 5. Auditoría Estructural y de Comentarios del Notebook Maestro
# ---------------------------------------------------------------------------


def test_notebook_structure_syntax_comments_and_8_charts():
    assert NOTEBOOK_PATH.exists(), f"Falta el Notebook Maestro en {NOTEBOOK_PATH}"
    raw_text = NOTEBOOK_PATH.read_text(encoding="utf-8")
    assert "apify_api_" not in raw_text, "El notebook no debe contener tokens de Apify hardcodeados."

    nb = json.loads(raw_text)
    cells = nb.get("cells", [])
    md_cells = [c for c in cells if c.get("cell_type") == "markdown"]
    code_cells = [c for c in cells if c.get("cell_type") == "code"]

    assert len(md_cells) >= 7, f"Se esperaban >= 7 celdas Markdown (Pasos 0..6), hay {len(md_cells)}"
    assert len(code_cells) >= 7, f"Se esperaban >= 7 celdas de código, hay {len(code_cells)}"

    all_code_parts = []
    for idx, cell in enumerate(code_cells):
        src = "".join(cell.get("source", []))
        # Filtrar magics de IPython/Colab (% / !) antes de ast.parse
        clean_lines = [ln for ln in src.splitlines() if not ln.lstrip().startswith(("%", "!"))]
        clean_src = "\n".join(clean_lines)
        ast.parse(clean_src, filename=f"cell_{idx}")

        comment_lines = [ln for ln in src.splitlines() if ln.strip().startswith("#")]
        assert len(comment_lines) >= 2, (
            f"La celda de código #{idx} tiene solo {len(comment_lines)} comentarios inline (mínimo 2)."
        )
        all_code_parts.append(src)

    combined = "\n".join(all_code_parts).lower()
    # Verificar presencia explícita de los 8 bloques gráficos de Defensa Ejecutiva
    expected_chart_markers = [
        "01_distribucion_target",
        "02_mapa_scatter_caba",
        "03_kmeans_elbow_centroides",
        "04_baseline_vs_modelos",
        "05_learning_curve",
        "06_pred_vs_real_residuos",
        "07_error_por_subgrupo",
        "08_shap_beeswarm_waterfall",
    ]
    for marker in expected_chart_markers:
        assert marker in combined, f"Falta el gráfico de Defensa Ejecutiva '{marker}' en el notebook."


# ---------------------------------------------------------------------------
# 6. Higiene del Repositorio (Git & .gitignore)
# ---------------------------------------------------------------------------


def test_repo_hygiene_datasets_and_legacy_notebooks_removed():
    gitignore_text = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "Datasets/" in gitignore_text, ".gitignore debe ignorar Datasets/"
    assert "etl/output/" in gitignore_text, ".gitignore debe ignorar etl/output/"

    tracked = subprocess.check_output(
        [
            "git",
            "ls-files",
            "Datasets/",
            "etl/output/",
            "etl/etl_pipeline.ipynb",
            "eda/eda_phase2.ipynb",
            "mlops/inference.ipynb",
        ],
        cwd=REPO_ROOT,
        text=True,
    ).strip()
    assert tracked == "", f"Aún hay archivos legados o datasets trackeados en git:\n{tracked}"

    # Verificar que se preservan artefactos y geo-cache requeridos por producción/tests
    assert (REPO_ROOT / "src" / "mlops" / "artifacts").is_dir()
    assert (REPO_ROOT / "actors" / "inference" / "reference_geo").is_dir()
