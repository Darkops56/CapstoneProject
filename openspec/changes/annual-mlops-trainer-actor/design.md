# Design: Actor de Entrenamiento Anual en Apify y Model Registry en Drive

## Context
Ver `proposal.md` y `specs/mlops-annual-training/spec.md`.  
El reentrenamiento del modelo de Machine Learning (XGBoost y KMeans) ocurre con una frecuencia anual (cada 1 año).  
Para evitar montar infraestructura de servidores HTTP permanente (que generaría costos mensuales y problemas de timeout), se implementa un **Actor dedicado en Apify** (`trainer/`) que corre bajo demanda durante 3 a 5 minutos, sube los binarios versionados (`v1`, `v2`...) a Google Drive en la carpeta `03_model_registry/`, y se apaga de forma serverless.  
Adicionalmente, se integra en el workflow mensual de n8n la política de retención para conservar únicamente los 3 datasets más recientes en `01_mensual_enriquecido/`.

---

## Goals / Non-Goals

### Goals
- Implementar el versionador incremental de modelos en `mlops/registry.json`.
- Crear el contenedor serverless de entrenamiento en `trainer/` con integración a Google Drive `03_model_registry/`.
- Mantener el actor mensual (`actor/`) ligero, autónomo y sin dependencias de reentrenamiento.
- Implementar la purga automática de datasets de más de 3 meses en n8n.
- Cero regresión en los tests del proyecto.

### Non-Goals
- No se levantará una API web permanente (FastAPI/Flask) para entrenamiento.
- No se reentrenará en el ciclo mensual; el ciclo mensual es estrictamente de inferencia.

---

## Decisions

### Decisión 1: Actor Serverless en Apify vs. Servidor HTTP 24/7
* **Elección**: Usar un Actor de Apify para el reentrenamiento anual.
* **Razón**: Corre bajo demanda por minutos, cuesta centavos de dólar al año y se integra nativamente con las credenciales de Apify ya configuradas en n8n.

### Decisión 2: Separación Estricta entre Actor Mensual y Actor Trainer
* **Elección**: Mantener dos actores separados: `actor/` (Inferencia mensual liviana) y `trainer/` (Entrenamiento anual con `shap` y `xgboost`).
* **Razón**: Evita que el contenedor de inferencia mensual arrastre 500 MB adicionales de librerías y sufra cold starts lentos.

### Decisión 3: Estructura de `03_model_registry` en Google Drive
* **Elección**: Carpeta raíz `03_model_registry` conteniendo `models_manifest.json` y subcarpetas versionadas `v1/`, `v2/`, etc.
* **Razón**: Preserva la convención numérica ordenada de Drive (`01_mensual_enriquecido`, `02_anual_gcba_raw`, `03_model_registry`).

---

## Protocolo Grill Me Exhaustivo: 10 Escenarios de Falla Crítica

| ID | Vector de Falla Crítica | Causa Raíz / Frontera | Discriminador Causal 1:1 (`{tipo, razon}`) | Mitigación y Recuperación Determinista |
| :--- | :--- | :--- | :--- | :--- |
| **V1** | **OOM Kill en Apify durante entrenamiento** | El cálculo de SHAP beeswarm o matrices XGBoost excede la RAM del contenedor. | `{tipo: MEM_ERR, razon: SHAP_TREE_EXPLODER_OOM}` | Configurar memoria mínima de 1024MB/2048MB en Apify y limitar el background sample de SHAP a 100 instancias. |
| **V2** | **Regresión de Precisión en Nuevo Modelo** | Datos atípicos del nuevo año causan que el $R^2$ caiga por debajo de 0.80. | `{tipo: ML_ERR, razon: METRIC_DEGRADATION_R2_DROP}` | El script evalúa métricas antes de guardar: si $R^2 < 0.80$, emite `ERR_METRIC_REGRESSION` y aborta sin pisar producción. |
| **V3** | **Fallo de Autenticación con Google Drive** | Credenciales de Service Account inválidas o carpeta inexistente. | `{tipo: AUTH_ERR, razon: GDRIVE_AUTH_FAILURE}` | Valida conectividad con `03_model_registry` antes de iniciar el cómputo pesado de entrenamiento. |
| **V4** | **Timeout de Ejecución en n8n** | n8n corta la conexión esperando que el actor termine. | `{tipo: NET_ERR, razon: HTTP_WAIT_TIMEOUT}` | Configurar `waitForFinish=360` (6 minutos) en el nodo n8n o invocar de forma asíncrona. |
| **V5** | **Purga Accidental de Todos los Datasets en Drive** | Error en el código de retención de n8n borra el dataset actual. | `{tipo: DATA_LOSS, razon: SLICE_OFF_BY_ONE}` | El nodo de retención exige explícitamente `files.length > KEEP_N` antes de enviar IDs a la papelera. |
| **V6** | **Colisión de Versiones de Modelos** | Se intenta sobrescribir una carpeta `v1/` existente con nuevos pesos. | `{tipo: REG_ERR, razon: IMMUTABLE_VERSION_OVERWRITE}` | Las versiones son inmutables: `bump_version` autoincrementa siempre a $N+1$ consultando el manifiesto. |
| **V7** | **Incompatibilidad de Pickling entre Versiones** | Diferencias de versión de Scikit-Learn entre el trainer y el actor de inferencia. | `{tipo: PKL_ERR, razon: SKLEARN_UNPICKLE_MISMATCH}` | Ambos actores (`actor/` y `trainer/`) comparten la misma versión base de Python 3.11 y `scikit-learn==1.3.2`. |
| **V8** | **Falta de Datos para Reentrenamiento** | La carpeta histórica tiene menos de 500 registros. | `{tipo: DATA_ERR, razon: INSUFFICIENT_TRAINING_VOLUME}` | Valida `len(df) >= 500` antes de entrenar; de lo contrario cancela con `ERR_INSUFFICIENT_DATA`. |
| **V9** | **Bloqueo por Cuota de Créditos en Apify** | La cuenta se queda sin créditos a fin de año. | `{tipo: QUOTA_ERR, razon: APIFY_CREDIT_EXHAUSTION}` | El script de entrenamiento puede ejecutarse alternativamente en local vía CLI: `python mlops/train_models.py --bump`. |
| **V10** | **Corrupción de Archivo `models_manifest.json`** | Escritura interrumpida a mitad del proceso. | `{tipo: IO_ERR, razon: ATOMIC_WRITE_FAILURE}` | Escritura atómica: se genera localmente el JSON completo y se sube en un único request de reemplazo. |

---

## Risks / Trade-offs

* **Riesgo**: Apify podría tardar más de 5 minutos si el volumen de datos crece a 50.000 filas.  
  *Mitigación*: Para el volumen esperado de CABA (1.000 a 3.000 filas anuales), el tiempo de cómputo en CPU es inferior a 120 segundos.

---

## Migration Plan

1. **MLOps Registry**: Implementar `mlops/registry.py` con autoincremento de versión y registro de métricas.
2. **Actor Trainer**: Crear el directorio `trainer/` con Dockerfile, entrypoint y lógica de subida a Drive.
3. **Flujo n8n**: Modificar `workflow_mensual_zonaprop_inferencia.json` incorporando los nodos de retención (últimos 3 meses).
4. **Verificación**: Test unitario para el registry y prueba de compilación del arnés.
