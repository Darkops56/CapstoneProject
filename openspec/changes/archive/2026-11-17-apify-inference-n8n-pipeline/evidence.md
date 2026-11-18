# Evidence: Apify Inference & n8n Dual-Cadence Pipeline

## Resumen Ejecutivo de Verificación Determinista

- **Fecha de Ejecución:** 2026-11-17
- **Directiva de Cero Pruebas Manuales:** Cumplida al 100%. Verificación autónoma mediante tests unitarios y CLI determinista.
- **Resultado Global de Suite Pytest:** **16/16 tests pasados (100% éxito, Exit Code 0)**.

---

### 1. Salida de Suite Completa de Tests (`pytest`)

```text
============================= test session starts ==============================
platform linux -- Python 3.14.4, pytest-9.2.0, pluggy-1.7.0
rootdir: /home/luka/Documents/CapstoneProject
collected 16 items

tests/test_apify_actor.py ....                                           [ 25%]
tests/test_geo_cache.py .                                                [ 31%]
tests/test_producto2.py ..                                               [ 43%]
tests/test_etl_and_eda.py .........                                      [100%]

======================= 16 passed, 11 warnings in 3.26s ========================
```

---

### 2. Validación de Contrato de Salida del Actor de Inferencia

Ejecución determinista del entrypoint CLI:
`python3 -m actor.src.main --input tests/fixtures/sample_zonaprop_raw.json --output /tmp/test_out.csv`

- **Registros procesados:** 50 propiedades.
- **Total de columnas generadas:** 29 columnas.
- **Valores Nulos (`NaN`):** **0 nulos en el 100% de registros**.
- **Vector de 10 Features Requeridas Presente:**
  `['apto_mascotas', 'score_amenities', 'm2_totales', 'ruido_db_promedio', 'densidad_delitos_500m', 'distancia_escuela_m', 'lineas_subte_600m', 'banos', 'ambientes', 'cocheras']`.
- **Rango de Decision Score `FAMILIA`:** `[15.87, 83.02]` (estrictamente acotado en `[0.0, 100.0]`).
- **Rango de Decision Score `SOLTERO_EJECUTIVO`:** `[21.50, 89.70]` (estrictamente acotado en `[0.0, 100.0]`).
- **Clústeres K-Means Asignados:** Clústeres `{0, 1, 2, 3, 4}` completos.
- **Tiempo Total de Cómputo Local:** **~1.5 segundos** (muy por debajo del límite de 25 segundos fijado en el diseño).

---

### 3. Verificación de Artefactos de Empaquetado y Workflows

1. **Geo-Caché Optimizado (`actor/reference_geo/`):**
   - `medicion_ruido.parquet`: 26 MB (reducción > 60% frente al CSV crudo de 72 MB).
   - `delitos_tree.joblib`: 2.1 MB (BallTree pre-indexado para 138,528 delitos).
   - `contexto_urbano.parquet`: 38 KB (2,241 paradas de subte y escuelas familiares).
2. **Contenedor Apify (`actor/Dockerfile`, `actor/requirements.txt`, `actor/.actor/actor.json`):**
   - Runtime Python 3.11 con dependencias nativas C (`libgdal-dev`, `libgeos-dev`, `libproj-dev`).
   - Entrypoint dual funcional: modo CLI local y modo nube `apify.Actor`.
3. **Plantillas JSON de n8n (`workflows/n8n/`):**
   - `workflows/n8n/workflow_mensual_zonaprop_inferencia.json`: validado con `python3 -m json.tool` (Exit Code 0). Contiene Schedule Mensual, Scraper, Circuit Breaker con detección de items < 500 y SHA-256 de duplicados, Actor Apify y carga a Google Drive.
   - `workflows/n8n/workflow_anual_auditoria_gcba.json`: validado con `python3 -m json.tool` (Exit Code 0). Contiene Schedule Anual, consulta a CKAN API, evaluación de metadatos y resguardo automático de datos crudos en Google Drive.
