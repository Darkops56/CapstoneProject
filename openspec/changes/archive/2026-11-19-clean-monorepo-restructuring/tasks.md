# Tasks: Saneamiento y Reestructuración Limpia del Monorepo

## 1. Consolidación de Documentación en `docs/`

- [x] 1.1 Crear las subcarpetas `docs/architecture/` y `docs/evidence/` y mover los archivos explicativos de `explicacion/` hacia `docs/architecture/`, verificando con `ls docs/architecture/`.
- [x] 1.2 Mover `Feature.md` a `docs/feature_selection.md` y `PreguntasNegocio.txt` a `docs/business_questions.md`, verificando existencia con `ls docs/`.
- [x] 1.3 Mover `evidence.md` a `docs/evidence/evidence_consolidation.md` y eliminar el directorio obsoleto `explicacion/`.

## 2. Saneamiento de Seguridad y Scripts

- [x] 2.1 Mover `ObtenerJsonApify.py` a `scripts/fetch_apify_raw.py` y reemplazar el token hardcodeado por `os.environ.get("APIFY_TOKEN")`.
- [x] 2.2 Verificar mediante grep que no queden tokens en texto plano (`apify_api_`) en la raíz del repositorio.

## 3. Reubicación de Fixtures y Limpieza de Datos

- [x] 3.1 Mover `data/curated_sample_output.csv` y `data/sample_raw_listings.json` a `tests/fixtures/`.
- [x] 3.2 Actualizar las referencias de fixtures en `tests/` y `config/settings.py` y remover el directorio `data/` de la raíz.
- [x] 3.3 Remover `.matplotlib_cache/` del disco de trabajo.

## 4. Estandarización de Módulos (MLOps & ETL)

- [x] 4.1 Mover `producto1/` a `etl/output/` y `producto2/` a `mlops/`.
- [x] 4.2 Actualizar `config/settings.py` para resolver las nuevas rutas `mlops/` y `etl/output/` manteniendo aliases de compatibilidad retroactiva.
- [x] 4.3 Actualizar `README.md` maestro reflejando la nueva estructura limpia de directorios.

## 5. Verificación de Sistema (SVC) y Evidencia

- [x] 5.1 Ejecutar la suite completa de pruebas: `pytest -v` verificando que los 33 tests pasen al 100% (Exit Code 0).
- [x] 5.2 Verificar respuesta del dashboard con `streamlit run dashboard/app.py` en background (`curl -s -I http://localhost:8501`).
- [x] 5.3 Generar artefacto de evidencia `docs/evidence/evidence_clean_restructure.md` y commitear a `main`.
