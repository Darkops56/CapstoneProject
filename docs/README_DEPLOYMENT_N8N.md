# Runbook de Despliegue y Operación: Pipeline de Inferencia Zonaprop, Model Registry & n8n

Este documento detalla el paso a paso minucioso para desplegar los actores de inferencia y entrenamiento en **Apify Cloud**, configurar el almacenamiento versionado en **Google Drive** y orquestar las ejecuciones automáticas y políticas de retención utilizando **n8n**.

---

## 1. Arquitectura de Workflows y Actores

El ecosistema desacopla estrictamente el ciclo mensual de inferencia del ciclo anual de reentrenamiento serverless:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ORQUESTACIÓN EN N8N                               │
├──────────────────────────────────────┬──────────────────────────────────────┤
│       CICLO MENSUAL (Día 1)          │        CICLO ANUAL (1 de Marzo)      │
├──────────────────────────────────────┼──────────────────────────────────────┤
│ 1. Scraper Zonaprop (Apify)          │ 1. Auditoría CKAN GCBA (Delitos)     │
│ 2. Circuit Breaker & Idempotencia    │ 2. Resguardo Raw en Google Drive     │
│ 3. Actor Inferencia (actor/)         │ 3. Actor Reentrenamiento (trainer/)  │
│ 4. Guardar CSV en 01_mensual         │ 4. Registro en 03_model_registry     │
│ 5. Purga Retención Trimestral        │ 5. Actualización models_manifest.json│
└──────────────────────────────────────┴──────────────────────────────────────┘
```

### Repositorio de Workflows (`workflows/n8n/`)
- **`workflow_mensual_zonaprop_inferencia.json`**: Flujo mensual completo con extracción Zonaprop, scoring corporativo, persistencia en Google Drive y **purga automática de datasets de más de 3 meses**.
- **`workflow_anual_auditoria_gcba.json`**: Flujo anual de auditoría e ingesta de datos abiertos de delitos del GCBA.
- **`Pipeline Completo Anual y Mensual.json`**: Integración de ambos ciclos en un único lienzo visual.

> **Seguridad de Credenciales:** Los archivos JSON exportados solo contienen identificadores de referencia interna (`id`), garantizando que **ningún token de Apify ni credencial OAuth2 de Google Drive queda expuesto en el código**.

---

## 2. Requisitos Previos

1. **Node.js LTS (>= v22.x)**:
   ```bash
   nvm install 22
   nvm use 22
   nvm alias default 22
   ```
2. **Apify CLI**:
   ```bash
   npm install -g apify-cli
   apify --version
   ```
3. **Instancia de n8n**:
   - Cuenta activa en **n8n Cloud** o instancia self-hosted (vía Docker: `docker run -it --rm -p 5678:5678 n8nio/n8n`).
4. **Google Drive**:
   - Cuenta de Google con acceso para crear carpetas y configurar credenciales OAuth2.

---

## 3. Despliegue de Actores en Apify Cloud

El proyecto cuenta con dos actores serverless desacoplados para optimizar memoria, tiempos de inicio y costos:

### Paso 3.1: Autenticación en Apify
En tu terminal local ejecuta:
```bash
apify login
```
Verifica la sesión activa con:
```bash
apify info
```

---

### Paso 3.2: Desplegar Actor de Inferencia Mensual (`actor/`)
Este actor ligero procesa los datos mensuales, cruza el geo-caché de CABA y aplica inferencia con modelos congelados:

```bash
cd actor
apify push
```
- Se compilará en Apify bajo el nombre `zonaprop-curator-inference`.
- **Configurar Permisos Completos (Crítico)**:
  1. Ve a [console.apify.com/actors](https://console.apify.com/actors) > `zonaprop-curator-inference` > pestaña **Settings**.
  2. En **Access & Permissions**, cambia **Actor permissions** a **`Full permissions`** (necesario para leer datasets del scraper).
  3. Guarda los cambios.

---

### Paso 3.3: Desplegar Actor de Reentrenamiento Anual (`trainer/`)
Este actor serverless entrena bajo demanda XGBoost y K-Means, evalúa $R^2 \ge 0.80$ y exporta modelos a Drive:

```bash
cd ../trainer
apify push
```
- Se compilará en Apify bajo el nombre `mlops-annual-trainer`.
- **Configurar Memoria Mínima**: Asignar al menos **1024 MB o 2048 MB** en *Settings > Memory* para el entrenamiento y cómputo de siluetas.

---

## 4. Preparación de Google Drive

En tu unidad de [Google Drive](https://drive.google.com/), estructura las siguientes carpetas canónicas:

1. **`01_mensual_enriquecido`** (ej. ID: `10bpShYlE_FSzUtW3xNz5jH0BGbRGF4yo`):
   - Almacena los archivos mensuales `alquileres_caba_enriquecido_YYYY_MM.csv` consumidos por el dashboard de Streamlit.
   - Aplica la política de retención para conservar únicamente los 3 datasets más recientes.
2. **`02_anual_gcba_raw`** (ej. ID: `1HFbHhTxwNWq4rdTY2EIAjNme9xnTlZx2`):
   - Almacena los archivos raw oficiales anuales del GCBA (`delitos_gcba_anual_YYYY.csv`).
3. **`03_model_registry`**:
   - Almacena las subcarpetas versionadas de modelos (`v1/`, `v2/`, etc.) y el manifiesto global `models_manifest.json`.

---

## 5. Configuración y Conexión en n8n

### Paso 5.1: Conectar Credenciales en n8n

1. **Credencial de Apify (Header Auth)**:
   - En n8n: **Credentials** > **Add Credential** > busca **Header Auth**.
   - **Name**: `Authorization`
   - **Value**: `Bearer TU_API_TOKEN_DE_APIFY` *(obtenido en console.apify.com > Settings > Integrations)*.
   - Nombre sugerido: `Apify Header Auth`.

2. **Credencial de Google Drive (OAuth2)**:
   - En n8n: **Credentials** > **Add Credential** > busca **Google Drive OAuth2 API**.
   - Haz clic en **Sign in with Google**, selecciona tu cuenta y autoriza el acceso a Drive.
   - Nombre sugerido: `Google Drive account`.

---

### Paso 5.2: Importar el Workflow

1. En n8n, crea un nuevo workflow.
2. Menú superior derecho (`...`) > **Import from File**.
3. Selecciona `workflows/n8n/workflow_mensual_zonaprop_inferencia.json`.

---

### Paso 5.3: Configuración Detallada de los Nodos en n8n

| Nodo | Parámetros Clave | Configuración Requerida |
| :--- | :--- | :--- |
| **Apify: Scraper Zonaprop** | URL & Auth | `waitForFinish=300`, Auth: `Apify Header Auth` |
| **Apify: Actor Curado & Inferencia** | URL | `https://api.apify.com/v2/acts/TU_USUARIO~zonaprop-curator-inference/runs?waitForFinish=120` |
| **Descargar CSV Enriquecido** | Options > Response | **Response Format: `File`** (descarga binaria, no texto) |
| **Google Drive: Guardar CSV Mensual** | Resource / Operation | Folder: `01_mensual_enriquecido`, Name: `=alquileres_caba_enriquecido_{{ $now.format('yyyy_MM') }}.csv` |
| **Google Drive: Listar Archivos 01_mensual_enriquecido** | Resource / Operation | **Resource:** `File/Folder`<br>**Operation:** `Search`<br>**Search Method:** `Advanced Search`<br>**Query String:** `'10bpShYlE_FSzUtW3xNz5jH0BGbRGF4yo' in parents and trashed = false and mimeType = 'text/csv'`<br>**Return All:** `true` |
| **Retención: Filtrar Archivos > 3 Meses** | Code Node (JS) | Ordena por fecha descendente y retorna excedentes a purgar (`items.slice(3)`) si `length > 3`. |
| **Google Drive: Purgar Excedente a Papelera** | Resource / Operation | **Resource:** `File`<br>**Operation:** `Delete`<br>**File ID:** `={{ $json.fileId }}`<br>**Delete Permanently:** `false` (envía a papelera defensivamente) |

