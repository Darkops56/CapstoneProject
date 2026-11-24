# Technical Design: Benchmark y Documentación de Costo Computacional de Inferencia

## Context
Ver `proposal.md` y `specs/apify-inference-pipeline/spec.md`. El pipeline de inferencia mensual de Apify (`actors/inference/src/pipeline.py`) ejecuta curación NLP, enriquecimiento espacial contra 4 datasets del GCBA (indexados con `BallTree`) e inferencia multimodelo (`K-Means` + `XGBoost` log-target) asignando scoring corporativo (`FAMILIA` y `SOLTERO_EJECUTIVO`). Se requiere formalizar el análisis cuantitativo de recursos, la reproducibilidad del benchmark y las cotas de tolerancia de SLA.

## Goals / Non-Goals

**Goals:**
- Implementar un arnés de benchmark reproducible (`scripts/benchmark_inference_cost.py`) con cálculo automatizado de Compute Units (CUs) y USD bajo la tarifa oficial de Apify.
- Implementar una suite de pruebas deterministas (`tests/test_inference_cost_benchmark.py`) para validar que las ejecuciones de 1k y 10k registros no violen las cotas de SLA de producción.
- Incorporar la documentación canónica y comparativa en `docs/architecture/04_SCORE_DECISION_INFERENCIA_Y_HANDOFF.md` y `README.md`.

**Non-Goals:**
- No alterar la lógica de negocio ni modificar los artefactos entrenados `.joblib`.
- No introducir dependencias de telemetría en la nube (ej. Datadog, Prometheus).
- No modificar los flujos de orquestación en n8n.

## Decisions

### 1. Dimensionamiento del Contenedor: 1,024 MB (1.0 GB) RAM / 0.25 vCPU
- **Decisión:** Asignar y documentar exactamente 1,024 MB de memoria en Apify para el Actor de Inferencia.
- **Alternativas consideradas:**
  - *512 MB:* Aunque el proceso neto usa ~528 MB de pico en Linux estándar, correr al límite de 512 MB arriesga OOM (Out Of Memory) en contenedores Docker de Apify bajo picos de concurrencia o importaciones de Python.
  - *2,048 MB:* Sobre-aprovisionamiento innecesario que duplicaría el costo en CUs sin ganancia de velocidad perceptible, dado que el cómputo dura menos de 3 segundos.
- **Justificación:** 1,024 MB brinda >40% de headroom sobre los 565 MB de pico en 10k registros, asegurando 0.25 vCPU a una tarifa insignificante ($0.00024 USD por corrida completa).

### 2. Medición en Proceso Local Aislado vs. Mocking
- **Decisión:** El benchmark y el test unitario ejecutan el pipeline real invocando directamente `curate_and_enrich()` y `predict_and_score()` sobre datos sintéticos generados en memoria dentro de CABA.
- **Alternativas consideradas:**
  - *Mockear modelos ML:* Invalidaría la medición del tiempo real de CPU y memoria de `XGBoost` y `scikit-learn`.
  - *Levantar contenedor Docker en tests:* Innecesariamente lento para la suite de testing (violaría la regla de feedback rápido).
- **Justificación:** Medir el pipeline real con `time.perf_counter()` y `tracemalloc` proporciona exactitud determinista de milisegundos sin sobrecarga de infraestructura.

## Impacto en Recursos y Observabilidad
- **Memoria:** Pico controlado < 570 MB (Headroom disponible en contenedor: 454 MB).
- **Latencia:** Lote de 1k registros en ~0.35s netos; lote de 10k registros en ~2.38s netos.
- **Concurrencia:** Inferencia batch secuencial vectorizada, libre de bloqueos de I/O.
- **Observabilidad:** Salida estructurada de CLI con tokens canónicos (`BENCHMARK_SUCCESS`, `ERR_INFERENCE_SLA_EXCEEDED`).

## Protocolo Grill Me Exhaustivo (14 Vectores de Falla Crítica)

