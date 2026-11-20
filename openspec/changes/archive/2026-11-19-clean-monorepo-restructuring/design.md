# Design: Saneamiento y Reestructuración Limpia del Monorepo

## Context
Ver `proposal.md` y `specs/monorepo-structure/spec.md`.  
Actualmente, el repositorio cuenta con 22 directorios y archivos en la raíz, arrastrando nomenclatura de entregas académicas (`producto1/`, `producto2/`), fragmentación de documentación (`explicacion/`, `Feature.md`, `PreguntasNegocio.txt`), un script con credenciales hardcodeadas (`ObtenerJsonApify.py`), y datos de muestra en una carpeta `data/` confusa.

Este diseño establece la transición segura y no destructiva hacia una estructura limpia, manteniendo 100% de compatibilidad hacia atrás en los tests de backend y la suite de Streamlit.

---

## Goals / Non-Goals

### Goals
- Consolidar toda la documentación técnica y de negocio en `docs/`.
- Sanitizar `ObtenerJsonApify.py` eliminando el token de Apify en texto plano y reubicándolo en `scripts/fetch_apify_raw.py`.
- Mover los fixtures de muestra de `data/` a `tests/fixtures/` y eliminar la carpeta `data/` de la raíz.
- Centralizar las rutas en `config/settings.py` permitiendo la formalización de `mlops/` y `etl/output/` con aliases retrocompatibles.
- Mantener la suite de tests en verde (33/33 tests pasando con Exit Code 0).

### Non-Goals
- No se reentrenarán modelos ni se modificarán hiperparámetros.
- No se alterarán los contratos de salida de Apify ni la lógica del dashboard.

---

## Decisions

### Decisión 1: Compatibilidad Retroactiva en `config/settings.py`
* **Elección**: Actualizar `config/settings.py` para definir `MLOPS_DIR = BASE_DIR / "mlops"` y mantener `PRODUCTO2_DIR = MLOPS_DIR` como alias, permitiendo que scripts antiguos sigan importando `config.PRODUCTO2_ARTIFACTS_DIR` sin romperse.
* **Alternativa descartada**: Romper los nombres anteriores y buscar/reemplazar en masa en todos los notebooks históricos. *Razón de descarte*: Riego innecesario de romper notebooks de referencia (`.ipynb`) que no forman parte del pipeline activo.

### Decisión 2: Cuarentena Estricta de Credenciales
* **Elección**: Reemplazar la constante `TOKEN = "apify_api_..."` por `TOKEN = os.environ.get("APIFY_TOKEN")` con excepción explícita si no está seteado.
* **Alternativa descartada**: Dejar el script en la raíz con el token. *Razón de descarte*: Vulnerabilidad crítica de seguridad en repositorios de código.

### Decisión 3: Eliminación de la Carpeta `data/` en la Raíz
* **Elección**: Reubicar `data/curated_sample_output.csv` y `data/sample_raw_listings.json` en `tests/fixtures/` y suprimir `data/` de la raíz.
* **Alternativa descartada**: Dejar `data/` en la raíz. *Razón de descarte*: Genera confusión con el dashboard, que ahora consume exclusivamente Google Drive y no debe dar la impresión de requerir un archivo local.

---

## Protocolo Grill Me Exhaustivo: 10 Escenarios de Falla Crítica

