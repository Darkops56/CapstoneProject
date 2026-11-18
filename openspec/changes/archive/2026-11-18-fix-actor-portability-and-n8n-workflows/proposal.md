# Proposal: Fix Actor Portability & n8n Workflows Semantic Invariants

## Tier de Complejidad y Gobernanza YAGNI
- **Tier Asignado:** **Tier M (Medio)**
- **Justificación YAGNI:** El cambio corrige defectos críticos de integración y frontera hermética descubiertos durante la auditoría post-mortem: desacoplamiento de dependencias externas en el Actor Docker (`etl/` y `producto2/`), corrección de la cadencia anual del cron en n8n, compuerta condicional de idempotencia anual, dimensionamiento de timeouts asíncronos (`waitForFinish=300`) y transporte de datos binarios a Google Drive. No se añaden nuevas bibliotecas ni se altera la lógica matemática del modelo.

## Archivos Inspeccionados del Repositorio
- `actor/src/pipeline.py`: Importaciones no herméticas hacia `etl.etl_pipeline` y `producto2.inference`.
- `actor/src/main.py`: Detección ambigua del modo nube frente a ejecuciones CLI locales.
- `actor/Dockerfile`: Contexto de construcción aislado sin acceso a la raíz del monorepo.
- `workflows/n8n/workflow_mensual_zonaprop_inferencia.json`: Timeout de 120s en scraper y falta de flags binarias en Drive.
- `workflows/n8n/workflow_anual_auditoria_gcba.json`: Parámetro `"field": "months"` (mensual en vez de anual) y descarga incondicional sin evaluar `metadata_modified`.
- `openspec/specs/apify-inference-pipeline/spec.md`: Especificación viva existente a ser refinada.

## Why
La implementación inicial del Actor y de los flujos de n8n presentaba dos vulnerabilidades críticas que impedirían su funcionamiento en la nube:
1. El Actor en Docker crashearía con `ModuleNotFoundError` en Apify porque importaba módulos fuera de su contexto de construcción (`actor/`).
2. El workflow anual de n8n se ejecutaría 12 veces al año (mensual) en lugar de 1 vez al año, sobreescribiendo datos en Google Drive con archivos potencialmente vacíos debido a la falta de mapeo binario.

## What Changes
- **Hermeticidad del Actor (`actor/src/`):**
  - Creación de `actor/src/nlp_parser.py`: Embebe las funciones de limpieza tabular, NLP regex (expensas, mascotas) y extracción de amenities de forma autónoma.
  - Creación de `actor/src/scoring.py`: Embebe la fórmula del score de decisión (0-100) y clasificación de recomendaciones corporativas.
  - Refactorización de `actor/src/pipeline.py` para consumir exclusivamente módulos locales de `actor/src/`, eliminando toda dependencia hacia `etl/` y `producto2/`.
  - Refinamiento de `actor/src/main.py`: Solo activa el runtime de Apify si `APIFY_IS_AT_HOME` está presente o ante flags explícitas.
- **Corrección Semántica del Workflow Mensual (`workflows/n8n/workflow_mensual_zonaprop_inferencia.json`):**
  - Ajuste del trigger a expresión cron explícita `"0 3 1 * *"`.
  - Incremento de timeout en la llamada al scraper a `waitForFinish=300` y validación defensiva de `status === "SUCCEEDED"` para erradicar falsos positivos del Circuit Breaker.
  - Adición del parámetro `&clean=true` en la descarga del CSV desde Apify.
  - Inclusión de `"binaryData": true` en el nodo de Google Drive.
- **Corrección Semántica del Workflow Anual (`workflows/n8n/workflow_anual_auditoria_gcba.json`):**
  - Corrección de la frecuencia a expresión cron anual `"0 4 1 3 *"` (1 de Marzo a las 04:00 AM).
  - Incorporación de compuerta condicional `IF` que compara `metadata_modified` con el registro previo en `$getWorkflowStaticData()`, deteniendo la ejecución si el GCBA no publicó novedades.
  - Inclusión de `"binaryData": true` en el nodo de Google Drive.

## Capabilities

### New Capabilities
*(Ninguna).*

### Modified Capabilities
- `apify-inference-pipeline`: Se actualizan los requerimientos para exigir hermeticidad de frontera en el contenedor y la semántica corregida de los crons, timeouts y transporte binario en n8n.

## Impact
- **Contratos Públicos y Dockerfile:** El Actor pasa a ser un artefacto 100% autocontenido y portable, ejecutable tanto con `docker build` en Apify como vía CLI local.
- **Compatibilidad hacia atrás:** 100% compatible. Las salidas de datos, esquemas de CSV y predicciones se mantienen idénticos.
- **Rendimiento:** Se evitan descargas anuales redundantes y se previene el bloqueo prematuro del Circuit Breaker en ejecuciones mensuales reales.

## Non-Goals
- Alterar la lógica matemática del modelo de precios XGBoost o K-Means.
- Cambiar de proveedor de almacenamiento en la nube (se mantiene Google Drive).
- Implementar interfaz de usuario (se mantiene en una rama posterior).

## Assumptions Eradication
- **Supuesto 1:** ¿El comando `python3 -m json.tool` garantiza que un workflow de n8n esté bien configurado?
  - *Hecho comprobado:* Falso. Solo valida sintaxis textual; la semántica de nodos y parámetros de n8n requiere aserciones deterministas de sus propiedades.
- **Supuesto 2:** ¿Los tests unitarios locales demuestran que un Dockerfile compilará sin errores de import?
  - *Hecho comprobado:* Falso. Si los tests corren desde la raíz del monorepo, Python enmascara las rutas relativas. Se requiere probar el aislamiento hermético (`PYTHONPATH=""`).
