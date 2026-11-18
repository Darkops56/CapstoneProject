# Design: Apify Inference & n8n Dual-Cadence Pipeline

## Context
Ver `proposal.md` y `specs/apify-inference-pipeline/spec.md`. El sistema actual cuenta con funciones de curado en `etl/etl_pipeline.py` y de inferencia en `producto2/inference.py`, alimentadas por artefactos `.joblib` en `producto2/artifacts/`. La meta es migrar este flujo a la nube en una arquitectura serverless portable orquestada por n8n y ejecutada en Apify.

## Goals / Non-Goals

**Goals:**
- Construir un Actor en Apify autocontenido capaz de ejecutar limpieza tabular, NLP y enriquecimiento geoespacial con datos GCBA cacheados, junto con la inferencia de precios y scoring.
- Diseñar la topología de dos workflows desacoplados en n8n: mensual (scraping + circuit breaker + inferencia + Drive) y anual (auditoría CKAN GCBA + Drive).
- Mantener la transportabilidad total: el Actor debe poder ejecutarse idénticamente de forma local por CLI (`python -m src.main`) o en la nube de Apify.

**Non-Goals:**
- Creación de interfaz gráfica o mapas interactivos (diferido a una rama futura de frontend).
- Re-entrenamiento automático de modelos ML en cada ciclo.
- Creación de bases de datos relacionales o clústeres PostGIS.

## Decisions

### Decisión 1: Actor de Apify Unificado (Curación + Cruce Espacial + Inferencia)
- **Alternativa A:** Separar en 2 actores (Actor 1: Geo-Curación, Actor 2: Inferencia ML).
- **Alternativa B (Elegida):** 1 solo Actor unificado.
- **Justificación:** Elimina latencia y costo de I/O de red en Apify (no hay transferencia intermedia de datasets pesados con geometrías). El paquete completo de inferencia suma menos de 250 KB y comparte dependencias base (Python 3.11, pandas, numpy).

### Decisión 2: Pre-indexación y Geo-Caché Embebido en Imagen Docker
- **Alternativa A:** Descargar `medicion_de_ruido_diurno_2018.csv` (72 MB) y delitos en cada ejecución mensual.
- **Alternativa B (Elegida):** Script de preparación (`scripts/prepare_geo_cache.py`) que comprime el ruido en GeoParquet indexado y pre-construye el BallTree/KDTree para delitos, incluyéndolos en `/actor/reference_geo/` dentro del contenedor.
- **Justificación:** Reduce el arranque del Actor de > 45 segundos a < 2 segundos. La memoria RAM se mantiene en < 350 MB durante la inferencia de 1,000 propiedades.

### Decisión 3: Circuit Breaker y Detección de Idempotencia en n8n
- **Alternativa A:** Ejecutar siempre el Actor de Inferencia sin validar el resultado del scraper.
- **Alternativa B (Elegida):** Evaluar en n8n el conteo de items y el hash SHA-256 de IDs. Si el lote es < 500 items o idéntico al mes anterior, abortar con código discriminado.
- **Justificación:** Protege el consumo de Compute Units en Apify y evita sobreescribir datasets consistentes en Google Drive con datos corruptos o vacíos.

### Decisión 4: Formato de Artefactos de Modelo
- **Alternativa A:** Serialización `.pickle` estándar.
- **Alternativa B (Elegida):** Serialización `.joblib` (existente en `producto2/artifacts/`).
- **Justificación:** `joblib` está optimizado para modelos Scikit-Learn y XGBoost con matrices NumPy internas, logrando una carga en memoria 3x más rápida y ocupando menor espacio en disco.

## Protocolo Grill-Me Exhaustivo (14 Vectores de Falla Crítica)

