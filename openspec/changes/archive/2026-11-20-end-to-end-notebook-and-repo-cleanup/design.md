## Context

Ver `proposal.md` para la motivación y alcance. El repositorio cuenta actualmente con pipelines Python modulares (`etl/etl_pipeline.py`, `eda/eda_phase2.py`, `mlops/train_models.py`, `mlops/inference.py`) y configuración centralizada (`config/settings.py`), pero carece de un cuaderno maestro ejecutable end-to-end que descargue fuentes en vivo (CKAN GCBA + scraper Apify `memo23~zonaprop-scraper`), entrene, compare contra baselines y genere los 8 gráficos de Defensa Ejecutiva. Además, `Datasets/` (163 MB) y `etl/output/` (368 KB) están trackeados en git, y `tests/test_etl_and_eda.py:209` asume la existencia física de `Datasets/Curados/`.

## Goals / Non-Goals

**Goals:**
* Consolidar el flujo completo en un único cuaderno raíz (`pipeline_observatorio_caba.ipynb`) 100% comentado y explicado en español (celdas Markdown por fase + comentarios inline en código).
* Extraer la lógica de frontera (creación de carpetas, descarga CKAN GCBA, cliente Apify Scraper `last_run`/`run_new`, comparativa Baseline vs. XGBoost, cálculo de errores por subgrupo) en `scripts/notebook_helpers.py` para verificación determinista vía `pytest`.
* Remover `Datasets/`, `etl/output/` y los 3 notebooks legados del índice de git y del árbol local, manteniendo `pytest` en Exit Code `0`.

**Non-Goals:**
* Reescribir la lógica de negocio del ETL geoespacial (`etl/etl_pipeline.py`) o del Score de Decisión (`mlops/inference.py`): el notebook los orquesta y explica, reutilizando funciones probadas.
* Alterar `actor/`, `trainer/`, `dashboard/` o `workflows/n8n/`.

## Decisions

### 1. Separación Notebook narrativo + `scripts/notebook_helpers.py`
* **Decisión:** Colocar los clientes HTTP defensivos (CKAN y Apify) y utilidades de evaluación comparativa en `scripts/notebook_helpers.py`, invocados desde `pipeline_observatorio_caba.ipynb`.
* **Justificación (Impuesto a la Complejidad):** Sin este módulo liviano, probar la descarga CKAN/Apify o el guardrail de regresión requeriría ejecutar el notebook completo con red real (no determinista y costoso en créditos Apify). Con el helper, las celdas del notebook permanecen limpias, legibles y profusamente comentadas, mientras `pytest` valida cada frontera con mocks en milisegundos.
* **Alternativa descartada:** Código monolítico solo en celdas `.ipynb` (dificulta testing unitario y control de diffs).

### 2. Estrategia de comentarios y documentación didáctica del Notebook
* **Decisión:** Cada uno de los 7 pasos (Paso 0 a Paso 6) abrirá con una celda Markdown estructurada en 3 puntos: **Qué hacemos**, **Por qué importa para el negocio/Capstone** y **Qué validar en la salida**. Cada celda de código incluirá comentarios inline (`#`) por bloque lógico (parámetros, transformaciones, métricas y lectura de cada gráfico).
* **Justificación:** Cumple el requisito explícito del usuario para defensa técnica y transferencia del proyecto.

### 3. Parámetros de configuración justificados (sin defaults arbitrarios)
* `APIFY_MODE = "last_run"` por defecto: evita consumir créditos de Apify en ejecuciones exploratorias; cambiar a `"run_new"` replica el comportamiento mensual de n8n.
* `MAX_ITEMS = 200` (en modo `"run_new"`): suficiente para superar el mínimo estadístico de entrenamiento (`>= 100` tras limpieza/outliers) manteniendo la ejecución bajo 90 s; ajustable a `1000` para corridas de producción.
* `HTTP_TIMEOUT_S = 60` para CKAN y `WAIT_FOR_FINISH_S = 300` para `memo23~zonaprop-scraper`: alineado con los timeouts reales de `workflows/n8n/Pipeline Completo Anual y Mensual.json` (`timeout: 300000` ms) para evitar cortes prematuros en descargas de `delitos` (~30–60 MB).
* `MIN_R2_THRESHOLD = 0.50` (en helper de validación del notebook, configurable a `0.70`/`0.80` en datasets completos): previene falsos positivos con muestras chicas en `"run_new"` sin relajar la exigencia de superar estrictamente al `DummyRegressor`.

