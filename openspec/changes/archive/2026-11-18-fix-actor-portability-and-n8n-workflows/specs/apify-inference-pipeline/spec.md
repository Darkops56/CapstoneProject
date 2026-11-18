## MODIFIED Requirements

### Requirement: Validación de Integridad y Circuit Breaker en n8n
El orquestador n8n SHALL verificar el volumen, estado de finalización exitosa (`SUCCEEDED`) y la novedad de los datos de Zonaprop antes de invocar la ejecución del Actor de Apify, configurando un timeout asíncrono no menor a 300 segundos.

#### Scenario: Scraper bloqueado o lote incompleto
- **WHEN** el scraper de Zonaprop finaliza con una cantidad de registros inferior al umbral mínimo de 500 o con estado distinto de `SUCCEEDED`
- **THEN** el flujo SHALL detener la ejecución, registrar el token canónico `ERR_SCRAPER_INCOMPLETE_BATCH` y omitir el llamado al Actor de Inferencia sin modificar archivos en Google Drive.

#### Scenario: Scraper devuelve lote idéntico al mes anterior
- **WHEN** el hash criptográfico SHA-256 de los `listingId` del lote actual coincide exactamente con el hash del mes previo
- **THEN** el flujo SHALL detener la ejecución, registrar el estado canónico `SKIP_IDENTICAL_DATASET` y preservar el dataset existente en Google Drive.

### Requirement: Auditoría Anual de Datos Abiertos del GCBA
El orquestador n8n SHALL consultar anualmente (mediante cron canónico `0 4 1 3 *`) el catálogo CKAN de Buenos Aires Data para auditar la vigencia de los datasets de entorno urbano, evaluando la novedad antes de descargar.

#### Scenario: Detección de actualización en catálogo CKAN
- **WHEN** el endpoint de CKAN para `delitos` reporta un timestamp `metadata_modified` posterior al último procesado registrado
- **THEN** n8n SHALL descargar el recurso oficial a la carpeta `DataLake/01_raw/gcba_anual/` de Google Drive con flag binaria habilitada y emitir el token `EVENT_GCBA_DATA_UPDATED`.

#### Scenario: Sin cambios en catálogo CKAN
- **WHEN** el timestamp `metadata_modified` coincide con el último registro procesado
- **THEN** n8n SHALL finalizar la ejecución anual registrando el token canónico `SKIP_NO_ANNUAL_UPDATE` sin descargar archivos repetidos.

## ADDED Requirements

### Requirement: Hermeticidad y Desacoplamiento del Actor en Docker
El Actor de Apify SHALL ser completamente autocontenido dentro de su directorio raíz `actor/`, ejecutando curación, cruce geoespacial e inferencia sin importar módulos externos al contenedor.

#### Scenario: Ejecución en entorno limpio sin monorepo
- **WHEN** el Actor se ejecuta en un entorno donde las rutas de `etl/` y `producto2/` están ausentes del `sys.path`
- **THEN** el Actor SHALL procesar el lote sin arrojar `ModuleNotFoundError`, emitiendo las 10 features y scores con Exit Code 0.

## Test Plan & Resilience Strategy

1. **Aserción Semántica de Workflows n8n:**
   - Script determinista que valida que `workflow_anual_auditoria_gcba.json` tenga expresión cron `0 4 1 3 *` y que ambos flujos posean `"binaryData": true` para la subida a Drive.
2. **Test de Aislamiento Hermético (Clean-Room):**
   - Test unitario específico `test_actor_hermetic_isolation` que remueve la raíz del monorepo de `sys.path` y valida que `actor.src.pipeline` funcione de forma 100% independiente.
