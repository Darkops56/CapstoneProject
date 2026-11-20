# Evidencia de Verificación: `docs-living-architecture-sync`

**Fecha de Ejecución**: 2026-11-20  
**Cambio OpenSpec**: `docs-living-architecture-sync`  
**Tier de Complejidad**: Tier M  
**Resultado Global**: 100% Aprobado (Zero Regression, Exit Code 0, 70 tests colectados: 68 passed, 2 skipped)

---

## 1. Resumen de Implementación

En cumplimiento estricto con las directivas constitucionales de Arquitectura Viva (*Living Architecture*) y Cero Intervención Manual:

1. **`README.md`**:
   - Reestructuración con índice temático navegable e interactivo.
   - Árbol topológico exacto reflejando la adopción canónica de `actors/` (contenedores Apify serverless) y `src/` (`src-layout`).
   - Diagrama de ciclos de vida actualizado (Mensual vs. Anual Serverless con publicación a KV Store de producción).
   - Delegación canónica de variables de entorno y secrets a `docs/README_DASHBOARD_CONFIG.md`, erradicando contradicciones con `gdrive_csv_url`.
   - Incorporación de la sección de `notebooks/` (`pipeline_observatorio_caba.ipynb` y `observatorio_caba_showcase.ipynb`).
2. **`docs/README_DEPLOYMENT_N8N.md`**:
   - Actualización de los comandos de despliegue a `cd actors/inference` y `cd actors/trainer`.
   - Documentación exhaustiva de los 31 nodos operativos del lienzo unificado (auditoría CKAN de 4 datasets de GCBA, retención dual, subida atómica y publicación en KV Store).
   - Inclusión de advertencia operativa de importación limpia para evitar duplicación de cron en n8n Cloud.
3. **`docs/architecture/00` a `04`**:
   - Actualización de todas las rutas de import y almacenamiento a `src/config/`, `src/etl/`, `src/eda/` y `src/mlops/`.
   - Reporte fiel del arnés de pruebas automatizadas (70 tests).
   - Clarificación en `03_MODELADO` del baseline $R^2 = 0.7775$ de `v1` frente a la guarda de calidad $R^2 \ge 0.80$ para reentrenamientos en el Model Registry (`src/mlops/registry.py`).
   - Reescribir la sección 4 de `04_SCORE_DECISION` reflejando el handoff real a Apify (`actors/inference`), Google Drive y Streamlit Cloud.
4. **`docs/business_questions.md` y `docs/feature_selection.md`**:
   - Enriquecimiento con formato Markdown completo en `business_questions.md`.
   - Eliminación de la duplicación de las preguntas Q1-Q5 en `feature_selection.md`, dejándolo enfocado exclusivamente en la matriz de features, scores combinados y VIF.
5. **`openspec/specs/apify-inference-pipeline/spec.md`**:
   - Sincronización de rutas a `actors/inference/` y alineación del arnés de pruebas.

---

## 2. Ejecución Determinista de la Suite de Pruebas

```
$ pytest
============================= test session starts ==============================
platform linux -- Python 3.14.4, pytest-9.2.0, pluggy-1.7.0
rootdir: /home/luka/Documents/CapstoneProject
configfile: pytest.ini
testpaths: dashboard/tests, tests
plugins: anyio-4.16.0, typeguard-4.4.4
collected 70 items

dashboard/tests/test_dashboard.py ...................                    [ 27%]
tests/test_apify_actor.py ........                                       [ 38%]
tests/test_end_to_end_notebook.py ............                           [ 55%]
tests/test_etl_and_eda.py .......ss                                      [ 68%]
tests/test_geo_cache.py .                                                [ 70%]
tests/test_inference_scoring.py ..                                       [ 72%]
tests/test_model_registry.py .......                                     [ 82%]
tests/test_n8n_workflows.py ....                                         [ 88%]
tests/test_showcase_notebook.py ..                                       [ 91%]
tests/test_trainer_actor.py ......                                       [100%]

================== 68 passed, 2 skipped, 11 warnings in 4.78s ==================
```

---

## 3. Verificación Estática de Enlaces de Documentación

Auditoría exhaustiva mediante script Python de resolución de rutas relativas:
```
Total checked docs: 17
Broken links found: 0
```

---

## 4. Validación Estricta de OpenSpec

```bash
$ openspec validate docs-living-architecture-sync --strict
Change 'docs-living-architecture-sync' is valid

$ openspec validate --specs
- Validating...
✓ spec/annual-pipeline-mlops
✓ spec/apify-inference-pipeline
✓ spec/crime-heatmap-and-showcase
✓ spec/end-to-end-notebook
✓ spec/mlops-annual-training
✓ spec/monorepo-structure
✓ spec/monorepo-workspace
Totals: 7 passed, 0 failed (7 items)
```
