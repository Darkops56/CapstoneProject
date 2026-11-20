## Why

Actualmente el repositorio pesa ~163 MB en `Datasets/` versionados en git y fragmenta el flujo de ciencia de datos en tres notebooks desconectados (`etl/etl_pipeline.ipynb`, `eda/eda_phase2.ipynb`, `mlops/inference.ipynb`) sin un cuaderno de entrenamiento ni descarga en vivo de fuentes. Esto impide transportar el proyecto con lo mínimo e indispensable y deja fuera gráficos críticos de evaluación y sesgo exigidos por el material de `apuntes/` (SIC) para la defensa ejecutiva del Capstone.

## Tier de Complejidad (Gobernanza YAGNI)

* **Tier asignado:** **Tier M (Medio)**.
* **Justificación YAGNI:** Introduce un nuevo artefacto principal ejecutable (Notebook Maestro End-to-End + módulo auxiliar liviano de descarga/evaluación testeable), modifica la higiene del repositorio (`Datasets/` y `etl/output/` excluidos de git) y adapta tests de integración. No altera el núcleo de producción (`actor/`, `trainer/`, `dashboard/`, `workflows/n8n/`), por lo que no amerita arquitectura Tier L ni capas de abstracción innecesarias.

## What Changes

* **Nuevo Notebook Maestro End-to-End (`pipeline_observatorio_caba.ipynb`) en la raíz del repositorio:**
  * Replica paso a paso el flujo de `workflows/n8n/Pipeline Completo Anual y Mensual.json` **sin utilizar los actores custom de Apify** (`lukita7956~zonaprop-curator-inference` ni `lukita7956~mlops-annual-trainer`), consumiendo únicamente el actor scraper de terceros (`memo23~zonaprop-scraper`) y la CKAN API oficial del GCBA.
  * Crea dinámicamente en runtime las carpetas `Datasets/Originales`, `Datasets/Curados`, `etl/output`, `mlops/artifacts` y `mlops/figures`.
  * Configurable en la celda 0 con `APIFY_MODE` (`"last_run"` para reutilizar el último run exitoso sin gastar créditos o `"run_new"` para disparar scraping nuevo con `maxItems`).
  * Ejecuta en secuencia: Setup → Ingesta Live (CKAN + Apify Scraper) → ETL & Enriquecimiento Geoespacial → EDA & Selección de 10 Features (VIF < 10) → Entrenamiento (K-Means + Comparativa Baseline vs. Ridge vs. Random Forest vs. XGBoost) → Panel de **8 Gráficos de Defensa Ejecutiva** → Inferencia Individual/Batch y Score de Decisión (0–100).
  * **Documentación y comentarios didácticos obligatorios:** cada bloque debe contar con celdas Markdown explicativas (objetivo, supuestos, interpretación de negocio) y comentarios inline claros en el código Python explicando cada transformación, fórmula, hiperparámetro y gráfico, de modo que el cuaderno sea autoexplicativo para la defensa técnica y para terceros.
* **Módulo auxiliar testeable (`scripts/notebook_helpers.py`):** encapsula la descarga defensiva de CKAN GCBA, la resolución de Apify (`last_run`/`run_new`) y las funciones de evaluación comparativa/residuos para garantizar pruebas unitarias deterministas sin duplicar lógica opaca en el notebook.
* **Limpieza del repositorio para portabilidad mínima:**
  * **BREAKING (entorno local sin ejecutar notebook):** Eliminación de `Datasets/` (163 MB) y `etl/output/` (368 KB) del índice de git y del árbol de trabajo, agregándolos explícitamente a `.gitignore`.
  * Eliminación de los 3 notebooks legados (`etl/etl_pipeline.ipynb`, `eda/eda_phase2.ipynb`, `mlops/inference.ipynb`) reemplazados por `pipeline_observatorio_caba.ipynb`.
  * Se conservan `mlops/artifacts/` (480 KB) y `actor/reference_geo/` (28 MB) para preservar la integridad de tests de inferencia y despliegues de `actor/Dockerfile`.
* **Actualización y ampliación de tests deterministas:**
  * Ajuste de `test_datasets_curados_folder_has_5_valid_csvs()` en `tests/test_etl_and_eda.py` para usar `pytest.skip` cuando `Datasets/Curados/` no exista en un clone limpio.
  * Nueva suite `tests/test_end_to_end_notebook.py` que valida sintaxis AST de todas las celdas, presencia de comentarios/Markdown, cobertura de los 8 gráficos, descarga CKAN/Apify con mocks y escenarios negativos.

