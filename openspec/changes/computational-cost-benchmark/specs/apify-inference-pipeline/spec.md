## ADDED Requirements

### Requirement: Evaluación Cuantitativa de Rendimiento y Costo Computacional (SLA)
El pipeline de curación geoespacial e inferencia del Actor de Apify SHALL satisfacer umbrales estrictos de latencia de ejecución, memoria RAM y consumo de Compute Units (CUs) para lotes de 1,000 y 10,000 registros, garantizando una asignación segura de contenedor hermético de 1,024 MB sin riesgo de degradación ni desborde de memoria (OOM).

#### Scenario: Evaluación de lote estándar de 1,000 registros
- **WHEN** se ejecuta el pipeline completo de curación e inferencia sobre un lote representativo de 1,000 publicaciones
- **THEN** el tiempo neto de ejecución SHALL ser estrictamente inferior a 5.0 segundos, el uso de memoria residente pico SHALL mantenerse por debajo de 1,024 MB, y el consumo estimado de Compute Units SHALL ser inferior a 0.002 CU ($0.0004 USD a la tarifa base de $0.20/CU).

#### Scenario: Evaluación de lote extendido mensual de 10,000 registros
- **WHEN** se ejecuta el pipeline completo de curación e inferencia sobre un lote representativo mensual de 10,000 publicaciones
- **THEN** el tiempo neto de ejecución SHALL ser estrictamente inferior a 10.0 segundos, el uso de memoria residente pico SHALL mantenerse por debajo de 1,024 MB, y el consumo estimado de Compute Units SHALL ser inferior a 0.005 CU ($0.0010 USD a la tarifa base de $0.20/CU).

#### Scenario: Detección de degradación de rendimiento y fallo de SLA
- **WHEN** una corrida de benchmark supera los límites máximos estipulados de tiempo (> 5.0s para 1k o > 10.0s para 10k) o excede 1,024 MB de memoria RAM
- **THEN** el arnés de prueba automatizado SHALL fallar deterministamente con Exit Code 1 emitiendo el token canónico `ERR_INFERENCE_SLA_EXCEEDED`.

## Test Plan & Resilience Strategy
- **Suite Determinista:** Creación de `tests/test_inference_cost_benchmark.py` ejecutado vía `pytest` en suite aislada, verificando numéricamente los tiempos y consumos contra los umbrales de SLA.
- **Herramienta Reproducible de Auditoría:** `scripts/benchmark_inference_cost.py` ejecutable por CLI para inspección forense y cálculo de métricas financieras oficiales de Apify.
- **Cero Dependencias de Red:** Las pruebas y benchmarks operan 100% desconectados consumiendo los artefactos locales de `actors/inference/reference_geo/` y `actors/inference/artifacts/`.
