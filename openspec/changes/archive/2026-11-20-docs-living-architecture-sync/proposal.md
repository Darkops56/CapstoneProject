# Proposal: Sincronización Integral de Documentación y Arquitectura Viva (Living Architecture)

## Tier de Complejidad
- **Tier Asignado:** Tier M (Medio).
- **Justificación YAGNI:** El cambio actualiza exhaustivamente la documentación técnica maestra (`README.md`, `docs/README_DEPLOYMENT_N8N.md`, `docs/architecture/00` a `04`, `docs/business_questions.md`, `docs/feature_selection.md`) y la especificación de inferencia `openspec/specs/apify-inference-pipeline/spec.md` para reflejar con 100% de fidelidad la topología real (`actors/`, `src/`, `notebooks/`), las suites de prueba (70 tests) y los flujos orquestados en n8n y Apify. No agrega código nuevo ni dependencias; elimina divergencias y evita la sobre-ingeniería preservando la estructura limpia del monorepo.

## Evidencia Empírica: Archivos Inspeccionados
1. `README.md`: Muestra rutas obsoletas (`actor/`, `trainer/`, `mlops/`, etc.), no documenta `actors/` ni `src/`, no enlaza a `docs/README_DASHBOARD_CONFIG.md` y no refleja el ciclo anual serverless ni los nuevos notebooks.
2. `docs/README_DEPLOYMENT_N8N.md`: Conserva instrucciones desactualizadas (`cd actor`, `cd trainer`) y no documenta la totalidad de los 31 nodos del pipeline unificado ni el flujo hacia Apify Key-Value Store de producción.
3. `docs/architecture/00_INDICE_Y_ARQUITECTURA.md`: Cita `producto1/` y `producto2/`, 11 tests (cuando existen 70) y omite los nuevos componentes de `actors/`, `src/`, `notebooks/` y `dashboard/`.
4. `docs/architecture/01_ETL_Y_CURACION_DE_DATOS.md` y `02_EDA_ESTADISTICO_Y_SELECCION_FEATURES.md`: Rutas y contexto legacy desalineados de `src/etl/` y `src/eda/`.
5. `docs/architecture/03_MODELADO_KMEANS_XGBOOST_Y_SHAP.md`: No documenta el Model Registry (`src/mlops/registry.py`), la salvaguarda de regresión ni la discrepancia entre $R^2 = 0.7775$ de baseline `v1` y el umbral $R^2 \ge 0.80$ para reentrenamientos anuales.
6. `docs/architecture/04_SCORE_DECISION_INFERENCIA_Y_HANDOFF.md`: Hace referencia a un handoff hipotético obsoleto con "Make/n8n", en lugar del handoff productivo real implementado (`actors/inference/`, `actors/trainer/`, `n8n`, `dashboard/`).
7. `docs/business_questions.md` y `docs/feature_selection.md`: Duplicación innecesaria de las preguntas Q1-Q5 y falta de formato Markdown en `business_questions.md`.
8. `openspec/specs/apify-inference-pipeline/spec.md`: Referencias legacy a `actor/`, `producto2/` y rutas inexistentes.

## Why
Tras la consolidación del monorepo en `src/` y `actors/`, la adición del notebook maestro y la extensión del dashboard a 70 tests deterministas, los documentos maestros presentan asimetría y contradicciones severas con el código en producción. Es mandatorio actualizar la documentación técnica bajo la directiva de *Living Architecture*, asegurando que la documentación sea autoexplicativa, navegable, fidedigna y libre de duplicaciones.

## What Changes
- **MODIFICACIÓN (`README.md`)**:
  - Reestructuración completa con un índice visual y navegable de alto impacto.
  - Actualización del árbol de arquitectura reflejando `actors/`, `src/`, `dashboard/`, `notebooks/`, `scripts/`, `docs/`, `tests/` y `workflows/`.
  - Diagrama de ciclos de vida actualizado (Ciclo Mensual Inferencia vs. Ciclo Anual Reentrenamiento Serverless con KV Store).
  - Unificación de la guía de configuración del Dashboard enlazando a `docs/README_DASHBOARD_CONFIG.md` sin duplicar variables contradictorias.
  - Indicación precisa de comandos de ejecución local y comandos deterministas de prueba (`pytest`).
- **MODIFICACIÓN (`docs/README_DEPLOYMENT_N8N.md`)**:
  - Actualización de comandos Apify CLI a `actors/inference` y `actors/trainer`.
  - Documentación detallada de los 31 nodos del flujo unificado (auditoría CKAN de 4 datasets, retención dual, subida atómica a Drive y publicación al KV Store de producción).
  - Inclusión de advertencia operativa de importación limpia en n8n para prevenir nodos duplicados en el lienzo.
- **MODIFICACIÓN (`docs/architecture/00` a `04`)**:
  - Corrección de todas las rutas relativas apuntando a `src/config/`, `src/etl/`, `src/eda/` y `src/mlops/`.
  - Actualización de métricas de software reportando la suite de 70 tests automatizados.
  - Explicación explícita en `03_MODELADO` del baseline $R^2 = 0.7775$ de `v1` frente a la guarda de $R^2 \ge 0.80$ en el Model Registry.
  - Reescribir la sección 4 de `04_SCORE_DECISION_INFERENCIA_Y_HANDOFF.md` reflejando el handoff productivo real a Apify y Streamlit Cloud.
- **MODIFICACIÓN (`docs/business_questions.md` y `docs/feature_selection.md`)**:
  - Formato Markdown enriquecido en `docs/business_questions.md`.
  - Eliminación de la duplicación de las 5 preguntas en `docs/feature_selection.md`, dejando este último enfocado exclusivamente en la matriz de features, VIF y justificación técnica.
- **MODIFICACIÓN (`openspec/specs/apify-inference-pipeline/spec.md`)**:
  - Actualización de rutas legacy (`actor/` -> `actors/inference/`, etc.).

## Capabilities

### Modified Capabilities
- `apify-inference-pipeline`: Actualización del contrato de rutas del actor a `actors/inference/` y alineación de nombres de fixtures de prueba.

## Assumptions Eradication (Hechos Comprobados)
1. **Verificación de Tests**: La suite unificada cuenta exactamente con 70 pruebas (68 aprobadas, 2 omitidas condicionalmente por ausencia de `Datasets/` local), con código de salida 0.
2. **Topología Real**: `actors/inference/` y `actors/trainer/` son los directorios vigentes en git tras el commit `8563869`.
3. **Flujos n8n**: `workflows/n8n/Pipeline Completo Anual y Mensual.json` contiene exactamente 31 nodos operativos.

## Non-Goals
- No modificar código ejecutable en `src/`, `actors/`, `dashboard/` ni `notebooks/`.
- No alterar la suite de pruebas deterministas en `tests/`.
- No introducir nuevas herramientas o frameworks de documentación.

## Impact
- **Rendimiento:** Nulo en tiempo de ejecución.
- **Contratos Públicos:** Ningún contrato de API externa es modificado.
- **Mantenibilidad:** Erradica contradicciones entre código y documentación, garantizando una entrega ejecutiva y técnica impecable.
