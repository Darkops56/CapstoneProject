# Design: Resiliencia del Pipeline Anual, Retención Dual y Desacoplamiento MLOps

## Context
Ver `proposal.md` y `specs/annual-pipeline-mlops/spec.md`.  
El ecosistema de Machine Learning de Zonaprop desacopla el ciclo mensual de inferencia del ciclo anual de reentrenamiento.  
Sin embargo, el workflow anual de n8n carecía de conexión al Actor Trainer y dependía de la disponibilidad de la API CKAN del GCBA. Además, la purga de Google Drive a los 3 meses en `01_mensual_enriquecido/` destruía los datos necesarios para el reentrenamiento de 12 meses.  
Este diseño establece una arquitectura resiliente con fallback, doble carpeta de retención y desacoplamiento entre el curado geoespacial y la inferencia de modelos.

---

## Goals / Non-Goals

### Goals
- Conectar en `workflows/n8n/workflow_anual_auditoria_gcba.json` el nodo de invocación al Actor Trainer en Apify con fallback ante caídas de GCBA.
- Implementar la arquitectura de retención dual en Drive: buffer mensual (90 días) vs. acumulador anual inmutable deduplicado (`04_historico_alquileres_anual`).
- Garantizar que el reentrenamiento anual sea incondicional cada 1 de marzo para compensar el drift inflacionario.
- Proveer desacoplamiento de inferencia para cargar modelos dinámicamente desde el manifest de Drive sin redesplegar contenedores.

### Non-Goals
- No se modifican los contratos de datos de salida consumidos por el Dashboard de Streamlit.
- No se reemplaza el almacenamiento de Google Drive ni el runtime serverless de Apify.

---

## Decisions

### Decisión 1: Pipeline Anual Secuencial Convergente con Degradación Elegante
* **Elección**: El cron del 1 de marzo ejecuta la auditoría de GCBA con `Continue on Fail: True` (timeout 30s) y converge incondicionalmente en la ejecución del Actor Trainer.
* **Alternativa descartada**: Disparo condicional estricto. *Razón de descarte*: Si GCBA demora la publicación del dataset de delitos, los modelos de precios no se reentrenarían, quedando expuestos a un severo desajuste inflacionario.

### Decisión 2: Separación de Buffer Operativo e Histórico Anual Deduplicado
* **Elección**: Separar `01_mensual_enriquecido/` (retención de 3 meses para el dashboard) de `04_historico_alquileres_anual/` (acumulador anual inmutable). En el acumulador anual se aplica deduplicación por clave natural `(calle_normalizada, m2_cubiertos, ambientes)` conservando la última observación.
* **Alternativa descartada**: Aumentar la retención de `01_mensual_enriquecido/` a 12 meses. *Razón de descarte*: Sobrecargaría el cargador de datos del Dashboard de Streamlit con miles de filas obsoletas y duplicadas.

### Decisión 3: Carga Dinámica de Modelos desde Manifest de Drive
* **Elección**: El actor de inferencia consulta el puntero `production_version` en `03_model_registry/models_manifest.json` y carga los artefactos correspondientes desde Drive (con fallback local a `actor/artifacts/`).
* **Alternativa descartada**: Hardcodear los `.joblib` en la imagen Docker del actor. *Razón de descarte*: Obligaría a un `apify push` manual de 500 MB tras cada reentrenamiento anual.

---

## Protocolo Grill Me Exhaustivo: Puntos de Ruptura y Vectores de Falla

