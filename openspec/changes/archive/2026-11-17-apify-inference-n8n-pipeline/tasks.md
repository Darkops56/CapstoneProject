## 1. Fase 0 - Contratos y Stubs de Interfaces

- [x] 1.1 Crear estructura de directorios `actor/` (`actor/src/`, `actor/artifacts/`, `actor/reference_geo/`) y definir stubs con `NotImplementedError` en `actor/src/main.py`, `actor/src/pipeline.py` y `scripts/prepare_geo_cache.py`. Verificar presencia de archivos con `ls -la actor/src/ scripts/prepare_geo_cache.py`.
- [x] 1.2 Copiar los artefactos entrenados existentes (`kmeans_model.joblib`, `xgb_price_model.joblib`, `model_metadata.joblib`) desde `producto2/artifacts/` hacia `actor/artifacts/`. Verificar integridad con `python3 -c "import joblib; m=joblib.load('actor/artifacts/model_metadata.joblib'); print(m['regression_features'])"`.

## 2. Fase 1 - Harness Red (Test Suites Previos al Código)

- [x] 2.1 Crear fixture de prueba `tests/fixtures/sample_zonaprop_raw.json` con 50 publicaciones representativas de CABA. Verificar que el archivo JSON sea válido con `python3 -m json.tool tests/fixtures/sample_zonaprop_raw.json > /dev/null`.
- [x] 2.2 Escribir suite de pruebas deterministas en `tests/test_apify_actor.py` cubriendo: validación de schema de entrada, imputación ante coordenadas nulas (`AUDIT_COORD_IMPUTED`), vector exacto de 10 features y límites numéricos `[0, 100]` de scores. Ejecutar `pytest tests/test_apify_actor.py` y verificar que falle con `NotImplementedError` (Fase Red).
- [x] 2.3 Escribir suite de pruebas unitarias para el script de geo-caché en `tests/test_geo_cache.py` validando la compresión de ruido y el árbol de delitos. Ejecutar `pytest tests/test_geo_cache.py` y verificar fallo inicial en Red.

## 3. Fase 2 - Implementación del Núcleo (Core Green)

- [x] 3.1 Implementar `scripts/prepare_geo_cache.py` para comprimir `Datasets/Curados/medicion_ruido_curado.csv` a GeoParquet y pre-generar el BallTree de delitos en `actor/reference_geo/`. Ejecutar `python3 scripts/prepare_geo_cache.py` y verificar `pytest tests/test_geo_cache.py` en Exit Code 0.
- [x] 3.2 Implementar en `actor/src/pipeline.py` la curación tabular y NLP (reutilizando funciones probadas de `etl/etl_pipeline.py`) y el cruce geoespacial rápido contra `actor/reference_geo/`. Verificar con `pytest tests/test_apify_actor.py -k test_curation_and_spatial` en Exit Code 0.
- [x] 3.3 Implementar en `actor/src/pipeline.py` la etapa de inferencia y scoring de decisión conectando con `actor/artifacts/`. Verificar con `pytest tests/test_apify_actor.py -k test_inference_and_scoring` en Exit Code 0.

## 4. Fase 3 - Empaquetado y Consumo de Frontera (Actor & n8n)

- [x] 4.1 Implementar el entrypoint dual CLI / Apify SDK en `actor/src/main.py` soportando `--input` y `--output` en modo local y `apify.Actor` en modo nube. Verificar ejecución local con `python3 -m actor.src.main --input tests/fixtures/sample_zonaprop_raw.json --output /tmp/test_out.csv` con Exit Code 0.
- [x] 4.2 Crear `actor/Dockerfile`, `actor/requirements.txt` y `actor/.actor/actor.json` con especificación de runtime Python 3.11 y memoria de 512 MB. Validar sintaxis con `docker build --check actor/` o linters de Dockerfile.
- [x] 4.3 Exportar plantillas JSON de workflows de n8n en `workflows/n8n/`:
  - `workflows/n8n/workflow_mensual_zonaprop_inferencia.json`: cron mensual + Apify scraper + Circuit Breaker (evaluación de conteo y SHA-256) + Actor Inferencia + Google Drive upload.
  - `workflows/n8n/workflow_anual_auditoria_gcba.json`: cron anual + CKAN HTTP request + Google Drive download.
  Verificar validez JSON con `python3 -m json.tool workflows/n8n/workflow_mensual_zonaprop_inferencia.json > /dev/null`.

## 5. Fase 4 - Verificación Determinista Final (SVC & Evidence)

- [x] 5.1 Ejecutar regresión completa con la suite total de pruebas: `pytest tests/test_apify_actor.py tests/test_geo_cache.py tests/test_producto2.py tests/test_etl_and_eda.py`. Verificar Exit Code 0 en el 100% de tests.
- [x] 5.2 Generar reporte determinista `openspec/changes/apify-inference-n8n-pipeline/evidence.md` documentando la salida de los tests, el tiempo de ejecución (< 25s) y la ausencia de valores nulos en el dataset de salida.