## Archivos Inspeccionados del Repositorio

* `workflows/n8n/Pipeline Completo Anual y Mensual.json` (catálogo CKAN GCBA y payload de `memo23~zonaprop-scraper`).
* `etl/etl_pipeline.ipynb`, `eda/eda_phase2.ipynb`, `mlops/inference.ipynb` (fragmentación actual y ausencia de notebook de entrenamiento).
* `mlops/train_models.py`, `mlops/model_metrics.json`, `scripts/fetch_apify_raw.py` (lógica de entrenamiento y descarga actual).
* `tests/test_etl_and_eda.py` (líneas 182–225: dependencia dura sobre `Datasets/Curados/`).
* `.gitignore` (exclusiones actuales; `Datasets/` y `etl/output/` hoy están trackeados en git).
* `apuntes/clase_24_Matplotlib_Probabilidad.ipynb`, `apuntes/clase_33_Titanic_Investigacion_Integradora.ipynb`, `apuntes/clase_36_C5_00b_TITANIC_ETL_FE_Preprocessing.ipynb`, `apuntes/clase_36_C5_00c_CANCER_ETL_FE_Preprocessing.ipynb` y `apuntes/Capstone Project - Clase 42 hasta Clase 47/capstone_project_cronograma_alumnos.xlsx` (criterios de gráficos, baseline, sesgo-varianza y auditoría de error por subgrupo).

## Capabilities

### New Capabilities
- `end-to-end-notebook`: Flujo reproducible en un único Notebook Maestro comentado (`pipeline_observatorio_caba.ipynb`) con creación dinámica de carpetas, ingesta live CKAN GCBA + Apify Scraper, entrenamiento/evaluación con 8 gráficos de defensa ejecutiva y repositorio limpio sin datasets versionados.

### Modified Capabilities
<!-- Ninguna capacidad existente en openspec/specs/ cambia sus requisitos de producción. -->

## Impact

* **Rendimiento y almacenamiento:** Reduce el tamaño versionado del repositorio en **~163.4 MB** (`Datasets/` + `etl/output/`). La ejecución completa del notebook en modo live depende de latencia de red CKAN/Apify (~1–4 min) y memoria pico en entrenamiento (~500 MB–1 GB).
* **Contratos públicos:** No modifica contratos de `dashboard/`, `actor/`, `trainer/`, `workflows/n8n/` ni `openspec/specs/apify-inference-pipeline/spec.md`. Introduce el contrato de configuración del notebook (`APIFY_TOKEN`, `APIFY_MODE`, `MAX_ITEMS`) y tokens canónicos de error en `scripts/notebook_helpers.py`.
* **Compatibilidad hacia atrás:** Quienes clonen el repo ya no encontrarán `Datasets/` ni `etl/output/` precargados; deberán ejecutar `pipeline_observatorio_caba.ipynb` para generarlos. `pytest` seguirá pasando en Exit Code `0` en clones limpios sin datasets.
* **Dependencias:** Cero paquetes externos nuevos no presentes ya en el stack científico del repo (`requests`, `pandas`, `numpy`, `scipy`, `scikit-learn`, `xgboost`, `shap`, `matplotlib`, `seaborn`, `openpyxl`, `joblib`).

## Non-Goals

* No modificar ni desplegar cambios en los workflows de `workflows/n8n/`, `actor/`, `trainer/` ni `dashboard/`.
* No eliminar `actor/reference_geo/` ni `mlops/artifacts/`.
* No implementar scraping propio (BeautifulSoup/Playwright) para Zonaprop; se utiliza explícitamente el actor scraper `memo23~zonaprop-scraper`.
* No incluir modelos de series temporales (Prophet) ni gráficos exploratorios secundarios fuera del set de Defensa Ejecutiva.

## Assumptions Eradication (Hechos Comprobados)

* **Comprobado:** `Datasets/` pesa 163 MB y sus 9 archivos están actualmente trackeados en git (`git ls-files Datasets/`).
* **Comprobado:** `tests/test_etl_and_eda.py:209-225` falla si `Datasets/Curados/` no existe, mientras que `tests/test_etl_and_eda.py:182-186` ya utiliza `pytest.skip`.
* **Comprobado:** El workflow n8n consulta 4 IDs en CKAN GCBA (`delitos`, `bocas-subte`, `mapa-ruido`, `establecimientos-educativos`) y el actor `memo23~zonaprop-scraper`.
* **Comprobado:** No existe ningún notebook de entrenamiento en el repositorio; el entrenamiento existe solo en `mlops/train_models.py` y `trainer/src/train_pipeline.py`.
