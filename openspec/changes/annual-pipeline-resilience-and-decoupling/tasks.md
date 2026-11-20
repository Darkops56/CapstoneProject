# Tasks: Resiliencia del Pipeline Anual, Retención Dual y Desacoplamiento MLOps

## 1. Fase 0: Firmas y Contratos de Frontera

- [x] 1.1 Definir en `trainer/src/train_pipeline.py` y `mlops/registry.py` las firmas para cálculo de hash SHA-256 e idempotencia, verificando con `python3 -c "import trainer.src.train_pipeline; import mlops.registry"`.
- [x] 1.2 Definir en `trainer/src/gdrive_exporter.py` la firma del exportador atómico con staging temporal (`export_version_to_gdrive_atomic`), verificando imports sin errores de sintaxis.

## 2. Fase 1: Test Harness y Aserciones Semánticas (Verification-First)

- [x] 2.1 Crear en `tests/test_n8n_workflows.py` las pruebas semánticas para el workflow anual convergente (verificar nodo `Apify: Actor Trainer`, parámetro `waitForFinish=360`, token `WARN_GCBA_UNAVAILABLE` y `Continue on Fail`).
- [x] 2.2 Crear en `tests/test_model_registry.py` la prueba unitaria para idempotencia por hash SHA-256 (verificar que no se produzca bump si el dataset es idéntico).
- [x] 2.3 Ejecutar `pytest tests/test_n8n_workflows.py tests/test_model_registry.py` y comprobar que fallen inicialmente (Fase Red).

## 3. Fase 2: Implementación de Resiliencia MLOps y Registry

- [x] 3.1 Implementar en `mlops/registry.py` la validación de hash SHA-256 y deduplicación por clave natural `(calle_normalizada, m2_cubiertos, ambientes)` en acumuladores anuales.
- [x] 3.2 Implementar en `trainer/src/train_pipeline.py` el subsampling de fondo de SHAP ($N=100$) para garantizar ejecución rápida ($< 90$ segundos) y mitigar socket timeout en n8n.
- [x] 3.3 Implementar en `trainer/src/gdrive_exporter.py` la subida atómica a `staging_v(N+1)/` antes de actualizar `models_manifest.json`.

## 4. Fase 3: Conexión de Workflows en n8n y Configuración de Almacenamiento

- [x] 4.1 Actualizar `workflows/n8n/workflow_anual_auditoria_gcba.json` conectando el nodo HTTP al Actor Trainer en Apify, configurando `Continue on Fail` en la rama CKAN y convergencia incondicional.
- [x] 4.2 Actualizar `workflows/n8n/Pipeline Completo Anual y Mensual.json` reflejando el lienzo unificado con la retención dual (`01_mensual_enriquecido` vs. `04_historico_alquileres_anual`).
- [x] 4.3 Actualizar `docs/README_DEPLOYMENT_N8N.md` documentando la nueva topología, variables de Drive y tabla de resolución de fallas.

## 5. Fase 4: Verificación Integral del Sistema (SVC Exit Code 0)

- [x] 5.1 Ejecutar la suite completa de pruebas con `pytest` asegurando que los 33 tests existentes más los nuevos tests de resiliencia pasen con Exit Code 0.
- [x] 5.2 Validar la integridad del cambio ejecutando `openspec validate annual-pipeline-resilience-and-decoupling --strict`.
- [x] 5.3 Generar el reporte de evidencia determinista en `docs/evidence/evidence_annual_pipeline_resilience.md`.
