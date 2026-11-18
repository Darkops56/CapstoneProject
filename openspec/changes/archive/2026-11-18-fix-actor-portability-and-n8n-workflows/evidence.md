# Verification Evidence: Fix Actor Portability and n8n Workflows Semantic Invariants

## Resumen Ejecutivo de Verificación Determinista
- **Cambio:** `fix-actor-portability-and-n8n-workflows`
- **Fecha:** 2026-11-18
- **Resultado:** **EXIT CODE 0 (Determinista, Cero Pruebas Manuales)**
- **Radio de Explosión (Blast Radius):**
  - Módulos modificados/creados: `actor/src/nlp_parser.py`, `actor/src/scoring.py`, `actor/src/pipeline.py`, `actor/src/main.py`.
  - Workflows modificados: `workflows/n8n/workflow_mensual_zonaprop_inferencia.json`, `workflows/n8n/workflow_anual_auditoria_gcba.json`.
  - Harness de pruebas agregado: `tests/test_n8n_workflows.py`, `tests/test_apify_actor.py` (aislamiento hermético).

## Resultados de las Fases TDD y Regresión

### 1. Test de Aislamiento Hermético (Container Context Leak Resolved)
```bash
$ python3 -m pytest tests/test_apify_actor.py -k test_actor_hermetic_isolation
======================= 1 passed, 6 deselected in 2.17s ========================
```
*Garantía:* Se bloqueó la importación de `etl` y `producto2` en `sys.modules`, comprobando que `actor.src.pipeline` se ejecuta de forma completamente autocontenida sin requerir el monorepo.

### 2. Aserciones Semánticas en Workflows n8n
```bash
$ python3 -m pytest tests/test_n8n_workflows.py
============================== 2 passed in 0.01s ===============================
```
*Invariantes Validados:*
- `workflow_mensual_zonaprop_inferencia.json`:
  - Cron trigger: `0 3 1 * *`.
  - Scraper URL: `waitForFinish=300`.
  - Circuit Breaker: validación defensiva `runStatus === 'SUCCEEDED'`, `itemCount >= 500`, SHA-256 hash idempotence.
  - CSV Download: `format=csv&clean=true`.
  - Google Drive upload: `binaryData: true`, `binaryPropertyName: "data"`.
- `workflow_anual_auditoria_gcba.json`:
  - Cron trigger: `0 4 1 3 *` (1 de Marzo anual, no mensual).
  - Idempotencia: comparación con `$getWorkflowStaticData('global').lastModified`.
  - Compuerta IF: bifurcación condicional ante novedades en GCBA.
  - Emisión de tokens canónicos: `SKIP_NO_ANNUAL_UPDATE` y `EVENT_GCBA_DATA_UPDATED`.
  - Google Drive upload: `binaryData: true`, `binaryPropertyName: "data"`.

### 3. Suite Completa de Regresión (Single Verification Command)
```bash
$ PYTHONPATH="" python3 -m pytest tests/test_apify_actor.py tests/test_geo_cache.py tests/test_n8n_workflows.py tests/test_producto2.py tests/test_etl_and_eda.py
======================= 21 passed, 11 warnings in 4.21s ========================
```

### 4. Prueba de Extremo a Extremo CLI del Actor
```bash
$ python3 -m actor.src.main --input tests/fixtures/sample_zonaprop_raw.json --output data/curated_sample_output.csv --limit 50
[Actor] Iniciando pipeline para 50 propiedades...
[Actor] Curación y cruce geoespacial completados (50 registros)
[Actor] Inferencia y cálculo de scores finalizados exitosamente
Éxito: 50 registros guardados en 'data/curated_sample_output.csv'
```
*Salida generada:* 50 registros, 29 columnas completas (10 features geoespaciales requeridas, precios justos, ahorro, cluster habitacional y scores de decisión corporativa para Soltero Ejecutivo y Familia).
