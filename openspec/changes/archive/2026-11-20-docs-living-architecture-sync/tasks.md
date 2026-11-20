## 1. Verificación Inicial de Integridad y Enlaces (Fase 0 y 1: Harness & Red)

- [x] 1.1 Ejecutar suite pytest completa determinista para constatar el baseline verde de 70 tests y ausencia de regresiones (`pytest`).
- [x] 1.2 Ejecutar script de validación estática para auditar links rotos y nombres de archivos referenciados en `docs/` y `README.md` (`python3 -c "import os, re; ..."`).

## 2. Actualización de Documentación Operativa y Raíz (Fase 2: Core Documentation)

- [x] 2.1 Reestructurar `README.md` incorporando índice temático interactivo, árbol topológico `src/` + `actors/`, ciclo dual mensual/anual y enlace canónico a `docs/README_DASHBOARD_CONFIG.md`.
- [x] 2.2 Actualizar `docs/README_DEPLOYMENT_N8N.md` con las rutas `actors/inference` y `actors/trainer`, tabla completa de los 31 nodos de n8n y advertencia de importación limpia para evitar nodos duplicados.
- [x] 2.3 Formatear `docs/business_questions.md` con sintaxis Markdown completa y depurar `docs/feature_selection.md` eliminando la duplicación de Q1-Q5.

## 3. Actualización de Guías de Arquitectura (Fase 3: Architecture Sync)

- [x] 3.1 Actualizar `docs/architecture/00_INDICE_Y_ARQUITECTURA.md` reemplazando rutas legacy con `src/` y `actors/`, y reflejando el volumen real de 70 tests.
- [x] 3.2 Actualizar `docs/architecture/01_ETL_Y_CURACION_DE_DATOS.md` y `docs/architecture/02_EDA_ESTADISTICO_Y_SELECCION_FEATURES.md` con rutas `src/etl/` y `src/eda/`.
- [x] 3.3 Actualizar `docs/architecture/03_MODELADO_KMEANS_XGBOOST_Y_SHAP.md` documentando el baseline $R^2 = 0.7775$ de `v1` vs el umbral $R^2 \ge 0.80$ del Model Registry (`src/mlops/registry.py`).
- [x] 3.4 Actualizar `docs/architecture/04_SCORE_DECISION_INFERENCIA_Y_HANDOFF.md` reflejando el handoff productivo real hacia `actors/inference`, Google Drive y Streamlit Cloud.
- [x] 3.5 Sincronizar el spec `openspec/specs/apify-inference-pipeline/spec.md` con la ruta canónica `actors/inference/`.

## 4. Verificación de Contrato y Evidencia Final (Fase 4: SVC Exit Code 0)

- [x] 4.1 Validar que `openspec validate docs-living-architecture-sync --strict` pase con Exit Code 0.
- [x] 4.2 Ejecutar regresión completa con `pytest` y verificar 70 tests colectados (68 passed, 2 skipped, Exit Code 0).
- [x] 4.3 Generar reporte de evidencia determinista `docs/evidence/evidence_docs_living_architecture_sync.md`.
