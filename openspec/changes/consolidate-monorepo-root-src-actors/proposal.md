# Proposal: Consolidación de Raíz del Monorepo en `actors/` y `src/`

## Tier de Complejidad
- **Tier Asignado:** Tier L (Arquitectónico).
- **Justificación YAGNI:** El cambio reestructura la topología raíz del monorepo, agrupando 6 directorios de primer nivel (`actor/`, `trainer/`, `config/`, `etl/`, `eda/`, `mlops/`) en 2 dominios cohesivos (`actors/` y `src/`), eliminando el shim obsoleto `producto2/` y reubicando el notebook maestro en `notebooks/`. No se agregan nuevas dependencias ni se añaden capas intermedias innecesarias; responde directamente a la necesidad de orden estructural y contención de complejidad.

## Evidencia Empírica: Archivos Inspeccionados
La necesidad y viabilidad del cambio se fundamenta en la auditoría directa de:
1. `config/settings.py`: Resolución de rutas relativas con `BASE_DIR = Path(__file__).resolve().parent.parent` (requiere migrar a `.parents[2]`).
2. `actor/Dockerfile` y `trainer/Dockerfile`: Ambos contenedores Apify poseen anatomía idéntica (`COPY src/ ./src/`) y operan de forma autónoma con `WORKDIR /usr/src/app`.
3. `producto2/__init__.py`: Shim legado de 9 líneas que solo reexporta `mlops.inference`, consumido únicamente de forma residual por `mlops/train_models.py` y `tests/test_producto2.py`.
4. `pytest.ini`: Configuración actual de `pythonpath = dashboard .`, que debe extenderse con `src` para habilitar el estándar industrial `src-layout`.
5. `tests/test_end_to_end_notebook.py`: Aserciones directas que verifican `mlops/artifacts`, `actor/reference_geo` y la ruta del notebook maestro `pipeline_observatorio_caba.ipynb`.

## Why
Actualmente la raíz del monorepo presenta una dispersión de 14 directorios visibles más notebooks y shims legados sueltos, dificultando la navegación, el mantenimiento y la separación de responsabilidades. Consolidar los contenedores serverless en `actors/` y la lógica de procesamiento analítico/ML en `src/` reduce la superficie de la raíz a 9 carpetas esenciales, alineando el proyecto con los estándares canónicos de arquitectura limpia en Python sin romper los contratos de ejecución en la nube.

## What Changes
- **MODIFICACIÓN**: Agrupar los contenedores de Apify bajo `actors/`:
  - `actor/` -> `actors/inference/`
  - `trainer/` -> `actors/trainer/`
- **MODIFICACIÓN**: Consolidar el núcleo analítico y de datos bajo `src/`:
  - `config/` -> `src/config/`
  - `etl/` -> `src/etl/`
  - `eda/` -> `src/eda/`
  - `mlops/` -> `src/mlops/`
- **REMOVAL (BREAKING interno)**: Eliminar el directorio `producto2/` y actualizar los imports residuales en `src/mlops/train_models.py` y renombrar `tests/test_producto2.py` a `tests/test_inference_scoring.py`.
- **MODIFICACIÓN**: Mover `pipeline_observatorio_caba.ipynb` a `notebooks/pipeline_observatorio_caba.ipynb` para erradicar archivos de código sueltos en la raíz.
- **MODIFICACIÓN**: Ajustar `pytest.ini` para incluir `src` en el `pythonpath` (`pythonpath = src dashboard .`).
- **MODIFICACIÓN**: Ajustar `src/config/settings.py` fijando `BASE_DIR = Path(__file__).resolve().parents[2]` para asegurar la resolución determinista de rutas absolutas.
- **MODIFICACIÓN**: Actualizar rutas y aserciones en `tests/test_apify_actor.py`, `tests/test_trainer_actor.py`, `tests/test_geo_cache.py`, `tests/test_end_to_end_notebook.py` y `scripts/prepare_geo_cache.py`.

## Capabilities

### Modified Capabilities
- `monorepo-structure`: Actualización de la especificación de topología de directorios, estableciendo `actors/` y `src/` como directorios canónicos, retiro de `producto2/` y relocalización de notebooks en `notebooks/`.

## Assumptions Eradication (Hechos Comprobados)
1. **Docker Workdir Independence**: Se comprobó que `actor/Dockerfile` y `trainer/Dockerfile` copian `./src/` relativo a su contexto de construcción; moverlos a `actors/inference` y `actors/trainer` no altera su ejecución en Apify siempre que el contexto de build sea la subcarpeta.
2. **Streamlit Isolation**: Se comprobó que `dashboard/` opera de manera 100% autónoma consumiendo datos de Google Drive, por lo que mover carpetas del backend no altera el despliegue en Streamlit Cloud.
3. **Green Baseline Suite**: Se ejecutó `pytest` sobre el monorepo previo al cambio, obteniendo 68 tests aprobados, 2 omitidos y 0 fallos en 5.15s.

## Non-Goals
- **Actualización de `README.md`**: Excluida explícitamente del alcance por instrucción directa del usuario; el usuario actualizará la documentación maestra posteriormente.
- **Modificación de lógica matemática o hiperparámetros**: No se alteran algoritmos de K-Means, XGBoost ni umbrales de negocio.
- **Modificación de flujos n8n**: Los flujos en `workflows/n8n/` continúan operando contra los endpoints configurados en Apify y Google Drive.

## Impact
- **Rendimiento:** Nulo en runtime; acelera el autocompletado y reduce la sobrecarga cognitiva del desarrollador y agentes.
- **Contratos Públicos:** Ningún contrato público de la API de Apify ni de Google Drive es alterado.
- **Compatibilidad hacia atrás:** La inclusión de `src` en `pytest.ini` garantiza que los imports `from config import settings`, `from etl import ...`, `from eda import ...` y `from mlops import ...` continúen resolviéndose de manera transparente durante la ejecución de tests y scripts.
