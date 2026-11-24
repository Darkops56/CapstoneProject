## 1. Fase 0: Firmas y Stubs de Benchmark

- [x] 1.1 Definir la firma de `run_inference_benchmark(batch_sizes, memory_mb, apify_cu_rate)` en `scripts/benchmark_inference_cost.py` con stub inicial y verificar existencia del módulo con `python3 -c "import scripts.benchmark_inference_cost"`.

## 2. Fase 1: Harness de Pruebas Automatizadas (Red)

- [x] 2.1 Crear la suite determinista `tests/test_inference_cost_benchmark.py` con aserciones de SLA (< 5.0s para 1k reg, < 10.0s para 10k reg, < 1024 MB RAM) y verificar ejecución con fallo o stub vía `pytest tests/test_inference_cost_benchmark.py`.

## 3. Fase 2: Implementación del Core de Medición

- [x] 3.1 Implementar la lógica completa de medición empírica con `time.perf_counter()`, `tracemalloc` y cálculo de CUs de Apify en `scripts/benchmark_inference_cost.py` y verificar salida con `python3 scripts/benchmark_inference_cost.py --records 1000,10000`.

## 4. Fase 3: Documentación Técnica Canónica

- [x] 4.1 Incorporar la ficha del Punto 7 y la comparativa 1.000 vs. 10.000 registros con fórmulas en `docs/architecture/04_SCORE_DECISION_INFERENCIA_Y_HANDOFF.md` y verificar integridad con `grep -i "Costo Computacional de Inferencia" docs/architecture/04_SCORE_DECISION_INFERENCIA_Y_HANDOFF.md`.
- [x] 4.2 Agregar la tabla resumen de recursos y costos de Apify en `README.md` y verificar con `grep -i "Costo Computacional" README.md`.

## 5. Fase 4: Verificación Integral del Sistema (SVC Exit Code 0)

- [x] 5.1 Ejecutar la suite completa de pruebas de inferencia y regresión general asegurando Exit Code 0 sin pruebas manuales con `pytest tests/test_inference_cost_benchmark.py tests/test_apify_actor.py tests/test_inference_scoring.py`.
- [x] 5.2 Generar el reporte de verificación formal en `evidence.md` documentando las aserciones deterministas satisfechas.
