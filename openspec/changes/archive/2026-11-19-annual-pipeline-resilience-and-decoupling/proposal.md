# Proposal: Resiliencia del Pipeline Anual, Retención Dual y Desacoplamiento MLOps

## Tier de Complejidad
**Tier M (Componente MLOps / Arquitectura Distribuida)**: Reestructuración del flujo anual de n8n para garantizar reentrenamiento incondicional contra el drift inflacionario, implementación de la política de retención dual en Google Drive (`01_mensual_enriquecido` vs. `04_historico_alquileres_anual`), mitigación de los 8 vectores de falla Grill-Me, y desacoplamiento de las etapas de curado e inferencia.

## Why
El análisis del repositorio evidenció tres vulnerabilidades críticas en el ciclo de vida del dato y de los modelos:
1. **Bloqueo por acoplamiento con GCBA**: En `workflows/n8n/workflow_anual_auditoria_gcba.json`, el flujo termina en la persistencia del raw de delitos y no dispara el reentrenamiento. Si el reentreno se condiciona a la publicación de datos de delitos de GCBA, la demora en su portal de datos abiertos congela los modelos en una escala de precios desactualizada, provocando severo *concept drift* por la inflación argentina.
2. **Paradoja de retención de datos**: La política de retención en n8n purga `01_mensual_enriquecido/` dejando solo 3 meses de historia. Al llegar el ciclo anual, el Actor Trainer carece del volumen y estacionalidad de 12 meses para reentrenar.
3. **Acoplamiento de Curado e Inferencia**: `actor/src/main.py` ejecuta consecutivamente el cruce espacial pesado y la inferencia con modelos congelados. Cuando se entrena una nueva versión de modelos, se requiere redesplegar (`apify push`) todo el contenedor con 100MB de geo-referencias, impidiendo re-scoring histórico sin re-procesamiento geoespacial.

## What Changes
- **Pipeline Anual Convergente en n8n (`workflows/n8n/`)**:
  - Unificar el flujo anual en un solo pipeline determinista donde la auditoría de CKAN GCBA precede al entrenamiento.
  - Implementar degradación elegante (`Continue on Fail` / Fallback) para que caídas o timeouts en la API de GCBA no impidan el reentrenamiento anual.
  - Conectar el nodo HTTP hacia Apify `mlops-annual-trainer` con `waitForFinish=360` y parámetros canónicos (`minR2Threshold: 0.80`, `minSamples: 500`).
- **Arquitectura de Retención Dual en Google Drive**:
  - Mantener `01_mensual_enriquecido/` como buffer operativo (últimos 3 meses) para optimizar el Dashboard de Streamlit.
  - Crear e integrar `04_historico_alquileres_anual/` como acumulador inmutable que persiste los 12 meses del ciclo anual para el Actor Trainer, con deduplicación por clave natural `(calle_normalizada, m2_cubiertos, ambientes)`.
- **Desacoplamiento Funcional de Curado e Inferencia**:
  - Parametrizar el Actor mensual (`actor/`) para admitir invocación por etapas (`--step=curate`, `--step=infer`, o `--step=all`) y carga dinámica de artefactos desde el manifiesto de Google Drive (`03_model_registry/models_manifest.json`), evitando redeploys completos ante cada versión de modelo.
- **Resguardo Urbano Completo**:
  - Documentar y respaldar en `02_anual_gcba_raw/` las 4 fuentes de contexto urbano de CABA (Delitos, Subtes, Escuelas, Ruido).

## Capabilities

### New Capabilities
- `annual-pipeline-resilience-and-decoupling`: Define el contrato del pipeline anual convergente con fallback ante fallos de GCBA, la política de almacenamiento dual (buffer vs. histórico anual deduplicado), la carga dinámica de modelos desde el registro de Drive y la suite de aserciones de resiliencia n8n.

### Modified Capabilities
*(Ninguna. El dashboard de Streamlit y los contratos de datos de salida conservan compatibilidad estricta hacia atrás).*

## Assumptions Eradication
- **Supuesto 1**: *El reentrenamiento anual solo debe ocurrir si GCBA publica nuevos delitos.*  
  **Hecho comprobado**: Falso. En CABA la dinámica inflacionaria en ARS requiere reajustar los pesos de precios anualmente de forma incondicional el 1 de marzo, con o sin actualización policial.
- **Supuesto 2**: *Los datasets mensuales en `01_mensual_enriquecido` son suficientes para el reentrenamiento.*  
  **Hecho comprobado**: Falso. La purga a 90 días destruye 9 meses de historial necesarios para el cómputo de métricas robustas ($N \ge 500$).
- **Supuesto 3**: *El actor de inferencia debe contener los modelos compilados dentro de su imagen Docker.*  
  **Hecho comprobado**: Falso. Desacoplar la carga de pesos desde Drive permite actualizar los modelos en producción sin recompilar ni redesplegar el contenedor de Apify.

## Non-Goals
- No se levantará una API permanente (FastAPI/Flask) para entrenamiento; se mantiene la arquitectura 100% serverless bajo demanda en Apify.
- No se modificará la interfaz de usuario ni las vistas de mapas en Streamlit (`dashboard/`).
- No se reentrenará en el ciclo mensual (el ciclo mensual permanece estrictamente para inferencia).

## Impact
- **Workflows**: Actualización de `workflows/n8n/workflow_anual_auditoria_gcba.json` y `Pipeline Completo Anual y Mensual.json`.
- **Almacenamiento**: Adición del ID de carpeta `04_historico_alquileres_anual` en las variables de configuración.
- **Testing**: Ampliación de `tests/test_n8n_workflows.py` con pruebas negativas y de resiliencia deterministas.
