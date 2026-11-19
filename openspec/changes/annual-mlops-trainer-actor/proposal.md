# Proposal: Actor de Entrenamiento Anual en Apify y Model Registry en Drive

## Tier de Complejidad
**Tier M (Componente MLOps / Serverless)**: Implementación de un flujo de reentrenamiento anual automatizado y bajo demanda utilizando un Actor dedicado en Apify, con versionado incremental (`v1`, `v2`, `v3`), exportación automática al Model Registry en Google Drive (`03_model_registry/`), y adición de la política de retención (últimos 3 meses) en n8n para `01_mensual_enriquecido/`.

## Why
El modelo de precios (XGBoost) y habitabilidad (K-Means) debe reentrenarse una vez al año para incorporar la dinámica inflacionaria y las actualizaciones oficiales de GCBA (`02_anual_gcba_raw`).
Sin embargo:
1. Montar un endpoint HTTP permanente (FastAPI) incurre en costos de servidor 24/7 y problemas de timeout para una tarea que corre 1 vez cada 365 días.
2. Incorporar librerías pesadas de entrenamiento (`shap`, `scikit-learn` completo) dentro del contenedor mensual de Apify aumentaría drásticamente el peso del contenedor y el tiempo de arranque en cada corrida mensual.
3. El almacenamiento en Google Drive carece actualmente de un registro estructurado de modelos (`03_model_registry/`) y acumula datasets mensuales sin política de retención automática.

La creación de un **Actor de Entrenamiento en Apify** (`trainer/`) permite una ejecución anual 100% serverless, desacoplada y a costo prácticamente cero, depositando los binarios versionados en Drive y actualizando el `models_manifest.json`.

## What Changes
- **Motor de Versionado e Histórico (`mlops/`)**:
  - Extender `mlops/train_models.py` con argumentos de control (`--bump`, `--version`, `--push-drive`).
  - Crear el manifiesto local `mlops/registry.json` con histórico de métricas ($R^2$, RMSE, fecha, features utilizadas).
  - Gestionar subcarpetas incrementales `mlops/artifacts/v1/`, `v2/`, etc.
- **Actor de Entrenamiento Serverless (`trainer/`)**:
  - Crear el directorio `trainer/` con su propio `Dockerfile`, `requirements.txt`, `actor.json` e input schema.
  - Implementar el pipeline de reentrenamiento que ingiere el histórico acumulado, entrena K-Means y XGBoost, valida que no haya regresión de métricas y exporta los artefactos `.joblib`.
  - Integrar la subida automática a Google Drive en `03_model_registry/v(N)/` y actualización del archivo `models_manifest.json`.
- **Política de Retención en n8n**:
  - Incorporar en `workflows/n8n/workflow_mensual_zonaprop_inferencia.json` los nodos de búsqueda y eliminación de archivos en Drive que excedan los últimos 3 meses en `01_mensual_enriquecido/`.

## Capabilities

### New Capabilities
- `mlops-annual-training`: Define el ciclo de vida del reentrenamiento anual serverless en Apify, la estructura de carpetas versionadas en `03_model_registry/` en Google Drive y la política de retención mensual en n8n.

### Modified Capabilities
*(Ninguna. El dashboard de Streamlit y el actor de inferencia mensual conservan sus contratos existentes).*

## Assumptions Eradication
- **Supuesto 1**: *Se necesita un servidor web (FastAPI/Flask) corriendo todo el año para exponer un endpoint de reentrenamiento.*  
  **Hecho comprobado**: Falso. Un Actor serverless en Apify ejecuta contenedores bajo demanda, corre durante 3-5 minutos una vez al año y se apaga automáticamente a costo casi nulo ($0.03 USD).
- **Supuesto 2**: *El actor de inferencia mensual debe contener las dependencias de reentrenamiento.*  
  **Hecho comprobado**: Falso. Separar el actor mensual (`actor/`, liviano) del actor de entrenamiento anual (`trainer/`, pesado con SHAP) preserva la velocidad de arranque y evita aumentos de memoria en el ciclo mensual.

## Non-Goals
- No se modificará la estructura de capas ni los componentes de UI del dashboard en Streamlit.
- No se alterarán los datasets oficiales en `02_anual_gcba_raw`.

## Impact
- **Nuevos componentes**: `trainer/` (Dockerfile, src, requirements), `mlops/registry.json`.
- **Compatibilidad**: 100% compatible con los tests existentes (33/33 tests pasando).
