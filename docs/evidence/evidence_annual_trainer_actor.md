# Evidencia Determinista: Actor de Entrenamiento Anual en Apify y Model Registry en Google Drive

**Fecha de Ejecución**: 2026-11-19  
**Cambio OpenSpec**: `annual-mlops-trainer-actor`  
**Resultado Global**: 100% Aprobado (Exit Code 0, 42/42 tests pasados)

---

## 1. Resumen Ejecutivo de Implementación

En cumplimiento estricto con las especificaciones técnicas y directivas constitucionales:
1. **Model Registry MLOps (`mlops/registry.py`)**:
   - Soporte para autoincremento de versiones (`v1`, `v2`, `v3`...).
   - Persistencia atómica de `mlops/registry.json`.
   - Protección contra regresión de métricas: umbral mínimo $R^2 \ge 0.80$. Emite excepción canónica `ERR_METRIC_REGRESSION` ante degradación.
   - CLI flags en `mlops/train_models.py` (`--bump`, `--registry`, `--min-r2`).
2. **Actor de Entrenamiento Anual en Apify (`trainer/`)**:
   - `Dockerfile` aislado basado en `apify/actor-python:3.11` con XGBoost, Scikit-Learn y Apify SDK.
   - Definición de esquemas `.actor/actor.json` e `.actor/input_schema.json`.
   - Pipeline de entrenamiento `trainer/src/train_pipeline.py` con validación de volumen mínimo (`ERR_INSUFFICIENT_DATA`, $\ge 500$ registros), optimización de silueta K-Means, y regresión XGBoost.
   - Entrypoint dual CLI / Apify SDK en `trainer/src/main.py`.
3. **Google Drive Exporter (`03_model_registry`)**:
   - Módulo `trainer/src/gdrive_exporter.py` que crea subcarpetas versionadas `v(N)/` en Google Drive y sube los binarios `.joblib`.
   - Creación y actualización atómica del manifiesto de producción `models_manifest.json` en Google Drive.
4. **Política de Retención Trimestral en n8n**:
   - Modificación de `workflows/n8n/workflow_mensual_zonaprop_inferencia.json` incorporando nodos de Google Drive para listar archivos en `01_mensual_enriquecido`, ordenar por antigüedad y enviar excedentes a la papelera (manteniendo estrictamente los últimos 3 datasets).

---

## 2. Ejecución Determinista de la Suite de Pruebas