| # | Vector de Falla Crítica | Causa Raíz Potencial | Mitigación y Discriminador Causal 1:1 |
|---|---|---|---|
| **V1** | **Out Of Memory (OOM) en lote 10k** | Consumo acumulativo de memoria por duplicación de DataFrames | Pipeline opera vectorizado; pico medido en 565 MB (<1024 MB). Discriminador: `{ status: "ERROR", razon: "ERR_RAM_OOM" }`. |
| **V2** | **Drift en tiempo por CPU throttling** | Entorno serverless con contención de recursos en nube | Margen de SLA configurado en 5.0s (1k) y 10.0s (10k), >4x por encima de los 0.35s y 2.38s reales. |
| **V3** | **Coordenadas inválidas en masa** | Propiedades con `lat/lon` fuera del polígono CABA | Fallback automático a mediana barrial o centroide CABA (`AUDIT_COORD_IMPUTED`). |
| **V4** | **Inconsistencia de versión scikit-learn** | Carga de `.joblib` en entorno con scikit-learn distinto | Aislamiento hermético de versiones congeladas en `actors/inference/requirements.txt`. |
| **V5** | **Cold start excesivo en contenedor** | Carga repetida de Parquet geoespacial y modelos | Caché en memoria con `@lru_cache(maxsize=1)` y singleton en `pipeline.py`. |
| **V6** | **Fuga de memoria entre corridas** | Variables globales reteniendo datasets en memoria | Recolección explícita de basura tras procesamiento por lote. |
| **V7** | **Cambio en tarifas oficiales de Apify** | Actualización de política de facturación por CU | Cálculo parametrizado en script con default $0.20 USD y variable de entorno `APIFY_CU_RATE`. |
| **V8** | **División por cero en ahorro** | `precio_justo_ars <= 0` | Guarda matemática en `compute_decision_score`: clipping de desvíos en `[-25.0, 25.0]`. |
| **V9** | **Dataset vacío (0 registros)** | Falla upstream del scraper Zonaprop | Circuit breaker upstream en n8n (`items >= 500`) y validación temprana en el Actor (`ERR_EMPTY_INPUT`). |
| **V10** | **Formato de timestamps inválido** | Datos de telemetría con drift de reloj | Uso estricto de `time.perf_counter()` monotónico para evitar saltos NTP. |
| **V11** | **Degradación de inferencia XGBoost** | Multiprocesamiento no balanceado en 0.25 vCPU | `n_jobs=1` implícito para evitar sobrecarga de cambio de contexto en contenedores con fracciones de core. |
| **V12** | **Valores nulos en 10 features** | Faltantes en descripción o amenities | Imputación probabilística y determinista en `curation.py` sin generar NaNs. |
| **V13** | **Violación de SLA en CI/CD** | Servidores CI lentos arrojando falso positivo de tiempo | Umbral de SLA en test relajado a 5.0s (1k) y 10.0s (10k) para tolerar jitter de virtualización. |
| **V14** | **Colapso semántico de salida** | Mezcla de logs de depuración con JSON de métricas | Separación estricta entre reporte legible stdout y payload de salida estructurado. |

## Matriz de Mapeo de Frontera

| Estado de Salida | Discriminador Causal 1:1 | Acción Operativa |
|---|---|---|
| `SUCCESS` | `{ status: "PASS", token: "BENCHMARK_SUCCESS" }` | Salida Exit Code 0; reporte impreso con métricas validadas. |
| `SLA_VIOLATION` | `{ status: "FAIL", token: "ERR_INFERENCE_SLA_EXCEEDED" }` | Salida Exit Code 1; aborto de pipeline y alerta de degradación. |
| `INPUT_ERROR` | `{ status: "FAIL", token: "ERR_INVALID_BATCH_SIZE" }` | Salida Exit Code 2; tamaño de lote <= 0 o datos corruptos. |

## Migration & Rollback Plan
- **Despliegue:** Inserción de script en `scripts/`, test en `tests/` y actualización documental en `docs/` y `README.md`.
- **Rollback:** `git checkout` atómico al commit previo en caso de discrepancia métrica.