| # | Vector de Falla Crítica | Causa Raíz | Discriminador Causal 1:1 (`{tipo, razon}`) | Mitigación y Frontera |
|---|---|---|---|---|
| **F01** | Bloqueo o CAPTCHA en Zonaprop | Rate-limiting / Cloudflare en el portal origen | `{ tipo: ABORT, razon: ERR_SCRAPER_RATE_LIMITED }` | n8n detecta items < 500 y aborta sin llamar a Apify. |
| **F02** | Schema Drift en campos clave de Zonaprop | Modificación de nombres de propiedades JSON | `{ tipo: FALLBACK, razon: WARN_SCHEMA_KEY_DRIFT }` | Parser con `.get()` defensivo y defaults canónicos. |
| **F03** | Coordenadas nulas o corruptas (`0.0, 0.0`) | Anuncio sin georreferenciación precisa | `{ tipo: IMPUTATION, razon: AUDIT_COORD_IMPUTED }` | Imputación por centroide del barrio reportado. |
| **F04** | Propiedad ubicada fuera del CRS CABA | Publicación errónea en Gran Buenos Aires | `{ tipo: OUTLIER, razon: AUDIT_COORD_OUTSIDE_CABA }` | Marcado como inelegible sin crashear el cálculo espacial. |
| **F05** | Consumo excesivo de RAM (OOM) en Spatial Join | Lectura de CSVs crudos de 72 MB en memoria | `{ tipo: CRASH, razon: ERR_MEMORY_EXHAUSTED }` | Uso de GeoParquet particionado y KDTree pre-construido. |
| **F06** | Incompatibilidad de versiones joblib / scikit-learn | Dockerfile con versiones desalineadas | `{ tipo: ERROR, razon: ERR_UNPICKLE_VERSION_MISMATCH }` | `requirements.txt` con pinning estricto de versiones. |
| **F07** | Ausencia total de amenities en el texto | Publicación sin descripción textual | `{ tipo: DEFAULT, razon: AUDIT_AMENITIES_ZERO }` | `score_amenities = 0.0` y bandera de advertencia. |
| **F08** | Inconsistencia en etiquetas de mascotas | Publicación dice "no mascotas" pero tiene filtro positivo | `{ tipo: CONFLICT, razon: AUDIT_PETS_DISCREPANCY }` | Regla NLP estricta probada en `etl_pipeline.py`. |
| **F09** | Duplicación exacta de ejecuciones | Cron mensual dispara dos veces el mismo lote | `{ tipo: SKIP, razon: SKIP_IDENTICAL_DATASET }` | Hash SHA-256 evaluado en n8n detiene la duplicación. |
| **F10** | Falla de token / permisos en Google Drive | Expiración de credencial OAuth2 o Service Account | `{ tipo: RETRY, razon: ERR_GDRIVE_AUTH_FAILED }` | n8n ejecuta política de 3 reintentos con backoff exponencial. |
| **F11** | Error de cuota de storage en Google Drive | Carpeta destino llena o cuota superada | `{ tipo: ALERT, razon: ERR_GDRIVE_QUOTA_EXCEEDED }` | n8n captura error de cuota y notifica a canal de monitoreo. |
| **F12** | API de CKAN GCBA no responde o 500 | Portal de datos abiertos en mantenimiento | `{ tipo: RETRY_LATER, razon: WARN_CKAN_UNAVAILABLE }` | n8n pospone el chequeo anual 24 horas sin romper el cron. |
| **F13** | Features incompletas para XGBoost | Vector de entrada no tiene exactamente 10 columnas | `{ tipo: ERROR, razon: ERR_FEATURE_VECTOR_SHAPE }` | Validador de schema previo al `.predict()` arroja excepción controlada. |
| **F14** | Score de decisión fuera de límites `[0, 100]` | Valores atípicos extremos distorsionan el min-max | `{ tipo: CLAMP, razon: AUDIT_SCORE_CLAMPED }` | Aplicación de `np.clip(score, 0.0, 100.0)` determinista. |

## Matriz de Mapeo de Frontera (Principio de No-Colapso Semántico)

```
[Entrada Scraper] 
       │
       ├── Items < 500 ──────────────> { estado: "FAILED", codigo: "ERR_SCRAPER_INCOMPLETE_BATCH" }
       ├── Hash Duplicado ───────────> { estado: "SKIPPED", codigo: "SKIP_IDENTICAL_DATASET" }
       └── Lote Válido ──────────────> { estado: "PROCEED", codigo: "OK_PROCEED_TO_INFERENCE" }

[Actor Apify]
       │
       ├── Coordenadas ausentes ─────> { tag: "AUDIT_COORD_IMPUTED", metodo: "CENTROID_BARRIO" }
       ├── Feature fuera de rango ───> { tag: "AUDIT_SCORE_CLAMPED", limites: [0.0, 100.0] }
       └── Inferencia exitosa ───────> { tag: "INFERENCE_SUCCESS", registros: N }
```

## Análisis de Impacto en Recursos y Rendimiento
- **Memoria:** El uso máximo de RAM del contenedor se fija en 512 MB. Los índices espaciales se cargan como `mmap` o estructuras binarias optimizadas.
- **Latencia:** Procesamiento de 1,000 registros en < 25 segundos (Curación: ~10s, Spatial Join: ~10s, Inferencia XGBoost + KMeans: ~3s).
- **Concurrencia:** Ejecución secuencial batch única por mes (concurrencia = 1).
- **Observabilidad:** Emisión de logs estructurados JSON con métricas de auditoría en stdout para consumo en Apify Console y n8n Execution History.

## Migration Plan & Rollback
1. El código del Actor se ubica en el directorio `actor/` sin modificar la estructura existente de `etl/` ni `producto2/`.
2. Las pruebas locales deterministas validan que el resultado del Actor coincida exactamente con las salidas de referencia de `producto2/resultados_inferencia_caba.csv`.
3. Rollback inmediato: Al estar desacoplado, cualquier falla en la nube no afecta los scripts analíticos locales.