| ID | Vector de Falla Crítica | Causa Raíz / Frontera | Discriminador Causal 1:1 (`{tipo, razon}`) | Mitigación y Recuperación Determinista |
| :--- | :--- | :--- | :--- | :--- |
| **BR-1** | **Caída o Timeout en API CKAN GCBA** | El servidor de datos abiertos de GCBA responde 500/504 o tarda > 30s. | `{tipo: NET_ERR, razon: CKAN_API_GATEWAY_TIMEOUT}` | En n8n, `Continue on Fail: True` + Timeout 30s. Emite `WARN_GCBA_UNAVAILABLE` y prosigue al Trainer con el árbol vigente. |
| **BR-2** | **Drift de Schema / Coordenadas en Delitos** | GCBA publica coordenadas en Gauss-Krüger o renombra columnas a `latitud`. | `{tipo: DATA_ERR, razon: URBAN_COORDINATES_OUT_OF_BOUNDS}` | Schema Guard: valida que `lat` $\in [-34.705, -34.525]$ y `lon` $\in [-58.535, -58.345]$. Si falla, aborta con `ERR_SCHEMA_DRIFT` y conserva el árbol anterior. |
| **BR-3** | **Sesgo por Duplicados Estacionales** | Departamentos no alquilados se acumulan 12 veces en el histórico anual. | `{tipo: ML_ERR, razon: OVERFITTING_STAGNANT_LISTINGS}` | Deduplicación por clave natural `(calle_normalizada, m2_cubiertos, ambientes)` conservando la última fila observada en el año. |
| **BR-4** | **Socket Timeout en n8n (> 360s)** | Cálculo de SHAP beeswarm o matrices de covarianza excede 6 minutos en CPU. | `{tipo: NET_ERR, razon: N8N_SYNC_SOCKET_TIMEOUT}` | Limitar el background sample de SHAP a $N=100$ instancias en el Trainer para garantizar runtime $< 90$ segundos. |
| **BR-5** | **Bump Duplicado por Reintentos (Idempotencia)** | Múltiples clicks o reintentos de n8n intentan generar versiones consecutivas idénticas. | `{tipo: REG_ERR, razon: DUPLICATE_VERSION_BUMP}` | Computar hash SHA-256 del dataset de entrenamiento; si coincide con la versión activa, emitir `SKIP_IDENTICAL_DATASET`. |
| **BR-6** | **Inconsistencia de Red al Subir a Drive** | Falla de conexión a mitad de subida de los 3 archivos `.joblib`. | `{tipo: IO_ERR, razon: PARTIAL_VERSION_CORRUPTION}` | Subida atómica en staging: subir a `staging_v(N+1)/`, verificar checksums de los 3 binarios y renombrar atómicamente antes de actualizar el manifiesto. |
| **BR-7** | **Regresión de Métricas en Producción** | El nuevo modelo obtiene $R^2 = 0.76 < 0.80$ y rompe producción. | `{tipo: ML_ERR, razon: METRIC_REGRESSION_R2_DROP}` | Trainer emite `ERR_METRIC_REGRESSION`. El puntero `production_version` en `models_manifest.json` no se modifica y la inferencia mensual continúa con la versión previa. |
| **BR-8** | **Volumen Insuficiente de Entrenamiento** | El histórico anual acumulado tiene menos de 500 filas deduplicadas. | `{tipo: DATA_ERR, razon: INSUFFICIENT_TRAINING_VOLUME}` | Validador `len(df) >= 500`; de lo contrario, cancela con `ERR_INSUFFICIENT_DATA` y previene el overfitting. |

---

## Architecture & Data Flow

```
                                  [Cron Anual: 1 de Marzo]
                                             │
                        ┌────────────────────┴────────────────────┐
                        ▼                                         ▼
            [CKAN API GCBA: Delitos]                    [Log: Inicio Reentreno]
                        │                                         │
                 ¿Responde < 30s?                                 │
                   /         \                                    │
                 SÍ           NO ──────────────────┐              │
                 │                                 │              │
           ¿Hay Novedad?                           ▼              │
             /       \                     [WARN_GCBA_OFFLINE]    │
           SÍ         NO                           │              │
           │           │                           │              │
     [Descargar]  [SKIP_UPDATE]                    │              │
           │           │                           │              │
     [Drive Raw]       └───────────────────────────┼──────────────┘
           │                                       │
     [Schema Guard]                                │
           │                                       │
     [Update Tree]                                 │
           │                                       │
           └───────────────────┬───────────────────┘
                               ▼
               [Verificar 04_historico_anual]
                               │
               [Apify: Actor Trainer (waitForFinish=360)]
                               │
                      ¿R² >= 0.80 y SHA Distinto?
                        /               \
                      SÍ                 NO
                      │                   │
             [Staging en Drive]     [ERR_REGRESSION o SKIP_IDEMPOTENT]
                      │                   │
             [Mover a v(N+1)]             └─> Producción Intacta
                      │
             [Update Manifest]
```

---

## Risks / Trade-offs

* **[Riesgo]**: Si la deduplicación por clave natural colisiona entre dos departamentos distintos en el mismo edificio con los mismos m² y ambientes.  
  *Mitigación*: Incluir el precio en la clave secundaria o conservar la última fecha de publicación como discriminador temporal explícito.
* **[Trade-off]**: Mantener dos carpetas en Google Drive consume una pequeña cuota adicional de almacenamiento.  
  *Justificación*: Para archivos CSV de 5.000 filas, 12 meses representan menos de 10 MB, haciendo el costo de almacenamiento virtualmente despreciable comparado con el valor de la estabilidad del modelo.

---

## Migration Plan

1. **Workflows en n8n**: Modificar `workflow_anual_auditoria_gcba.json` y `Pipeline Completo Anual y Mensual.json` agregando el nodo de llamada a Apify Trainer con `Continue on Fail` en la rama de CKAN.
2. **Estructura de Drive**: Documentar e incorporar la carpeta `04_historico_alquileres_anual` en `docs/README_DEPLOYMENT_N8N.md`.
3. **Tests Deterministas**: Extender `tests/test_n8n_workflows.py` con aserciones semánticas para los tokens `WARN_GCBA_UNAVAILABLE`, `waitForFinish=360` y la compuerta de convergencia.
