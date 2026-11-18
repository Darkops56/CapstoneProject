## 0. Fase 0: Firmas y Stubs Herméticos

- [x] 0.1 Crear stubs en `actor/src/nlp_parser.py` (`parse_price_ars`, `extract_expenses_ars`, `extract_apto_mascotas`, `_parse_main_features`, `extract_amenities`, `_extract_barrio_subzona`) con `NotImplementedError` y verificar con `python3 -c "import actor.src.nlp_parser"`
- [x] 0.2 Crear stubs en `actor/src/scoring.py` (`load_artifacts`, `compute_decision_score`, `_classify_recommendation`) con `NotImplementedError` y verificar con `python3 -c "import actor.src.scoring"`

## 1. Fase 1: Test Harness Hermético y Validación Semántica de Workflows (Red Phase)

- [x] 1.1 Escribir test hermético en `tests/test_apify_actor.py` que aísla `actor.src.pipeline` removiendo `etl` y `producto2` de `sys.modules`/`sys.path` para validar fallo inicial (Red Phase) mediante `python3 -m pytest tests/test_apify_actor.py -k test_actor_hermetic_isolation`
- [x] 1.2 Escribir script/test de aserción semántica para los workflows de n8n en `tests/test_n8n_workflows.py` verificando cron anual `0 4 1 3 *`, timeout scraper de 300s, `status === "SUCCEEDED"`, idempotencia `metadata_modified` y `binaryData: true` mediante `python3 -m pytest tests/test_n8n_workflows.py`

## 2. Fase 2: Implementación Core Desacoplada (Green Phase)

- [x] 2.1 Implementar lógica completa en `actor/src/nlp_parser.py` extrayendo las funciones de parsing regex de forma pura y verificar con `python3 -m pytest tests/test_apify_actor.py -k test_nlp_parser`
- [x] 2.2 Implementar lógica completa en `actor/src/scoring.py` extrayendo el cómputo de scores y carga de artefactos y verificar con `python3 -m pytest tests/test_apify_actor.py -k test_scoring`
- [x] 2.3 Refactorizar `actor/src/pipeline.py` para consumir exclusivamente `actor.src.nlp_parser` y `actor.src.scoring` sin referencias a `etl` o `producto2` y verificar el pase del test hermético con `python3 -m pytest tests/test_apify_actor.py -k test_actor_hermetic_isolation`
- [x] 2.4 Ajustar `actor/src/main.py` para que el modo Apify solo se dispare con `APIFY_IS_AT_HOME` o `--apify` explícito y verificar ejecución CLI local con `python3 -m actor.src.main --help`

## 3. Fase 3: Consumo en Frontera y Corrección Semántica de Workflows n8n

- [x] 3.1 Actualizar `workflows/n8n/workflow_mensual_zonaprop_inferencia.json` con cron `0 3 1 * *`, `waitForFinish=300`, validación defensiva `status === "SUCCEEDED"`, `&clean=true` y flag `binaryData: true` en Google Drive y verificar con `python3 -m pytest tests/test_n8n_workflows.py -k test_monthly_workflow`
- [x] 3.2 Actualizar `workflows/n8n/workflow_anual_auditoria_gcba.json` con cron `0 4 1 3 *`, compuerta `IF` de idempotencia `metadata_modified !== lastModified`, emisión de `SKIP_NO_ANNUAL_UPDATE` / `EVENT_GCBA_DATA_UPDATED` y `binaryData: true` en Google Drive y verificar con `python3 -m pytest tests/test_n8n_workflows.py -k test_annual_workflow`

## 4. Fase 4: Single Verification Command (SVC) y Regresión de Sistema

- [x] 4.1 Ejecutar suite completa de regresión determinista hermética con `PYTHONPATH="" python3 -m pytest tests/test_apify_actor.py tests/test_geo_cache.py tests/test_n8n_workflows.py tests/test_producto2.py tests/test_etl_and_eda.py` garantizando Exit Code 0
- [x] 4.2 Ejecutar prueba de extremo a extremo CLI del Actor procesando lote de muestra y verificar generación de CSV válido mediante `python3 -m actor.src.main --input data/sample_raw_listings.json --output data/curated_sample_output.csv --limit 50`
- [x] 4.3 Generar artefacto de auditoría y evidencia `evidence.md` documentando los resultados de la verificación determinista
