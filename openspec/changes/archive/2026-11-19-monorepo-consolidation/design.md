# Design: Consolidación Monorepo y Desacoplamiento de Despliegue

## Context
Ver `proposal.md` y `specs/monorepo-workspace/spec.md`.  
Actualmente, la rama `origin/main` contiene el pipeline ETL (`etl/`), el módulo de modelado (`producto2/`), el actor Apify (`actor/`) y material pesado en `apuntes/`. La rama `interactive_property_map_dashboard` contiene la aplicación Streamlit completa y probada en la raíz del repositorio.

El objetivo técnico es integrar el dashboard dentro de `main` en un subdirectorio aislado `dashboard/`, configurar el repositorio para despliegue continuo en Streamlit Community Cloud (`Main file path: dashboard/app.py`), sanear el rastreo de Git para excluir ~500 MB de binarios/PDFs prescindibles, y garantizar la no-regresión mediante verificación automatizada.

---

## Goals / Non-Goals

### Goals
- Unificar ambas ramas en `main` bajo una estructura de monorepo coherente.
- Mover todos los archivos del dashboard a `dashboard/` (`app.py`, `src/`, `data/`, `tests/`, `.streamlit/`, `requirements.txt`).
- Aislar las dependencias: el dashboard solo instala lo necesario para la UI (`pandas`, `streamlit`, `pydeck`, `numpy`, `openpyxl`, `pytest`), sin arrastrar `xgboost`, `scikit-learn` ni `shap`.
- Mantener compatibilidad 100% con Streamlit Community Cloud usando `dashboard/app.py`.
- Excluir del seguimiento de Git `apuntes/` y datasets pesados superiores a 50MB.

### Non-Goals
- No se crearán microservicios REST ni APIs intermedias (YAGNI).
- No se alterarán los scripts de entrenamiento (`producto2/train_models.py` pasa a `mlops/` o se preserva como módulo MLOps).
- No se modificará la lógica de negocio de scoring del dashboard.

---

## Decisions

### Decisión 1: Estructura de Subdirectorio Autónomo (`dashboard/`)
* **Elección**: Agrupar todo el código de presentación dentro de `dashboard/` con su propio `requirements.txt` y configuración `.streamlit/config.toml`.
* **Alternativa descartada**: Dejar `app.py` en la raíz. *Razón de descarte*: Mezclaría dependencias de ML (`xgboost`, `scikit-learn`) con las de Streamlit en un solo `requirements.txt` gigante, ralentizando el build del cloud y provocando conflictos de compilación en Debian/Linux.
* **Alternativa descartada**: Separar en dos repositorios de GitHub distintos. *Razón de descarte*: Viola el requerimiento del usuario de mantener un flujo unificado y requeriría sincronización manual de releases entre repos.

### Decisión 2: Desacoplamiento por Artefacto (CSV Enriquecido)
* **Elección**: El dashboard consume exclusivamente el archivo CSV procesado (`alquileres_caba_enriquecido_YYYY_MM.csv` desde Google Drive o `fallback_data.csv` local).
* **Alternativa descartada**: Inferencia en tiempo de ejecución (Streamlit cargando el modelo XGBoost y KMeans para predecir al vuelo). *Razón de descarte*: Eleva el consumo de memoria RAM por encima de los 1 GB en Streamlit Cloud (provocando OOM kills), y suma latencia innecesaria de arranque.

### Decisión 3: Higiene de Repositorio mediante `.gitignore`
* **Elección**: Agregar `apuntes/` y cachés a `.gitignore` en `main`, manteniendo los archivos en el disco local del usuario pero evitando que se suban a GitHub.
* **Alternativa descartada**: `git rm -r apuntes/` destructivo sin respaldo. *Razón de descarte*: El usuario perdería las notas y resúmenes de cátedra. Excluirlos con `.gitignore` preserva su copia local sin penalizar el repositorio remoto.

---

## Protocolo Grill Me Exhaustivo: 12 Escenarios de Falla Crítica

