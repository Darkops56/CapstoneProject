# Delta Spec: apify-inference-pipeline

## Visual Interaction Flow (Tier M)

```mermaid
sequenceDiagram
    autonumber
    participant n8n as n8n Orchestrator
    participant Scraper as Apify Zonaprop Scraper
    participant Actor as Apify Ingest & Scoring (actors/inference)
    participant GDrive as Google Drive (01_mensual_enriquecido)
    participant GCBA as Buenos Aires Data CKAN API

    Note over n8n,GDrive: Cadencia Mensual (Alquileres CABA)
    n8n->>Scraper: Trigger Run (maxItems: 1000)
    Scraper-->>n8n: Return defaultDatasetId
    n8n->>n8n: Evaluate Circuit Breaker (items >= 500)
    alt Validation Failed
        n8n->>n8n: Abort & Log ERR_SCRAPER_INCOMPLETE_BATCH
    else Validation Succeeded
        n8n->>Actor: POST /runs (datasetId)
        Actor-->>n8n: Return Processed Dataset (CSV)
        n8n->>GDrive: Upload alquileres_caba_enriquecido_YYYY_MM.csv
    end

    Note over n8n,GCBA: Cadencia Anual (Auditoría GCBA - 4 Datasets)
    n8n->>GCBA: GET /package_show?id=delitos (etc.)
    GCBA-->>n8n: Return metadata_modified & resources
    n8n->>GDrive: Store raw update if metadata is newer
```

## MODIFIED Requirements

### Requirement: Enriquecimiento Geoespacial y Carga de Geo-Caché en el Actor
El Actor de Apify SHALL cruzar las coordenadas de las propiedades con el caché de datos urbanos del GCBA embebido en el contenedor `actors/inference/reference_geo/` en formato comprimido sin realizar peticiones de red externas.

#### Scenario: Propiedad válida dentro de CABA
- **WHEN** se procesa un registro con coordenadas válidas dentro del polígono de CABA (`-34.70 <= lat <= -34.53` y `-58.54 <= lon <= -58.35`)
- **THEN** el Actor SHALL calcular exactamente las 4 métricas urbanas (`ruido_db_promedio`, `densidad_delitos_500m`, `distancia_escuela_m`, `lineas_subte_600m`) con valores numéricos no nulos.

#### Scenario: Coordenadas nulas o fuera de CABA
- **WHEN** un registro presenta coordenadas omitidas o fuera del bounding box oficial de CABA
- **THEN** el Actor SHALL imputar las métricas de entorno utilizando la mediana calculada del barrio reportado o el centroide de CABA, emitiendo el tag de auditoría `AUDIT_COORD_IMPUTED` sin interrumpir el proceso por excepción no controlada.

### Requirement: Hermeticidad y Desacoplamiento del Actor en Docker
El Actor de Apify SHALL ser completamente autocontenido dentro de su directorio raíz `actors/inference/`, ejecutando curación, cruce geoespacial e inferencia sin importar módulos externos al contenedor.

#### Scenario: Ejecución en entorno limpio sin monorepo
- **WHEN** el Actor se ejecuta en un entorno donde las rutas de `src/` están ausentes del `sys.path`
- **THEN** el Actor SHALL procesar el lote sin arrojar `ModuleNotFoundError`, emitiendo las 10 features y scores con Exit Code 0.

## Test Plan & Resilience Strategy

1. **Harness de Ejecución Determinista (SVC):**
   - El contenedor del Actor expone una interfaz de línea de comando que ejecuta el pipeline sobre fixtures locales (`tests/fixtures/sample_zonaprop_raw.json`) finalizando con Exit Code 0.
   - Validación de salida con `pytest` sobre `tests/test_apify_actor.py` verificando ausencia total de `NaN` en las 10 features finales.
2. **Resiliencia de Memoria:**
   - La lectura de `medicion_ruido` se efectúa desde Parquet indexado, garantizando que el uso de RAM del contenedor se mantenga por debajo de 512 MB durante la ejecución de los 1,000 registros.
