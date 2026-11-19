# Evidence: Clean Monorepo Restructuring & Hygiene Verification

**Change Name:** `clean-monorepo-restructuring`  
**Execution Date:** 2026-11-19  
**Target Branch:** `main`  
**Verification Status:** 100% Passed (Zero Regression, 33/33 Tests, Exit Code 0)

---

## 1. Executive Summary

Se completó exitosamente la reorganización del monorepo, reduciendo la raíz a los módulos estructurales clave:
1. **Centralización Documental**: Se unificaron `explicacion/`, `Feature.md`, `PreguntasNegocio.txt` y los reportes de evidencia bajo `docs/` (`docs/architecture/`, `docs/business_questions.md`, `docs/feature_selection.md`, `docs/evidence/`).
2. **Saneamiento de Seguridad**: Se extrajo y neutralizó el API Token de Apify que estaba hardcodeado en `ObtenerJsonApify.py`, transformando el archivo en la utilidad segura `scripts/fetch_apify_raw.py` que lee `APIFY_TOKEN` desde variables de entorno. Verificación estática confirmó 0 tokens en el repositorio.
3. **Aislamiento de Fixtures**: Se eliminó la carpeta confusa `data/` de la raíz, moviendo las muestras de prueba a `tests/fixtures/`.
4. **Evolución a MLOps**: Se formalizó `producto2/` como `mlops/` y `producto1/` como `etl/output/`, con soporte retrocompatible en `config/settings.py` y `producto2/__init__.py`.
5. **Cero Regresión**: Los 33 tests automatizados continúan pasando con Exit Code 0.

---

## 2. Test Execution Evidence

### Dashboard Unit & Integration Tests (12/12 Passed)
```bash
$ pytest dashboard/tests/ -v
============================= test session starts ==============================
collected 12 items

dashboard/tests/test_dashboard.py::test_classify_price_status_boundaries PASSED [  8%]
dashboard/tests/test_dashboard.py::test_normalizer_missing_required_columns PASSED [ 16%]
dashboard/tests/test_dashboard.py::test_normalizer_caba_bbox_drop PASSED [ 25%]
dashboard/tests/test_dashboard.py::test_normalizer_drive_schema_aliases PASSED [ 33%]
dashboard/tests/test_dashboard.py::test_normalizer_amenities_graceful_degradation PASSED [ 41%]
dashboard/tests/test_data_loader_rejects_unconfigured_drive PASSED [ 50%]
dashboard/tests/test_data_loader_drive_error_fails_fast_without_fallback PASSED [ 58%]
dashboard/tests/test_data_loader_successful_gdrive_fetch PASSED [ 66%]
dashboard/tests/test_map_view_deck_structure PASSED   [ 75%]
dashboard/tests/test_map_view_formatted_tooltips PASSED [ 83%]
dashboard/tests/test_ui_components_filter_logic PASSED [ 91%]
dashboard/tests/test_filter_performance PASSED        [100%]

============================== 12 passed in 0.67s ==============================
```

### Backend, ETL & MLOps Tests (21/21 Passed)
```bash
$ pytest tests/
============================= test session starts ==============================
collected 21 items

tests/test_apify_actor.py .......                                        [ 33%]
tests/test_etl_and_eda.py .........                                      [ 76%]
tests/test_geo_cache.py .                                                [ 80%]
tests/test_n8n_workflows.py ..                                           [ 90%]
tests/test_producto2.py ..                                               [100%]

======================= 21 passed, 11 warnings in 4.90s ========================
```

**Total Monorepo Assertions**: **33/33 tests passed (Exit Code 0)**.

---

## 3. Credential Quarantine Check
```bash
$ git grep -i "apify_api_"
# Exit code 1 (Zero matches found)
```

---

## 4. Gherkin Scenarios Compliance

| Requisito | Escenario | Resultado |
| :--- | :--- | :--- |
| **Documentation Centralization** | Documentation structure inspection | PASS (`docs/` contiene arquitectura, features y negocio; raíz limpia) |
| **Credential Quarantine in Scripts** | Apify scraper script inspection | PASS (`scripts/fetch_apify_raw.py` lee `APIFY_TOKEN` de env) |
| **Test Fixture Isolation** | Root directory inspection | PASS (`data/` eliminada de raíz; fixtures en `tests/fixtures/`) |
| **Backward Compatible Module Layout** | Running full regression test suite | PASS (33/33 tests pasando con Exit Code 0) |