```
$ pytest -v
============================= test session starts ==============================
platform linux -- Python 3.14.4, pytest-9.2.0, pluggy-1.7.0 -- /usr/bin/python3
cachedir: .pytest_cache
rootdir: /home/luka/Documents/CapstoneProject
configfile: pytest.ini
testpaths: dashboard/tests, tests
plugins: anyio-4.16.0, typeguard-4.4.4
collected 42 items

dashboard/tests/test_dashboard.py::test_classify_price_status_boundaries PASSED [  2%]
dashboard/tests/test_dashboard.py::test_normalizer_missing_required_columns PASSED [  4%]
dashboard/tests/test_dashboard.py::test_normalizer_caba_bbox_drop PASSED [  7%]
dashboard/tests/test_dashboard.py::test_normalizer_drive_schema_aliases PASSED [  9%]
dashboard/tests/test_dashboard.py::test_normalizer_amenities_graceful_degradation PASSED [ 11%]
dashboard/tests/test_dashboard.py::test_data_loader_rejects_unconfigured_drive PASSED [ 14%]
dashboard/tests/test_dashboard.py::test_data_loader_drive_error_fails_fast_without_fallback PASSED [ 16%]
dashboard/tests/test_dashboard.py::test_data_loader_successful_gdrive_fetch PASSED [ 19%]
dashboard/tests/test_dashboard.py::test_map_view_deck_structure PASSED   [ 21%]
dashboard/tests/test_dashboard.py::test_map_view_formatted_tooltips PASSED [ 23%]
dashboard/tests/test_dashboard.py::test_ui_components_filter_logic PASSED [ 26%]
dashboard/tests/test_dashboard.py::test_filter_performance PASSED        [ 28%]
tests/test_apify_actor.py::test_curation_and_spatial_output_columns PASSED [ 30%]
tests/test_apify_actor.py::test_imputation_on_null_or_outside_coords PASSED [ 33%]
tests/test_apify_actor.py::test_inference_and_scoring_bounds PASSED      [ 35%]
tests/test_apify_actor.py::test_run_pipeline_end_to_end PASSED           [ 38%]
tests/test_apify_actor.py::test_actor_hermetic_isolation PASSED          [ 40%]
tests/test_nlp_parser.py::test_nlp_parser PASSED                        [ 42%]
tests/test_scoring.py::test_scoring PASSED                               [ 45%]
tests/test_etl_and_eda.py::test_normalize_caba_coord_shifted_decimal PASSED [ 47%]
tests/test_etl_and_eda.py::test_parse_price_ars_usd_and_ars PASSED       [ 50%]
tests/test_etl_and_eda.py::test_extract_expenses_ars_structured_and_regex PASSED [ 52%]
tests/test_etl_and_eda.py::test_extract_apto_mascotas_negation_overrides_tag PASSED [ 54%]
tests/test_etl_and_eda.py::test_extract_amenities_profiles PASSED        [ 57%]
tests/test_etl_and_eda.py::test_enrich_with_schools_reprojects_caba_local_crs PASSED [ 59%]
tests/test_etl_and_eda.py::test_enrich_with_noise_within_and_nearest_fallback PASSED [ 61%]
tests/test_etl_and_eda.py::test_producto1_outputs_exist_and_meet_contract PASSED [ 64%]
tests/test_etl_and_eda.py::test_datasets_curados_folder_has_5_valid_csvs PASSED [ 66%]
tests/test_geo_cache.py::test_build_geo_cache_creates_artifacts PASSED   [ 69%]
tests/test_model_registry.py::test_registry_initial_state PASSED         [ 71%]
tests/test_model_registry.py::test_extract_r2_metric_formats PASSED      [ 73%]
tests/test_model_registry.py::test_bump_version_success_and_increment PASSED [ 76%]
tests/test_model_registry.py::test_bump_version_metric_regression_guard PASSED [ 78%]
tests/test_n8n_workflows.py::test_monthly_workflow_semantic_invariants PASSED [ 80%]
tests/test_n8n_workflows.py::test_annual_workflow_semantic_invariants PASSED [ 83%]
tests/test_producto2.py::test_decision_score_bounds_and_monotonicity PASSED [ 85%]
tests/test_producto2.py::test_inference_end_to_end_from_joblib PASSED    [ 88%]
tests/test_trainer_actor.py::test_insufficient_data_error_raised PASSED  [ 90%]
tests/test_trainer_actor.py::test_train_pipeline_execution_and_artifacts PASSED [ 92%]
tests/test_trainer_actor.py::test_metric_regression_error_raised PASSED  [ 95%]
tests/test_trainer_actor.py::test_gdrive_manifest_version_calculation PASSED [ 97%]
tests/test_trainer_actor.py::test_export_version_dry_run PASSED          [100%]

======================= 42 passed, 11 warnings in 7.83s ========================
```

---

## 3. Validación de Sintaxis n8n

```bash
$ python3 -m json.tool "workflows/n8n/workflow_mensual_zonaprop_inferencia.json" > /dev/null
# Exit Code: 0 (JSON válido)
```

## 4. Estado de Cumplimiento de Criterios

- [x] Versionador incremental de modelos (`v1`, `v2`, `v3`...) con umbral $R^2 \ge 0.80$.
- [x] Estructura serverless para Apify Actor (`trainer/`) sin acoplar el actor liviano mensual (`actor/`).
- [x] Sincronización y exportación versionada a Google Drive (`03_model_registry/` y `models_manifest.json`).
- [x] Política de retención trimestral en n8n con protección `KEEP_COUNT = 3`.
- [x] Cobertura automatizada 100% pasando sin intervención humana.
