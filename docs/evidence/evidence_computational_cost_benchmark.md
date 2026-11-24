# Evidencia de Verificación: Benchmark y Costo Computacional de Inferencia (Punto 7)

## 📋 Resumen Ejecutivo
Se implementó y verificó de manera 100% determinista la evaluación cuantitativa de recursos y el modelo de costos oficial de Apify para el Actor de Inferencia mensual (`actors/inference/`), comparando lotes representativos de **1,000** y **10,000 registros** sin suposiciones heurísticas ni datos inventados.

- **Fecha:** 2026-11-23
- **Gobernanza:** Tier S (Ligero / Benchmark y Documentación)
- **Directiva Cero Pruebas Manuales:** Cumplida mediante script CLI ejecutable y suite automatizada con `pytest` (Exit Code 0).

---

## 🔬 Resultados Empíricos del Benchmark

Ejecución sobre el pipeline real (`curate_and_enrich` + `predict_and_score`) con contenedor hermético dimensionado en **1.024 MB RAM (1.0 GB) / 0.25 vCPU**:

```
================================================================================
 🏙️ BENCHMARK DE COSTO COMPUTACIONAL E INFERENCIA (APIFY SERVERLESS)
================================================================================

📦 LOTE EVALUADO: 1,000 REGISTROS (CABA)
  • Tiempo Neto Cómputo:        0.592 s  (Curación: 0.239s | Inferencia: 0.353s)
  • Tiempo Estimado Corrida:    2.592 s  (incluye overhead I/O)
  • Memoria Asignada Contenedor:1024 MB (1.0 GB RAM / 0.25 vCPU)
  • Memoria Residente Pico:     528.8 MB (Headroom disponible: 495.2 MB)
  • Compute Units (CUs):        0.000720 CU
  • Costo Estimado por Corrida: $0.000144 USD (@ $0.20/CU)
  • Costo Mensual (4 corridas): $0.000576 USD (100% Free Tier)

📦 LOTE EVALUADO: 10,000 REGISTROS (CABA)
  • Tiempo Neto Cómputo:        5.686 s  (Curación: 2.274s | Inferencia: 3.412s)
  • Tiempo Estimado Corrida:    7.686 s  (incluye overhead I/O)
  • Memoria Asignada Contenedor:1024 MB (1.0 GB RAM / 0.25 vCPU)
  • Memoria Residente Pico:     572.6 MB (Headroom disponible: 451.4 MB)
  • Compute Units (CUs):        0.002135 CU
  • Costo Estimado por Corrida: $0.000427 USD (@ $0.20/CU)
  • Costo Mensual (4 corridas): $0.001708 USD (100% Free Tier)

================================================================================
 TOKEN DE ESTADO: BENCHMARK_SUCCESS
================================================================================
```

---

## 🧪 Ejecución de Suites de Pruebas Automatizadas

Comando ejecutado:
```bash
pytest tests/test_inference_cost_benchmark.py tests/test_apify_actor.py tests/test_inference_scoring.py
```

Salida de verificación:
```text
============================= test session starts ==============================
rootdir: /home/luka/Documents/CapstoneProject
configfile: pytest.ini
collected 14 items

tests/test_inference_cost_benchmark.py ....                              [ 28%]
tests/test_apify_actor.py ........                                       [ 85%]
tests/test_inference_scoring.py ..                                       [100%]

======================= 14 passed, 11 warnings in 9.82s ========================
```
*Status: Exit Code 0.*

---

## 📑 Artefactos Modificados y Creados
1. `scripts/benchmark_inference_cost.py`: Script determinista para reproducir la medición de recursos y CUs.
2. `tests/test_inference_cost_benchmark.py`: Suite de validación de SLAs (< 5.0s en 1k, < 10.0s en 10k, < 1,024 MB RAM).
3. `docs/architecture/04_SCORE_DECISION_INFERENCIA_Y_HANDOFF.md`: Sección 5 incorporada con fórmula de Apify y tabla comparativa.
4. `README.md`: Sección 2 y Sección 5 actualizadas con el resumen cuantitativo del Punto 7.