| ID | Vector de Falla Crítica | Causa Raíz / Frontera | Discriminador Causal 1:1 (`{tipo, razon}`) | Mitigación y Recuperación Determinista |
| :--- | :--- | :--- | :--- | :--- |
| **V1** | **ImportError en `dashboard/app.py`** | Rutas de importación `from src.config import ...` fallan al mover `app.py` a una subcarpeta. | `{tipo: IMP_ERR, razon: SYS_PATH_MISSING_DASHBOARD}` | `dashboard/app.py` añade explícitamente su propio directorio al `sys.path` al inicio: `sys.path.insert(0, os.path.dirname(__file__))`. |
| **V2** | **FileNotFoundError en `fallback_data.csv`** | Rutas relativas `data/fallback_data.csv` asumen ejecución desde la raíz en vez de `dashboard/`. | `{tipo: IO_ERR, razon: RELATIVE_PATH_ROOT_DRIFT}` | `src/config.py` resuelve rutas absolutas ancladas a `Path(__file__).parent.parent / "data" / "fallback_data.csv"`. |
| **V3** | **Fallo de Build en Streamlit Cloud** | Streamlit Cloud busca `requirements.txt` en la raíz en lugar de `dashboard/requirements.txt`. | `{tipo: DEPLOY_ERR, razon: ROOT_REQ_FILE_EMPTY}` | Proveer un `requirements.txt` en la raíz que apunte a `-r dashboard/requirements.txt` o contenga las dependencias mínimas del dashboard. |
| **V4** | **OOM en Streamlit Cloud por dependencias ML** | Inclusión accidental de `xgboost`/`scikit-learn` en las dependencias de producción. | `{tipo: MEM_KILL, razon: UNWANTED_ML_DEPS_IN_DASHBOARD}` | `dashboard/requirements.txt` auditado y en cuarentena estricta (solo `streamlit`, `pandas`, `pydeck`, `numpy`, `openpyxl`). |
| **V5** | **Inotify Limit Exceeded en Linux** | Streamlit intenta monitorear archivos en el nuevo path con watchdog. | `{tipo: KERNEL_ERR, razon: INOTIFY_EXHAUSTION}` | Trasladar `.streamlit/config.toml` con `fileWatcherType = "none"` dentro de `dashboard/.streamlit/` y la raíz. |
| **V6** | **Ruptura de Tests Pytest** | `pytest dashboard/tests/` falla porque `conftest.py` no resuelve los módulos de `dashboard/src`. | `{tipo: TEST_ERR, razon: PYTEST_ROOT_MISMATCH}` | Configurar `pythonpath = ["dashboard"]` en `pytest.ini` o resolver en `dashboard/tests/conftest.py`. |
| **V7** | **Conflictos de Merge Git** | Choque de historiales entre `interactive_property_map_dashboard` y `main`. | `{tipo: GIT_ERR, razon: DIVERGENT_COMMIT_HISTORIES}` | Ejecutar integración ordenada preparando la estructura de `dashboard/` en la rama de trabajo antes del merge hacia `main`. |
| **V8** | **Carga de Dataset Remoto Rota** | La URL o ID de Google Drive es inaccesible o expira. | `{tipo: NET_ERR, razon: GDRIVE_UNREACHABLE_OR_TIMEOUT}` | `dashboard/src/data_loader.py` implementa fallback determinista a `fallback_data.csv` y emite `st.info("Datos Locales (Offline)")`. |
| **V9** | **Sobreescritura accidental de `producto2`** | El merge pisa los modelos entrenados `.joblib` existentes en `main`. | `{tipo: DATA_ERR, razon: CLOBBER_PRETRAINED_WEIGHTS}` | Los archivos del dashboard viven estrictamente en `dashboard/`; cero colisión con `producto2/` o `actor/`. |
| **V10** | **Deriva de Schema CSV** | El pipeline mensual de Apify genera columnas nuevas no previstas en el dashboard. | `{tipo: SCHEMA_ERR, razon: UNEXPECTED_CSV_COLUMNS}` | `dashboard/src/normalizer.py` valida defensivamente y completa columnas requeridas faltantes con defaults. |
| **V11** | **Sobrecarga de Clonación por PDFs** | Clonar `main` descarga 500 MB de material de lectura académica. | `{tipo: REPO_BLOAT, razon: UNTRACKED_APUNTES_IN_GIT}` | Registrar `apuntes/` en `.gitignore` antes del push unificado. |
| **V12** | **Falsa regresión visual en navegador** | El usuario no ve los cambios debido a la caché de sesión de Streamlit o del navegador. | `{tipo: CACHE_ERR, razon: BROWSER_SESSION_STALE}` | Documentar la necesidad de refresco forzado (`Ctrl+Shift+R` o `R`) en el `README.md`. |

---

## Risks / Trade-offs

* **Riesgo**: Streamlit Cloud ejecutado desde `main` necesita saber explícitamente qué archivo levantar.  
  *Mitigación*: Documentar paso a paso la configuración de la app en Streamlit Cloud (*Main file path*: `dashboard/app.py`).
* **Riesgo**: Pytest ejecutado desde la raíz podría no encontrar los fixtures si no se especifica la ruta.  
  *Mitigación*: Crear `pytest.ini` en la raíz con `testpaths = ["dashboard/tests"]` y `pythonpath = ["dashboard"]`.

---

## Migration Plan

1. **Reorganizar rama actual**: Mover los archivos del dashboard a `dashboard/` en `interactive_property_map_dashboard`.
2. **Validar suite de tests en nueva ruta**: Ejecutar `pytest dashboard/tests/` (verificar 11/11 pasando).
3. **Checkout y sincronización de `main`**: Traer los cambios de `dashboard/` a `main`.
4. **Higiene de `.gitignore`**: Asegurar exclusión de `apuntes/` y binarios pesados.
5. **Generar `README.md` unificado**: Explicar la arquitectura Monorepo, flujo de ML y despliegue del dashboard.
6. **Push a `main`**: Publicar la rama unificada en GitHub.
