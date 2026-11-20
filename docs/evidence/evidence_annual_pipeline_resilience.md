# Evidencia de Verificación Determinista: `annual-pipeline-resilience-and-decoupling`

- **Fecha de verificación**: 2026-11-19
- **Cambio OpenSpec**: `annual-pipeline-resilience-and-decoupling`
- **Estado**: APROBADO (Exit Code 0 en todas las suites y validaciones)

---

## 1. Resumen de Implementación

| Componente | Archivo | Cambio Implementado |
| :--- | :--- | :--- |
| **Model Registry & Idempotencia** | `mlops/registry.py` | Cálculo determinista de hash SHA-256 (`compute_dataset_hash`), guarda de idempotencia (`SKIP_IDENTICAL_DATASET` en `bump_version`) y deduplicación por clave natural `(calle_normalizada, m2_cubiertos, ambientes)` (`deduplicate_annual_dataset`). |
| **Pipeline de Entrenamiento** | `trainer/src/train_pipeline.py` | Subsampling acotado de fondo SHAP (`compute_shap_background`, $N \le 100$) e inclusión de `dataset_hash` y `shap_background_size` en los metadatos y salida del pipeline. |
| **Exportador Atómico Drive** | `trainer/src/gdrive_exporter.py` | Subida en 2 fases (`export_version_to_gdrive_atomic`): staging en `staging_v(N+1)/`, verificación de integridad y renombrado atómico previo a actualizar `models_manifest.json`, con soporte de idempotencia SHA-256. |
| **Entrypoint Trainer** | `trainer/src/main.py` | Migración a `export_version_to_gdrive_atomic` reenviando `dataset_hash`. |
| **Workflow Anual n8n** | `workflows/n8n/workflow_anual_auditoria_gcba.json` | Degradación elegante (`continueOnFail: true`, `timeout: 30000ms`, token `WARN_GCBA_UNAVAILABLE`) y convergencia incondicional al nodo `Apify: Actor Trainer` (`waitForFinish=360`, `timeout: 360000ms`). |
| **Lienzo Unificado n8n** | `workflows/n8n/Pipeline Completo Anual y Mensual.json` | Integración del flujo anual convergente + retención dual (`01_mensual_enriquecido` vs. acumulador inmutable `04_historico_alquileres_anual`). |
| **Documentación Operativa** | `docs/README_DEPLOYMENT_N8N.md` | Documentación de `04_historico_alquileres_anual`, tabla de nodos actualizada y matriz de troubleshooting para `WARN_GCBA_UNAVAILABLE` y `SKIP_IDENTICAL_DATASET`. |

---

## 2. Resultados de Verificación Automatizada (SVC)

### 2.1 Suite Completa de Pruebas (`pytest -v`)
- **Comando**: `pytest -v`
- **Resultado**: **`49 passed in 6.26s`** (Exit Code 0)
- **Desglose de nuevas aserciones agregadas**:
  - `tests/test_n8n_workflows.py::test_annual_workflow_convergent_trainer_and_resilience` — **PASSED**
  - `tests/test_n8n_workflows.py::test_unified_pipeline_dual_retention_and_trainer` — **PASSED**
  - `tests/test_model_registry.py::test_dataset_hash_idempotency_skips_bump` — **PASSED**
  - `tests/test_model_registry.py::test_deduplicate_annual_dataset_natural_key` — **PASSED**
  - `tests/test_model_registry.py::test_shap_background_and_atomic_exporter` — **PASSED**
- **Regresión**: 44/44 pruebas preexistentes (Dashboard, Apify Actor, ETL/EDA, Geo-Cache, Producto 2, Trainer Actor, Model Registry y n8n Workflows) — **PASSED**

### 2.2 Validación Estricta de OpenSpec
- **Comando**: `openspec validate annual-pipeline-resilience-and-decoupling --strict`
- **Resultado**: `Change 'annual-pipeline-resilience-and-decoupling' is valid` (Exit Code 0)