| ID | Vector de Falla Crítica | Causa Raíz / Frontera | Discriminador Causal 1:1 (`{tipo, razon}`) | Mitigación y Recuperación Determinista |
| :--- | :--- | :--- | :--- | :--- |
| **V1** | **Fallo en tests de Producto 2 por renombramiento** | `tests/test_producto2.py` no encuentra los artefactos `.joblib` tras mover la carpeta. | `{tipo: IO_ERR, razon: ARTIFACT_PATH_NOT_RESOLVED}` | Configurar alias en `config/settings.py` que resuelvan a `mlops/artifacts` o verificar existencia antes del movimiento. |
| **V2** | **Fallo en tests de ETL por ruta de Producto 1** | `test_etl_and_eda.py` busca `producto1_dataset_curado.csv` en la ruta anterior. | `{tipo: IO_ERR, razon: ETL_OUTPUT_DRIFT}` | Mantener la ruta en `config/settings.py` apuntando a `etl/output/` con fallback de compatibilidad. |
| **V3** | **Exposición accidental de credenciales en Git history** | El token de Apify queda registrado en commits previos. | `{tipo: SEC_ERR, razon: TOKEN_IN_HISTORY}` | Sanitizar el archivo inmediatamente y advertir al usuario para revocar el token en la consola de Apify. |
| **V4** | **ImportError en `tests/test_geo_cache.py`** | Rutas relativas a `Datasets/` fallan al reorganizar. | `{tipo: IMP_ERR, razon: GEO_CACHE_IMPORT_FAIL}` | No mover `Datasets/` de forma destructiva; mantener el symlink o path relativo en `config/settings.py`. |
| **V5** | **Ruptura de links en documentación** | `README.md` referencia archivos en `explicacion/` que se movieron a `docs/`. | `{tipo: DOC_ERR, razon: BROKEN_MARKDOWN_LINKS}` | Actualizar las referencias cruzadas en `README.md` hacia las nuevas rutas en `docs/`. |
| **V6** | **Fallo en pruebas de n8n por fixtures movidos** | `test_n8n_workflows.py` intenta leer muestras JSON desde `data/`. | `{tipo: IO_ERR, razon: FIXTURE_NOT_FOUND_IN_DATA}` | Actualizar los paths de fixtures en los tests para apuntar a `tests/fixtures/`. |
| **V7** | **Incompatibilidad con Streamlit Cloud** | Streamlit Cloud intenta buscar archivos en la raíz que fueron movidos. | `{tipo: DEPLOY_ERR, razon: STREAMLIT_CLOUD_ROOT_DRIFT}` | El dashboard ya está 100% aislado en `dashboard/`; nada en la raíz afecta la UI. |
| **V8** | **Desaparición de notebooks EDA** | Los notebooks `.ipynb` fallan al buscar figuras en `figures/`. | `{tipo: NOTEBOOK_ERR, razon: FIGURE_PATH_DRIFT}` | Mantener la estructura interna de `eda/` y sus figuras intactas. |
| **V9** | **Colisión de imports entre `mlops` y otros paquetes** | Un paquete con nombre común en `sys.path` colisiona. | `{tipo: PKG_ERR, razon: NAMESPACE_COLLISION}` | `mlops` es un namespace interno protegido por la raíz del proyecto. |
| **V10** | **Residuos de archivos temporales en Git** | Archivos `.DS_Store` o `Thumbs.db` se introducen durante la reubicación. | `{tipo: GIT_DIRTY, razon: UNTRACKED_SYSTEM_FILES}` | Ejecutar `git status` limpio antes de confirmar cada paso. |

---

## Risks / Trade-offs

* **Riesgo**: `tests/test_apify_actor.py` podría depender de la ubicación de los modelos.  
  *Mitigación*: `actor/artifacts/` tiene sus propios `.joblib` congelados para producción; no depende de `producto2/` en runtime.

---

## Migration Plan

1. **Documentación**: Crear `docs/architecture/` y `docs/evidence/`; mover `explicacion/`, `Feature.md`, `PreguntasNegocio.txt` y `evidence.md`.
2. **Scripts y Seguridad**: Sanitizar y mover `ObtenerJsonApify.py` a `scripts/fetch_apify_raw.py`.
3. **Fixtures y Datos**: Mover archivos de `data/` a `tests/fixtures/` y remover `data/`.
4. **Módulos**: Reorganizar `producto1/` a `etl/output/` y `producto2/` a `mlops/`, actualizando `config/settings.py`.
5. **Verificación de Regresión**: Ejecutar `pytest` para certificar que los 33 tests pasen al 100%.
6. **Commit y Push**: Publicar cambios limpios en `main`.