### 4. Selección defensiva de recursos CKAN GCBA
* **Decisión:** Para cada `datasetId` (`delitos`, `bocas-subte`, `mapa-ruido`, `establecimientos-educativos`), filtrar recursos por formato (`csv`, `xlsx`), priorizando palabras clave semánticas (ej. `diurno` en `mapa-ruido`, año más reciente en `delitos`) y validando que el archivo descargado contenga al menos un subconjunto de columnas geográficas/clave antes de guardarlo en `Datasets/Originales/`.

### 5. Principio de No-Colapso Semántico y Matriz de Mapeo de Frontera

Toda operación de frontera en `scripts/notebook_helpers.py` retorna o lanza un discriminador causal 1:1 (`{"tipo": S_final, "razon": R_i}`) para evitar colapsar fallos de red, credenciales o esquema bajo un error genérico:

| Frontera | Estado Final (`tipo`) | Causa Raíz (`razon` / Token Canónico) | Acción del Notebook |
| :--- | :--- | :--- | :--- |
| Auth Apify | `ABORTED` | `ERR_MISSING_APIFY_TOKEN` | Detiene Paso 1 antes de red; indica exportar `APIFY_TOKEN`. |
| Config Apify | `ABORTED` | `ERR_INVALID_APIFY_MODE` | Detiene Paso 1; lista valores válidos (`last_run`, `run_new`). |
| CKAN GCBA HTTP | `FAILED` | `ERR_GCBA_DOWNLOAD` | Reporta `datasetId` y status HTTP; no escribe archivo parcial. |
| CKAN GCBA Schema | `FAILED` | `ERR_GCBA_SCHEMA` | Reporta columnas faltantes vs. recibidas; descarta archivo inválido. |
| Apify Scraper | `FAILED` | `ERR_APIFY_SCRAPER_FAILED` | Reporta status HTTP / run fallido / 0 ítems. |
| Evaluación ML | `REJECTED` | `ERR_METRIC_REGRESSION` | Bloquea exportación de `.joblib` si XGBoost no supera baseline/umbral. |
| Ejecución Exitosa | `OK` | `COMPLETED` | Persiste artefacto y continúa al paso siguiente. |

## Protocolo Grill-Me Exhaustivo (12 Escenarios de Falla Crítica)

