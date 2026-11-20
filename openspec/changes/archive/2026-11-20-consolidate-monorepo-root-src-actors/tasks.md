## Fase 0: Preparación de Entorno y Configuración de Arnés

- [x] 0.1 Configurar `pytest.ini` agregando `src` al `pythonpath` (`pythonpath = src dashboard .`) y actualizar `.gitignore` con `**/etl/output/` y `src/etl/output/`. Validar con `python3 -m pytest --version` y `git check-ignore src/etl/output/dummy.csv`.
- [x] 0.2 Crear directorios canónicos destino `actors/` y `src/` asegurando paquetes Python con `__init__.py`. Validar con `python3 -c "import os; assert os.path.isdir('src') and os.path.isdir('actors')"`.

## Fase 1: Arnés de Pruebas y Validación Red Phase

- [x] 1.1 Actualizar rutas e imports en `tests/test_apify_actor.py`, `tests/test_trainer_actor.py` y `tests/test_geo_cache.py` apuntando a `actors.inference` y `actors.trainer`. Verificar Red Phase esperada con `pytest tests/test_geo_cache.py`.
- [x] 1.2 Actualizar aserciones de higiene y paths en `tests/test_end_to_end_notebook.py` apuntando a `src/mlops/artifacts`, `actors/inference/reference_geo` y `notebooks/pipeline_observatorio_caba.ipynb`. Verificar Red Phase con `pytest tests/test_end_to_end_notebook.py -k test_repo_hygiene`.
- [x] 1.3 Renombrar `tests/test_producto2.py` a `tests/test_inference_scoring.py` reemplazando los imports hacia `producto2` por `mlops.inference`. Verificar con `pytest tests/test_inference_scoring.py`.

## Fase 2: Migración del Core Backend a `src/`

- [x] 2.1 Migrar `config/`, `etl/`, `eda/` y `mlops/` hacia `src/` mediante `git mv`. Validar integridad con `git status --porcelain`.
- [x] 2.2 Corregir resolución de `BASE_DIR = Path(__file__).resolve().parents[2]` en `src/config/settings.py`. Validar con comando determinista `python3 -c "from config import settings; assert (settings.BASE_DIR / 'pytest.ini').exists(), 'BASE_DIR inválido'"`.
- [x] 2.3 Reemplazar `from producto2 import inference` por `from mlops import inference` en `src/mlops/train_models.py` y eliminar físicamente el directorio legado `producto2/`. Validar con `git status` comprobando ausencia de `producto2`.

## Fase 3: Migración de Actores Serverless y Notebooks

- [x] 3.1 Migrar `actor/` a `actors/inference/` y `trainer/` a `actors/trainer/` mediante `git mv`. Validar presencia de Dockerfiles con `ls actors/inference/Dockerfile actors/trainer/Dockerfile`.
- [x] 3.2 Actualizar `scripts/prepare_geo_cache.py` para escribir en `actors/inference/reference_geo`. Validar con `python3 -c "import scripts.prepare_geo_cache as p; assert 'actors' in str(p.OUTPUT_DIR)"`.
- [x] 3.3 Reubicar `pipeline_observatorio_caba.ipynb` en `notebooks/` mediante `git mv`. Validar que la raíz no contenga archivos `.ipynb` con `test ! -f pipeline_observatorio_caba.ipynb && test -f notebooks/pipeline_observatorio_caba.ipynb`.

## Fase 4: Verificación Integral Determinista (SVC Exit Code 0)

- [x] 4.1 Ejecutar prueba de aislamiento hermético de Apify: `pytest tests/test_apify_actor.py -k test_actor_hermetic_isolation` garantizando Exit Code 0.
- [x] 4.2 Ejecutar suite completa de regresión: `pytest` verificando que los 70 tests del arnés pasen con código de salida 0 (`Exit Code 0`).
- [x] 4.3 Generar reporte obligatorio `docs/evidence/evidence_monorepo_root_consolidation.md` documentando la salida de los tests y la auditoría final de directorios en la raíz.