---

## 6. Verificación y Prueba de Extremo a Extremo

1. En n8n, haz clic en **Test workflow** (o *Execute workflow*).
2. Verifica la secuencia:
   - Scraper recolecta las publicaciones de Zonaprop.
   - Circuit Breaker valida `SUCCEEDED` y presencia de dataset.
   - Inferencia en Apify genera predicciones y scores (0-100).
   - n8n transfiere el CSV a la carpeta `01_mensual_enriquecido`.
   - El nodo de búsqueda lista los CSVs existentes en la carpeta.
   - Si existen más de 3 datasets mensuales, los más antiguos se envían a la papelera.
3. **Pase a Producción:** Activa el interruptor **Active** en la esquina superior de n8n para dejar programado el Cron mensual (Día 1 de cada mes a las 03:00 UTC).

---

## 7. Matriz de Troubleshooting Rápido

| Síntoma / Error | Causa Raíz | Solución Determinista |
| :--- | :--- | :--- |
| `Could not get parameter "queryString"` | El nodo de búsqueda de Drive tiene `Search Method` configurado con un texto no válido o vacío. | En el nodo de búsqueda, cambiar el desplegable **Search Method** a **`Advanced Search`**. Se abrirá el campo **Query String** para pegar la consulta. |
| `Cannot read properties of undefined (reading 'execute')` | Incompatibilidad de operación en n8n: se seleccionó Resource `File` con operation `list` (la cual no existe en la v3 del nodo). | Configurar **Resource: `File/Folder`** y **Operation: `Search`**. |
| `Apify CLI requires Node.js >= 22` | La terminal tiene activa una versión desactualizada o alpha de Node. | Ejecutar `nvm use 22` o `nvm alias default 22`. |
| `ForbiddenError: Insufficient permissions for the dataset (exit code 91)` | El Actor de Apify tiene permisos limitados y no puede leer datasets de otros actores. | En Apify Console > Actor `zonaprop-curator-inference` > Settings > Access & Permissions: seleccionar **`Full permissions`**. |
| Drive: `expects binary file 'data', but none was found` | El nodo HTTP de descarga no especificó el formato de archivo. | En el nodo HTTP de descarga, ir a `Options` > `Response` > `Response Format` y seleccionar **`File`**. |
| `ERR_METRIC_REGRESSION` en el Actor Trainer | El modelo reentrenado obtuvo un $R^2 < 0.80$ y abortó para proteger producción. | Verificar calidad y volumen de datos en el CSV de reentrenamiento. El registry anterior permanece intacto. |
