# Tasks: Actor de Entrenamiento Anual en Apify y Model Registry en Drive

## 1. MLOps Model Registry y Versionado

- [x] 1.1 Implementar `mlops/registry.py` con funciones para registrar nuevas versiones (`bump_version`), validar umbrales mínimos de métricas ($R^2 \ge 0.80$) y persistir `mlops/registry.json`.
- [x] 1.2 Adaptar `mlops/train_models.py` para soportar argumentos CLI (`--bump`, `--registry`) y exportar a `mlops/artifacts/v(N)/`.
- [x] 1.3 Crear suite de tests `tests/test_model_registry.py` verificando autoincremento de versiones y detección de regresión con `pytest tests/test_model_registry.py`.

## 2. Implementación del Actor de Entrenamiento en Apify (`trainer/`)

- [x] 2.1 Crear la estructura del actor `trainer/` con `Dockerfile` (Python 3.11, XGBoost, Scikit-Learn, Apify SDK) y `requirements.txt`.
- [x] 2.2 Crear el manifiesto `.actor/actor.json` e `input_schema.json` especificando parámetros (carpeta Drive, umbrales de métricas).
- [x] 2.3 Implementar `trainer/src/train_pipeline.py` y `trainer/src/main.py` con el pipeline completo de entrenamiento y evaluación.

## 3. Conector de Respaldo a Google Drive (`03_model_registry`)

- [x] 3.1 Implementar en `trainer/src/gdrive_exporter.py` la función para crear carpetas versionadas (`v1/`, `v2/`) en `03_model_registry/` y subir los artefactos `.joblib`.
- [x] 3.2 Implementar la creación y actualización atómica del archivo `models_manifest.json` en Drive con las métricas del modelo activo.

## 4. Política de Retención de Datasets en n8n

- [x] 4.1 Actualizar el JSON del workflow `workflows/n8n/workflow_mensual_zonaprop_inferencia.json` incorporando los nodos de listado, ordenamiento por fecha y purga a la papelera para mantener los últimos 3 meses en `01_mensual_enriquecido/`.
- [x] 4.2 Verificar sintaxis y estructura JSON del workflow actualizado con `python -m json.tool "workflows/n8n/workflow_mensual_zonaprop_inferencia.json" > /dev/null`.

## 5. Verificación de Sistema (SVC) y Evidencia

- [x] 5.1 Ejecutar la suite completa de pruebas del monorepo: `pytest -v` asegurando 100% de tests exitosos (Exit Code 0).
- [x] 5.2 Generar artefacto de evidencia `docs/evidence/evidence_annual_trainer_actor.md`.
- [x] 5.3 Commitear cambios a la rama `main` y sincronizar con `origin/main`.
