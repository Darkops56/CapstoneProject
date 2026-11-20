# Design: Consolidación de Raíz del Monorepo en `actors/` y `src/`

## Context
Ver `proposal.md` para la motivación y `specs/monorepo-structure/spec.md` para los contratos normativos.
El monorepo actual posee 14 directorios visibles en la raíz, con módulos de backend y analítica (`config/`, `etl/`, `eda/`, `mlops/`) dispersos en carpetas con 1 o 2 archivos cada una, shims legados (`producto2/`) y dos actores serverless Apify (`actor/` y `trainer/`) en el primer nivel. Los tests pasan actualmente en verde (68 passed, 2 skipped). La arquitectura debe consolidarse manteniendo el principio de cero regresión determinista.

## Goals / Non-Goals

**Goals:**
- Agrupar los contenedores Apify en `actors/inference/` y `actors/trainer/`.
- Consolidar los paquetes de backend, ETL, EDA y MLOps en `src/`.
- Integrar `src` al `pythonpath` en `pytest.ini` asegurando compatibilidad transparente con imports existentes (`src-layout`).
- Reubicar `pipeline_observatorio_caba.ipynb` dentro de `notebooks/`.
- Eliminar físicamente el shim legado `producto2/` y migrar `test_producto2.py` a `test_inference_scoring.py`.
- Mantener 100% de la suite de pruebas automatizadas en verde (`Exit Code 0`).

**Non-Goals:**
- Actualizar `README.md` (excluido a solicitud explícita del usuario).
- Modificar el código interno o dependencias de `dashboard/` (Streamlit permanece aislado).
- Alterar la lógica matemática de ML, hiperparámetros o serializaciones `.joblib`.

## Decisions

### Decisión 1: Espacio de Nombres `actors/` para Contenedores Serverless
- **Elección:** Mover `actor/` -> `actors/inference/` y `trainer/` -> `actors/trainer/`.
- **Alternativas consideradas:**
  - *Mantenerlos en raíz:* Perpetúa la dispersión y confunde el rol de `actor/` frente a `trainer/`.
  - *Mover a `cloud/actors/`:* Agrega un nivel de anidamiento innecesario violando YAGNI.
- **Razón:** Ambos son actores Apify con Dockerfile autónomo y `WORKDIR /usr/src/app`. En Apify Console se configura la carpeta raíz del build como `actors/inference` y `actors/trainer`.

### Decisión 2: Consolidación de Backend en `src/` con `src-layout`
- **Elección:** Agrupar `config/`, `etl/`, `eda/` y `mlops/` dentro de `src/`, y configurar `pythonpath = src dashboard .` en `pytest.ini`.
- **Alternativas consideradas:**
  - *Refactorizar todos los imports a `from src.mlops import ...`:* Rompe compatibilidad retroactiva y eleva el radio de explosión a decenas de archivos sin beneficio técnico inmediato.
  - *Crear shims en raíz:* Reintroduce la basura que se busca eliminar.
- **Razón:** Añadir `src` al `pythonpath` es la convención estándar en Python (`src-layout`). Permite resolver tanto `from config import settings` como `from src.config import settings` de forma natural.

### Decisión 3: Resolución Absoluta de `BASE_DIR` en `src/config/settings.py`
- **Elección:** Definir `BASE_DIR = Path(__file__).resolve().parents[2]`.
- **Razón:** `settings.py` ahora reside a 3 niveles de profundidad (`src/config/settings.py` -> `parent` = `config`, `parent.parent` = `src`, `parents[2]` = raíz del proyecto). Usar `parents[2]` garantiza que `DATASETS_DIR`, `MLOPS_DIR`, `ETL_OUTPUT_DIR` apunten sin ambigüedad a la raíz del repositorio.

### Decisión 4: Extirpación de `producto2/` y Limpieza de Deuda Técnica
- **Elección:** Eliminar `producto2/` físicamente. En `src/mlops/train_models.py` reemplazar `from producto2 import inference` por `from mlops import inference`. Renombrar `tests/test_producto2.py` a `tests/test_inference_scoring.py` importando directamente desde `mlops`.
- **Razón:** `producto2` era un alias temporal obsoleto. Mantenerlo confunde a nuevos agentes y desarrolladores.

### Decisión 5: Reubicación de Notebooks en `notebooks/`
- **Elección:** Mover `pipeline_observatorio_caba.ipynb` a `notebooks/pipeline_observatorio_caba.ipynb`.
- **Razón:** Asegura que la raíz solo contenga configuraciones maestras (`pytest.ini`, `requirements.txt`, `.gitignore`) y documentación base.

## Matriz de Mapeo de Frontera (Principio de No-Colapso Semántico)

| Ruta de Origen | Ruta de Destino | Discriminador de Frontera | Tipo de Consumidor |
|---|---|---|---|
| `actor/` | `actors/inference/` | `{ tipo: "actor_serverless", rol: "scoring_mensual" }` | Apify / n8n |
| `trainer/` | `actors/trainer/` | `{ tipo: "actor_serverless", rol: "reentrenamiento_anual" }` | Apify / n8n |
| `config/` | `src/config/` | `{ tipo: "core_module", rol: "global_settings" }` | Monorepo / Backend |
| `etl/` | `src/etl/` | `{ tipo: "core_module", rol: "geo_curation" }` | Pipeline Anual / Notebooks |
| `eda/` | `src/eda/` | `{ tipo: "core_module", rol: "statistical_audit" }` | Analítica / Figuras |
| `mlops/` | `src/mlops/` | `{ tipo: "core_module", rol: "model_registry_and_training" }` | Pipeline / Inferencia Batch |
| `producto2/` | *ELIMINADO* | `{ tipo: "legacy_shim", estado: "deprecado" }` | N/A |
| `pipeline_observatorio_caba.ipynb` | `notebooks/pipeline_observatorio_caba.ipynb` | `{ tipo: "interactive_notebook", rol: "master_pipeline" }` | Analistas / Showcase |

