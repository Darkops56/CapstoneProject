## Purpose
Provee el contrato de comportamiento del pipeline dual en Apify y n8n para la ingesta, validación de integridad (Circuit Breaker), enriquecimiento geoespacial, inferencia de precios justos con scoring corporativo y monitoreo anual de datos abiertos del GCBA.

## Visual Interaction Flow (Tier M)

```mermaid
sequenceDiagram
    autonumber
    participant n8n as n8n Orchestrator
    participant Scraper as Apify Zonaprop Scraper
    participant Actor as Apify Curator & Inference (actors/inference)
    participant GDrive as Google Drive
    participant GCBA as Buenos Aires Data CKAN API

    Note over n8n,GDrive: Cadencia Mensual (Alquileres CABA)
    n8n->>Scraper: Trigger Run (maxItems: 1000)
    Scraper-->>n8n: Return defaultDatasetId
    n8n->>n8n: Evaluate Circuit Breaker (items >= 500 & hash != prev)
    alt Validation Failed (Empty or Duplicate)
        n8n->>n8n: Abort & Log SKIP_NO_DIFF
    else Validation Succeeded
        n8n->>Actor: Run Actor (datasetId)
        Actor-->>n8n: Return Processed Dataset (CSV)
        n8n->>GDrive: Upload alquileres_caba_enriquecido_YYYY_MM.csv
    end

    Note over n8n,GCBA: Cadencia Anual (Auditoría GCBA)
    n8n->>GCBA: GET package_show?id=delitos (y otros 3 datasets)
    GCBA-->>n8n: Return metadata_modified & resources
    n8n->>GDrive: Store raw update if metadata is newer
```

## Requirements

### Requirement: Validación de Integridad y Circuit Breaker en n8n
El orquestador n8n SHALL verificar el volumen, estado de finalización exitosa (`SUCCEEDED`) y la novedad de los datos de Zonaprop antes de invocar la ejecución del Actor de Apify, configurando un timeout asíncrono no menor a 300 segundos.

#### Scenario: Scraper bloqueado o lote incompleto
- **WHEN** el scraper de Zonaprop finaliza con una cantidad de registros inferior al umbral mínimo de 500 o con estado distinto de `SUCCEEDED`
- **THEN** el flujo SHALL detener la ejecución, registrar el token canónico `ERR_SCRAPER_INCOMPLETE_BATCH` y omitir el llamado al Actor de Inferencia sin modificar archivos en Google Drive.

#### Scenario: Scraper devuelve lote idéntico al mes anterior
- **WHEN** el hash criptográfico SHA-256 de los `listingId` del lote actual coincide exactamente con el hash del mes previo
- **THEN** el flujo SHALL detener la ejecución, registrar el estado canónico `SKIP_IDENTICAL_DATASET` y preservar el dataset existente en Google Drive.

### Requirement: Enriquecimiento Geoespacial y Carga de Geo-Caché en el Actor
El Actor de Apify SHALL cruzar las coordenadas de las publicaciones con el caché de datos urbanos del GCBA embebido en el contenedor `actors/inference/reference_geo/` en formato comprimido sin realizar peticiones de red externas.

#### Scenario: Propiedad válida dentro de CABA
- **WHEN** se procesa un registro con coordenadas válidas dentro del polígono de CABA (`-34.70 <= lat <= -34.53` y `-58.54 <= lon <= -58.35`)
- **THEN** el Actor SHALL calcular exactamente las 4 métricas urbanas (`ruido_db_promedio`, `densidad_delitos_500m`, `distancia_escuela_m`, `lineas_subte_600m`) con valores numéricos no nulos.

#### Scenario: Coordenadas nulas o fuera de CABA
- **WHEN** un registro presenta coordenadas omitidas o fuera del bounding box oficial de CABA
- **THEN** el Actor SHALL imputar las métricas de entorno utilizando la mediana calculada del barrio reportado o el centroide de CABA, emitiendo el tag de auditoría `AUDIT_COORD_IMPUTED` sin interrumpir el proceso por excepción no controlada.

### Requirement: Inferencia y Asignación de Scores de Decisión
El Actor de Apify SHALL ejecutar los modelos K-Means y XGBoost cargados desde los artefactos `.joblib` y emitir el vector completo de 10 features junto a las predicciones y scores.

#### Scenario: Generación exitosa de predicciones y scores
- **WHEN** se evalúa un lote de hasta 1,000 propiedades curadas
- **THEN** cada registro de salida SHALL contener `precio_justo_ars` > 0.0, `desvio_precio_pct` numérico, `cluster_habitabilidad` en el rango discreto [1, 5], y `score_familia` y `score_soltero` estrictamente acotados en el intervalo `[0.0, 100.0]`.

### Requirement: Auditoría Anual de Datos Abiertos del GCBA
El orquestador n8n SHALL consultar anualmente (mediante cron canónico `0 4 1 3 *`) el catálogo CKAN de Buenos Aires Data para auditar la vigencia de los datasets de entorno urbano, evaluando la novedad antes de descargar.

#### Scenario: Detección de actualización en catálogo CKAN
- **WHEN** el endpoint de CKAN para `delitos` reporta un timestamp `metadata_modified` posterior al último procesado registrado
- **THEN** n8n SHALL descargar el recurso oficial a la carpeta `02_anual_gcba_raw/` de Google Drive con flag binaria habilitada y emitir el token `EVENT_GCBA_DATA_UPDATED`.

#### Scenario: Sin cambios en catálogo CKAN
- **WHEN** el timestamp `metadata_modified` coincide con el último registro procesado
- **THEN** n8n SHALL finalizar la ejecución anual registrando el token canónico `SKIP_NO_ANNUAL_UPDATE` sin descargar archivos repetidos.

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
