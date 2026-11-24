# Proposal: Benchmark y Documentación de Costo Computacional de Inferencia

## Why
El proyecto carecía de una especificación cuantitativa y documental rigurosa sobre el costo computacional de inferencia del Actor de Apify (Punto 7 del estándar de arquitectura de pipelines ML). La medición empírica sobre el pipeline real (`actors/inference/src/pipeline.py`) reveló que procesar 1,000 registros toma 0.35s netos (~2.35s de corrida total en Apify) consumiendo 0.000653 CUs ($0.000131 USD), mientras que procesar 10,000 registros toma 2.38s netos (~4.38s de corrida total) consumiendo 0.001216 CUs ($0.000243 USD). Es imperativo formalizar esta cota de SLA, documentarla canónicamente y proveer un arnés de verificación determinista para prevenir regresiones de rendimiento y consumo de memoria.

## Governance & Complexity Tier
- **Tier de Complejidad:** **Tier S (Ligero)**.
- **Justificación YAGNI:** El cambio no introduce nuevas capas de abstracción, servicios en segundo plano ni dependencias externas. Se limita a formalizar contratos de SLA en las especificaciones existentes, documentar las cotas de cómputo y añadir un script ejecutable de benchmark junto a una prueba unitaria determinista.

## Repo Inspection & Empirical Basis
- `actors/inference/src/pipeline.py`: Curación geoespacial con `BallTree` e inferencia batch con `predict_and_score`.
- `actors/inference/src/scoring.py`: Carga en memoria y cómputo de scores corporativos (`FAMILIA` y `SOLTERO_EJECUTIVO`).
- `docs/architecture/01_ETL_Y_CURACION_DE_DATOS.md`: Documentación previa de rendimiento de enriquecimiento geoespacial (<10s para 1k registros).
- `docs/architecture/04_SCORE_DECISION_INFERENCIA_Y_HANDOFF.md`: Contrato de inferencia operativa y scores de decisión.

## Assumptions Eradication
- **Hecho comprobado 1:** Apify no factura por predicción individual, sino por Compute Units (CUs), donde 1 CU = 1 GB de RAM consumido durante 1 hora. Tarifa estándar: $0.20 USD por CU.
- **Hecho comprobado 2:** Para 1,000 registros sintéticos representativos de CABA, el pico de memoria residente no excede 530 MB, y para 10,000 registros se mantiene por debajo de 570 MB. La asignación de 1,024 MB (1.0 GB) en Apify provee un margen de seguridad >40% frente a OOM (Out Of Memory).
- **Hecho comprobado 3:** La complejidad temporal de inferencia es sublineal respecto al tamaño del lote gracias a la vectorización de NumPy/XGBoost y la indexación espacial con `BallTree`.

## Non-Goals
- Modificar la arquitectura de modelos ni reentrenar artefactos `.joblib`.
- Alterar los schemas de entrada o salida del Actor (`input_schema.json`).
- Modificar el flujo orquestador de n8n ni añadir endpoints de telemetría remota.

## What Changes
- **Modificación de Especificación:** Actualización de `openspec/specs/apify-inference-pipeline/spec.md` incorporando requisitos y escenarios Gherkin para la cota de latencia, memoria y consumo de CUs en lotes de 1,000 y 10,000 registros.
- **Script de Benchmark Reutilizable:** Creación de `scripts/benchmark_inference_cost.py` para medir y reportar deterministamente el tiempo, RAM y costo oficial en Apify.
- **Harness de Prueba Determinista:** Creación de `tests/test_inference_cost_benchmark.py` con aserciones estrictas de SLA (< 5.0s para 1k registros, < 10.0s para 10k registros, < 1024 MB de memoria).
- **Documentación Técnica Canónica:** Incorporación de la ficha comparativa y análisis financiero de CUs en `docs/architecture/04_SCORE_DECISION_INFERENCIA_Y_HANDOFF.md` y en `README.md`.

## Capabilities

### New Capabilities
<!-- No new capabilities; modifies existing apify-inference-pipeline -->

### Modified Capabilities
- `apify-inference-pipeline`: Incorpora requerimientos cuantitativos de SLA computacional, límites de memoria RAM y costo de Compute Units (CU) en lotes de 1,000 y 10,000 registros.

## Impact
- **Rendimiento:** Cero sobrecarga en producción; el benchmark se ejecuta exclusivamente en CI / testing / auditoría.
- **Contratos Públicos:** Sin impacto de ruptura (retrocompatible al 100%).
- **Dependencias:** Ninguna dependencia adicional requerida; utiliza el stack estándar del repositorio (`scikit-learn`, `xgboost`, `pandas`, `pytest`).