1. **Token de Apify ausente o en blanco (`""` / `"   "`):** Validado con `.strip()` antes de cualquier request; lanza `ERR_MISSING_APIFY_TOKEN` con 0 llamadas HTTP.
2. **Fuga accidental de token en el `.ipynb`:** El notebook nunca incrusta el token en código ni lo imprime; el test estático verifica ausencia de patrones `apify_api_`.
3. **CKAN GCBA devuelve HTTP 500/503 o timeout:** `requests.get(..., timeout=60)` captura `RequestException` y lanza `ERR_GCBA_DOWNLOAD` indicando el `datasetId` afectado.
4. **CKAN GCBA cambia de `.xlsx` a `.csv` (o viceversa):** El selector acepta ambos formatos y el ETL/helper lee según extensión real (`read_csv` / `read_excel`).
5. **CKAN GCBA publica recurso con columnas renombradas o archivo HTML de error:** Validación post-descarga de columnas mínimas; si falla, borra el archivo corrupto y lanza `ERR_GCBA_SCHEMA`.
6. **Apify `last_run` no tiene runs previos con estado `SUCCEEDED`:** El helper filtra `status == "SUCCEEDED"` y si no existe ninguno lanza `ERR_APIFY_SCRAPER_FAILED` sugiriendo cambiar a `APIFY_MODE = "run_new"`.
7. **Apify `run_new` devuelve 0 ítems o bloquea por cambio en Zonaprop:** Guardrail `len(items) < 1` lanza `ERR_APIFY_SCRAPER_FAILED` antes del ETL.
8. **Ejecución en Google Colab sin repo clonado:** La celda 0 detecta `google.colab` y clona el repo o ajusta `sys.path` automáticamente antes de importar `scripts.notebook_helpers`.
9. **Dataset pequeño (`< 50` filas válidas) al usar `maxItems` bajo:** La curva de aprendizaje y 5-Fold CV ajustan `cv = min(5, max(2, len(df) // 10))` o detienen con advertencia explícita si `len(df) < 20`.
10. **Data Leakage en comparativa Baseline vs. Modelos:** Todos los modelos (`DummyRegressor`, `Ridge`, `RandomForest`, `XGBoost`) se encapsulan en `sklearn.pipeline.Pipeline` (imputación + escalado aprendidos exclusivamente en `train`) con `TransformedTargetRegressor(func=np.log1p, inverse_func=np.expm1)`.
11. **Regresión en `pytest` tras borrar `Datasets/` y `etl/output/`:** `tests/test_etl_and_eda.py:test_datasets_curados_folder_has_5_valid_csvs` se actualiza con `pytest.skip` condicional cuando `Datasets/Curados/` no existe.
12. **Limpieza incompleta en git (archivos siguen en índice tras agregar a `.gitignore`):** Se ejecuta `git rm -r --cached Datasets etl/output` y se verifica `git ls-files` == 0 líneas.

## Impacto en Memoria, Latencia, Concurrencia y Observabilidad

* **Memoria:** Pico estimado de ~600 MB–1.1 GB durante la carga de `delitos` y cálculo de `shap.Explainer` (mitigado acotando `shap.sample(X, min(150, len(X)))`).
* **Latencia:** Ingesta CKAN (~15–45 s) + Apify (`last_run`: ~5 s; `run_new` 200 items: ~60–120 s) + ETL/EDA/Modelado (~20–40 s).
* **Concurrencia:** Ejecución secuencial monocelda en Jupyter/Colab; sin estado compartido concurrente. Escritura atómica en disco (escribe archivo validado tras verificación de esquema).
* **Observabilidad:** Cada paso imprime un resumen estructurado (`[PASO X] estado | filas | archivo generado`) y persiste `mlops/model_metrics.json` + 8 figuras `.png` en `mlops/figures/`.

## Risks / Trade-offs

* **[Riesgo] Disponibilidad externa de CKAN GCBA en vivo durante la defensa** → Mitigación: si el usuario ya corrió el notebook una vez en su máquina/Colab, las carpetas locales `Datasets/Originales/` ya existen y el helper permite un flag `SKIP_IF_EXISTS = True` para reutilizar lo descargado en esa sesión sin depender del portal en tiempo real.
* **[Trade-off] Eliminar los 3 notebooks anteriores** → Reduce ruido y mantenimiento duplicado, a cambio de centralizar todo el recorrido didáctico en `pipeline_observatorio_caba.ipynb`.

## Migration Plan & Rollback

* **Migración:** Crear `scripts/notebook_helpers.py` y `pipeline_observatorio_caba.ipynb` → actualizar `tests/test_etl_and_eda.py` y agregar `tests/test_end_to_end_notebook.py` → actualizar `.gitignore` → remover `Datasets/`, `etl/output/` y los 3 notebooks legados → ejecutar `pytest` completo (Exit Code `0`).
* **Rollback:** `git checkout -- .` restaura los notebooks legados y el índice de git si cualquier validación de SVC fallara.