## Protocolo Grill-Me Exhaustivo (14 Vectores de Falla Crítica)

1. **Ruptura de `sys.path` en ejecuciones CLI:**
   - *Riesgo:* Ejecutar `python src/mlops/train_models.py` falla por no encontrar `config`.
   - *Mitigación:* `settings.py` resuelve rutas absolutas y añade la raíz y `src` al `sys.path` defensivamente si no están presentes.
2. **Cálculo defectuoso de `BASE_DIR`:**
   - *Riesgo:* `BASE_DIR` resolviendo a `src/`, provocando que `Datasets/` se busque en `src/Datasets/`.
   - *Mitigación:* Aserción estricta en test unitario: `assert (config.BASE_DIR / "pytest.ini").exists()`.
3. **Falla de aislamiento hermético en Actor de Inferencia:**
   - *Riesgo:* `test_actor_hermetic_isolation` falla al buscar `actor.src.pipeline`.
   - *Mitigación:* Actualizar el script de aislamiento en `tests/test_apify_actor.py` para bloquear `etl`, `mlops` e importar `actors.inference.src.pipeline`.
4. **Desconexión de `scripts/prepare_geo_cache.py`:**
   - *Riesgo:* Precomputa archivos en ruta vieja `actor/reference_geo`.
   - *Mitigación:* Actualizar `OUTPUT_DIR = BASE_DIR / "actors" / "inference" / "reference_geo"`.
5. **Ruptura de `tests/test_geo_cache.py`:**
   - *Riesgo:* Aserción a `Path("actor/reference_geo")` falla.
   - *Mitigación:* Actualizar ruta de validación a `Path("actors/inference/reference_geo")`.
6. **Regresión en `tests/test_trainer_actor.py`:**
   - *Riesgo:* Imports rotos `from trainer.src...`.
   - *Mitigación:* Actualizar imports a `from actors.trainer.src.train_pipeline import ...`.
7. **Ruptura en `tests/test_end_to_end_notebook.py`:**
   - *Riesgo:* Validación de higiene busca `mlops/artifacts` y `pipeline_observatorio_caba.ipynb` en raíz.
   - *Mitigación:* Actualizar `NOTEBOOK_PATH` a `notebooks/pipeline_observatorio_caba.ipynb` y directorios esperados a `src/mlops/artifacts` y `actors/inference/reference_geo`.
8. **Incompatibilidad en Dockerfile de Actores:**
   - *Riesgo:* Dockerfile esperando contexto relativo diferente.
   - *Mitigación:* Los Dockerfiles usan `COPY src/ ./src/` y operan dentro de su carpeta. Se verifica que el contexto de build en Apify sea el subdirectorio del actor.
9. **Filtraciones en `.gitignore`:**
   - *Riesgo:* Artefactos de ETL generados en `src/etl/output/` no ignorados.
   - *Mitigación:* Agregar regla comodín `**/etl/output/` y `src/etl/output/` en `.gitignore`.
10. **Persistencia de archivos huérfanos:**
    - *Riesgo:* Quedar carpetas vacías en la raíz tras mover archivos.
    - *Mitigación:* Eliminación explícita de directorios raíz vacíos tras la migración.
11. **Ruptura de Streamlit Cloud:**
    - *Riesgo:* Streamlit buscando código en backend reubicado.
    - *Mitigación:* `dashboard/` tiene cero dependencias hacia `src/`, `actor/` o `mlops/` (opera 100% sobre Google Drive). Se mantiene intacto.
12. **Inconsistencia de Model Registry en `src/mlops/registry.json`:**
    - *Riesgo:* Rutas serializadas en `registry.json` rotas.
    - *Mitigación:* `registry.py` resuelve artefactos relativos a `MLOPS_ARTIFACTS_DIR` parametrizado en `settings.py`.
13. **Fallas de concurrencia en tests:**
    - *Riesgo:* Tests escribiendo en carpetas cruzadas.
    - *Mitigación:* Las pruebas usan fixtures temporales aisladas (`tmp_path`).
14. **Deriva Semántica y Regresión Silenciosa:**
    - *Riesgo:* Al completar el refactor, no todos los tests pasan.
    - *Mitigación:* Puerta de verificación determinista final: ejecución de `pytest` exigiendo 100% de éxito (`Exit Code 0`).

## Análisis de Impacto
- **Memoria / Latencia:** Cero impacto en runtime.
- **Observabilidad:** Mejora la visibilidad del monorepo en herramientas de análisis estático y linters.

## Plan de Migración y Rollback
- **Fase 1:** Configurar `pytest.ini` (`pythonpath = src dashboard .`) y reglas de `.gitignore`.
- **Fase 2:** Migrar `config/`, `etl/`, `eda/`, `mlops/` a `src/` mediante `git mv`. Ajustar `BASE_DIR` en `settings.py`.
- **Fase 3:** Migrar `actor/` y `trainer/` a `actors/inference/` y `actors/trainer/` mediante `git mv`.
- **Fase 4:** Mover `pipeline_observatorio_caba.ipynb` a `notebooks/`.
- **Fase 5:** Eliminar `producto2/` y actualizar imports en `train_models.py` y tests.
- **Fase 6:** Ejecución de suite completa de pruebas deterministas (`pytest`).
- **Estrategia de Rollback:** En caso de fallos irrecuperables en pruebas, ejecutar `git checkout .` y `git clean -fd` para regresar al estado limpio verificado previo al cambio.
