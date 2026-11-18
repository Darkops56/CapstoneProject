# Proposal: Apify Inference & n8n Dual-Cadence Pipeline

## Tier de Complejidad y Gobernanza YAGNI
- **Tier Asignado:** **Tier M (Medio)**
- **Justificación YAGNI:** El cambio empaqueta la lógica existente de ETL (`etl/etl_pipeline.py`) e inferencia (`producto2/inference.py`, `producto2/artifacts/`) en un contenedor ejecutable como Actor de Apify y define los flujos de orquestación en n8n con persistencia en Google Drive. No se reentrenan modelos ni se agregan capas intermedias, bases de datos complejas ni microservicios desacoplados.

## Archivos Inspeccionados del Repositorio
- `etl/etl_pipeline.py`: Funciones de limpieza, regex/NLP (expensas, mascotas), indexación espacial y cruce con datasets urbanos.
- `producto2/inference.py`: Rutinas de carga de artefactos (`load_artifacts`), predicción XGBoost y scoring de decisión para `FAMILIA` y `SOLTERO_EJECUTIVO`.
- `producto2/artifacts/`: Modelos entrenados (`kmeans_model.joblib`, `xgb_price_model.joblib`, `model_metadata.joblib`).
- `Datasets/Originales/` y `Datasets/Curados/`: Datasets urbanos del GCBA (ruido, delitos, subte, escuelas) y Zonaprop.
- `ObtenerJsonApify.py`: Script base de interacción con la API de Apify y el scraper `memo23~zonaprop-scraper`.

## Why
Actualmente, el proceso de scraping, curación, cruce geoespacial e inferencia de alquileres en CABA se ejecuta de forma manual o local mediante notebooks y scripts dispersos. Para llevar la solución a un entorno productivo y transportable para Recursos Humanos (Corporate Relocation), se requiere un pipeline automatizado en la nube con doble cadencia:
1. **Cadencia Mensual:** Extracción de lotes de Zonaprop, validación de integridad/cambios (Circuit Breaker), curación geoespacial, inferencia de precio justo y scoring corporativo, con persistencia final en Google Drive.
2. **Cadencia Anual:** Auditoría automatizada de los datasets de datos abiertos del GCBA (Buenos Aires Data CKAN API) y resguardo de nuevas versiones en Drive.

## What Changes
- **Nuevo Módulo Actor Apify (`actor/`):**
  - Contenedor Docker dual (CLI local y Apify Actor) que combina curación tabular, NLP y enriquecimiento geoespacial con el motor de inferencia `.joblib`.
  - Geo-Caché embebido y optimizado de los 4 datasets urbanos del GCBA (`reference_geo/`), eliminando la descarga mensual de 72 MB de ruido y delitos.
- **Workflow de Orquestación n8n (Mensual):**
  - Disparo programado el primer día de cada mes.
  - Ejecución del scraper de Zonaprop (`memo23~zonaprop-scraper`, POC limitado a 1,000 items).
  - Nodo Circuit Breaker & Hash Check: detiene la ejecución si el scrape devolvió menos de 500 registros o si el hash del lote es idéntico al mes anterior.
  - Ejecución del Actor de Apify y descarga del CSV enriquecido final.
  - Persistencia en Google Drive (`DataLake/Curated/alquileres_caba_YYYY_MM.csv`).
- **Workflow de Monitoreo n8n (Anual):**
  - Disparo programado anual (1 de Marzo).
  - Consulta a la API pública de CKAN de Buenos Aires Data (`data.buenosaires.gob.ar`).
  - Detección de nuevas versiones de Delitos o Escuelas y descarga automática a `DataLake/01_raw/gcba_anual/` en Google Drive con notificación de alerta.
- **Script de Preparación de Caché Geoespacial (`scripts/prepare_geo_cache.py`):**
  - Pre-procesa los archivos pesados de `Datasets/Curados/` generando artefactos comprimidos Parquet e índices espaciales para el build del Dockerfile.

## Capabilities

### New Capabilities
- `apify-inference-pipeline`: Define el contrato de entrada/salida, comportamiento ante fallos, ejecución dual (CLI/Apify), enriquecimiento geoespacial y cálculo de scores para el Actor de Apify y los workflows de n8n.

### Modified Capabilities
*(Ninguna. No existen especificaciones previas en `openspec/specs/` cuya semántica o requerimientos se vean modificados).*

## Impact
- **Contratos Públicos / Input Schema del Actor:**
  - Entrada: `{ "datasetId": string, "limit": integer (default: 1000) }`.
  - Salida: Dataset de Apify con las 10 features normalizadas, clúster de habitabilidad, precio justo estimado, desvío porcentual y scores de decisión (0–100) para `FAMILIA` y `SOLTERO_EJECUTIVO`.
- **Rendimiento y Recursos:**
  - Reducción drástica del I/O: el Actor procesa 1,000 registros en < 30 segundos con menos de 512 MB de RAM gracias al Geo-Caché Parquet.
  - Idempotencia: el Circuit Breaker de n8n evita gasto innecesario de créditos de Apify y escrituras duplicadas en Drive.
- **Dependencias:**
  - Se añade `apify` SDK en las dependencias del contenedor de inferencia. No se añaden dependencias externas a la raíz del repositorio salvo las herramientas de empaquetado.
- **Compatibilidad hacia atrás:**
  - 100% compatible. Las funciones existentes en `etl/` y `producto2/` se reutilizan sin romper contratos ni alterar los scripts locales.

## Non-Goals
- Desarrollar la interfaz web interactiva (Frontend de mapas y filtros); esto se abordará en una rama posterior consumiendo el CSV generado.
- Reentrenar dinámicamente los modelos XGBoost y K-Means en cada ejecución mensual.
- Reemplazar el scraper de Zonaprop de Apify por un desarrollo propio desde cero.
- Implementar una base de datos relacional (PostgreSQL/PostGIS) en la nube para el POC; se utiliza persistencia plana en Google Drive.

## Assumptions Eradication
- **Supuesto Evaluado 1:** ¿El cruce espacial debe correr en n8n?
  - *Hecho comprobado:* Falso. GeoPandas y SciPy en nodos Code de n8n provocarían fallas de memoria (OOM) y sobrecarga. Debe ejecutarse dentro del contenedor del Actor de Apify.
- **Supuesto Evaluado 2:** ¿Los datasets del GCBA deben descargarse de internet en cada corrida mensual?
  - *Hecho comprobado:* Falso. Los datos de ruido y delitos del GCBA son anuales o decenales. Pre-indexarlos en la imagen Docker ahorra transferencias de 72 MB y reduce el tiempo a segundos.
- **Supuesto Evaluado 3:** ¿Un scrape mensual siempre debe procesarse?
  - *Hecho comprobado:* Falso. Si el scraper fue bloqueado (< 500 items) o el lote es idéntico (hash duplicado), el Circuit Breaker en n8n previene procesar datos corruptos.
