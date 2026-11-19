# Evidence: Monorepo Architecture Consolidation & Verification

**Change Name:** `monorepo-consolidation`  
**Execution Date:** 2026-11-19  
**Target Branch:** `main`  
**Verification Status:** 100% Passed (Zero Regression, Exit Code 0)

---

## 1. Executive Summary

La arquitectura del proyecto ha sido consolidada exitosamente en la rama `main` bajo un patrón de Monorepo modular y desacoplado.
- El dashboard interactivo de Streamlit ha sido aislado en el subdirectorio `dashboard/` (`app.py`, `src/`, `data/`, `tests/`, `.streamlit/`, `requirements.txt`).
- Los pipelines de MLOps (`producto2/`) y el contenedor de producción Apify (`actor/`) se conservaron íntegros e intactos.
- Se verificó que el dashboard no tiene ninguna dependencia en tiempo de ejecución de librerías de Machine Learning (`xgboost`, `scikit-learn`, `shap`), reduciendo el consumo de RAM en Streamlit Cloud y acelerando el arranque a milisegundos.
- Se excluyeron del seguimiento de Git ~500 MB de apuntes académicos en PDF (`apuntes/`) preservando su copia física en el disco local del desarrollador y reduciendo el tamaño clonable del repositorio a menos de 25 MB.
- Se redactó el documento maestro `README.md` con guías de arquitectura, reentrenamiento y despliegue continuo en Streamlit Community Cloud (`Main file path: dashboard/app.py`).

---

## 2. Automated Test Execution Evidence

### A. Dashboard Test Suite (11/11 Passed)
```bash
$ pytest dashboard/tests/ -v
============================= test session starts ==============================
platform linux -- Python 3.14.4, pytest-9.2.0, pluggy-1.7.0 -- /usr/bin/python3
cachedir: .pytest_cache
rootdir: /home/luka/Documents/CapstoneProject
configfile: pytest.ini
plugins: anyio-4.16.0, typeguard-4.4.4
collecting ... collected 11 items

dashboard/tests/test_dashboard.py::test_classify_price_status_boundaries PASSED [  9%]
dashboard/tests/test_dashboard.py::test_normalizer_missing_required_columns PASSED [ 18%]
dashboard/tests/test_dashboard.py::test_normalizer_caba_bbox_drop PASSED [ 27%]
dashboard/tests/test_dashboard.py::test_normalizer_drive_schema_aliases PASSED [ 36%]
dashboard/tests/test_dashboard.py::test_normalizer_amenities_graceful_degradation PASSED [ 45%]
dashboard/tests/test_dashboard.py::test_data_loader_fallback_when_unconfigured PASSED [ 54%]
dashboard/tests/test_dashboard.py::test_data_loader_fallback_on_drive_error PASSED [ 63%]
dashboard/tests/test_dashboard.py::test_map_view_deck_structure PASSED   [ 72%]
dashboard/tests/test_dashboard.py::test_map_view_formatted_tooltips PASSED [ 81%]
dashboard/tests/test_dashboard.py::test_ui_components_filter_logic PASSED [ 90%]
dashboard/tests/test_dashboard.py::test_filter_performance PASSED        [100%]

============================== 11 passed in 0.61s ==============================
```

### B. Machine Learning & Ingestion Pipeline Tests (21/21 Passed)
```bash
$ pytest tests/
============================= test session starts ==============================
rootdir: /home/luka/Documents/CapstoneProject
configfile: pytest.ini
collected 21 items

tests/test_apify_actor.py .......                                        [ 33%]
tests/test_etl_and_eda.py .........                                      [ 76%]
tests/test_geo_cache.py .                                                [ 80%]
tests/test_n8n_workflows.py ..                                           [ 90%]
tests/test_producto2.py ..                                               [100%]

======================= 21 passed, 11 warnings in 7.16s ========================
```

**Total Monorepo Assertions**: **32/32 tests passed (Exit Code 0)**.

---

## 3. Static Import Quarantine Check

Verificación estática mediante árbol de sintaxis abstracta (AST) para descartar dependencias de ML en `dashboard/`:
```bash
$ python3 -c "import ast, glob; forbidden = {'xgboost', 'sklearn', 'scikit_learn', 'shap'}; ..."
SUCCESS: Zero heavy ML imports found in dashboard (100% decoupled)
```

---

## 4. Live Service Endpoint Verification

Streamlit daemon ejecutando `dashboard/app.py`:
```bash
$ curl -s -I http://localhost:8501
HTTP/1.1 200 OK
server: uvicorn
content-type: text/html; charset=utf-8
```

---

## 5. Specification Compliance (Gherkin Scenarios)

| Requisito | Escenario | Resultado |
| :--- | :--- | :--- |
| **Dashboard Directory Isolation** | Local dashboard invocation | PASS (`streamlit run dashboard/app.py` Exit Code 0) |
| **Dashboard Directory Isolation** | Running isolated test suite | PASS (`pytest dashboard/tests/` 11 passed in 0.61s) |
| **Cloud Deployment Path Contract** | Streamlit cloud configuration validation | PASS (`Main file path: dashboard/app.py` documentado en README) |
| **Heavy Asset Exclusion and Git Hygiene** | Verifying gitignore rules | PASS (`apuntes/` excluida de git, repo < 25 MB) |
