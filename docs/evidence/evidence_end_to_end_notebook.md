# Evidence Report · `end-to-end-notebook-and-repo-cleanup`

* **Cambio OpenSpec:** `end-to-end-notebook-and-repo-cleanup` (Tier M)
* **Fecha de verificación:** 2026-11-20
* **Resultado SVC:** **PASS (Exit Code `0`)** — `68 passed, 2 skipped, 0 failed` en repositorio limpio (sin `Datasets/` ni `etl/output/`).

## 1. Trazabilidad de Criterios Gherkin (`specs/end-to-end-notebook/spec.md`)

| Escenario Gherkin | Test / Comando Determinista | Resultado |
| :--- | :--- | :---: |
| Repositorio limpio en git (`Datasets/`, `etl/output/` y 3 notebooks legados fuera de git + `.gitignore`) | `tests/test_end_to_end_notebook.py::test_repo_hygiene_datasets_and_legacy_notebooks_removed` + `test -z "$(git ls-files Datasets/ etl/output/)"` | **PASSED** |
| Inicialización dinámica de carpetas en runtime | `tests/test_end_to_end_notebook.py::test_ensure_runtime_dirs_creates_all_expected_folders` | **PASSED** |
| Suite de pruebas en entorno sin datasets generados | `pytest -v` (`test_producto1_outputs_exist_and_meet_contract` y `test_datasets_curados_folder_has_5_valid_csvs` en `SKIPPED`, `test_build_geo_cache_creates_artifacts` en `PASSED`) | **PASSED** |
| Rechazo `ERR_MISSING_APIFY_TOKEN` con 0 requests HTTP | `tests/test_end_to_end_notebook.py::test_apify_rejects_missing_token_without_http_calls` | **PASSED** |
| Rechazo `ERR_INVALID_APIFY_MODE` | `tests/test_end_to_end_notebook.py::test_apify_rejects_invalid_mode` | **PASSED** |
| Fallo CKAN (`ERR_GCBA_DOWNLOAD`, `ERR_GCBA_SCHEMA`) y descarga válida | `tests/test_end_to_end_notebook.py::test_gcba_download_*` (3 tests) | **PASSED** |
| Descarga Apify (`last_run`, `run_new`) y rechazo dataset vacío (`ERR_APIFY_SCRAPER_FAILED`) | `tests/test_end_to_end_notebook.py::test_apify_*` (2 tests) | **PASSED** |
| Comparativa 4 modelos (`DummyRegressor`, `Ridge`, `RandomForestRegressor`, `XGBoost`) + `ERR_METRIC_REGRESSION` | `tests/test_end_to_end_notebook.py::test_baseline_vs_models_returns_4_models_and_guards_regression` | **PASSED** |
| Auditoría de error por barrio y cuartil de precio | `tests/test_end_to_end_notebook.py::test_subgroup_error_audit_computes_barrio_and_price_quartiles` | **PASSED** |
| Sintaxis AST, narrativa Markdown (>= 7 celdas), >= 2 comentarios inline por celda de código, 8 gráficos y 0 secretos | `tests/test_end_to_end_notebook.py::test_notebook_structure_syntax_comments_and_8_charts` | **PASSED** |

## 2. Resumen de Ejecución SVC

```text
$ pytest -v && test -z "$(git ls-files Datasets/ etl/output/)" && echo "SVC_EXIT_0_OK"
================== 68 passed, 2 skipped, 11 warnings in 5.81s ==================
SVC_EXIT_0_OK
```

## 3. Archivos Creados, Modificados y Eliminados

* **Creados:**
  * `pipeline_observatorio_caba.ipynb` (Notebook Maestro End-to-End comentado, 16 celdas, Pasos 0 a 6 y 8 gráficos de Defensa Ejecutiva).
  * `scripts/notebook_helpers.py` (descarga defensiva CKAN GCBA, cliente Apify Scraper `last_run`/`run_new`, comparativa sin leakage y auditoría de error por subgrupo).
  * `tests/test_end_to_end_notebook.py` (12 tests deterministas Negative-Path First).
  * `docs/evidence/evidence_end_to_end_notebook.md` (este reporte).
* **Modificados:**
  * `.gitignore` (`Datasets/` y `etl/output/` agregados).
  * `README.md` (actualizada estructura al Notebook Maestro).
  * `tests/test_etl_and_eda.py` y `tests/test_geo_cache.py` (compatibilidad con clone limpio sin `Datasets/`).
* **Eliminados de git y disco (~163.4 MB liberados):**
  * `Datasets/` (9 archivos), `etl/output/` (3 archivos), `etl/etl_pipeline.ipynb`, `eda/eda_phase2.ipynb`, `mlops/inference.ipynb`.
