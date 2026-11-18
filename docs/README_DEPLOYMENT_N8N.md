# Runbook de Despliegue y Operación: Pipeline de Inferencia Zonaprop & n8n

Este documento detalla el paso a paso minucioso para desplegar el motor de scoring e inferencia inmobiliaria en **Apify Cloud** y orquestar las ejecuciones automáticas hacia **Google Drive** utilizando **n8n**.

---

## 1. Arquitectura de Workflows en el Repositorio

En la carpeta `workflows/n8n/` dispones de dos modalidades de despliegue según tu preferencia operativa:

- **Modo Todo en Uno (Recomendado):**
  - **`Pipeline Completo Anual y Mensual.json`**: Contiene ambas cadencias (mensual para Zonaprop y anual para GCBA) integradas en un único lienzo visual. Es el workflow listo para producción y pruebas conjuntas.
- **Modo Modular:**
  - **`workflow_mensual_zonaprop_inferencia.json`**: Flujo independiente exclusivo para la extracción mensual de Zonaprop, scoring y persistencia.
  - **`workflow_anual_auditoria_gcba.json`**: Flujo independiente exclusivo para la auditoría e ingesta anual de datos abiertos de delitos del GCBA.

> **Seguridad de Credenciales:** Los archivos JSON exportados solo contienen identificadores de referencia interna (`id`), garantizando que **ningún token secreto de Apify ni credencial OAuth de Google Drive queda expuesto en el código**.

---

## 2. Requisitos Previos

1. **Node.js LTS (>= v22.x)**:
   - Para evitar incompatibilidades de versiones pre-release en la CLI de Apify, utiliza la versión LTS recomendada:
     ```bash
     nvm install 22
     nvm use 22
     # Opcional: fijarla como global
     nvm alias default 22
     ```
2. **Apify CLI**:
   - Instalación global:
     ```bash
     npm install -g apify-cli
     apify --version
     ```
3. **Instancia de n8n**:
   - Acceso a **n8n Cloud** o una instancia self-hosted (vía Docker: `docker run -it --rm -p 5678:5678 n8nio/n8n`).
4. **Google Drive**:
   - Cuenta de Google con espacio disponible para almacenar los archivos CSV y raw.

---

## 3. Despliegue del Actor en Apify Cloud

El Actor encapsula la limpieza tabular, el cruce geoespacial con el caché urbano de CABA (ruido, delitos, escuelas, subtes) y los modelos de Machine Learning (XGBoost y K-Means).

### Paso 3.1: Inicio de Sesión en Apify
En tu terminal local ejecuta:
```bash
apify login
```
- Se abrirá automáticamente una pestaña en tu navegador.
- Inicia sesión con tu cuenta de Google o GitHub.
- La CLI confirmará la autenticación guardando el token de forma segura en `~/.apify/auth.json`.
- Puedes verificar tu usuario activo con:
  ```bash
  apify info
  ```

### Paso 3.2: Desplegar y Compilar el Actor
Sitúate en la carpeta `actor/` y haz el push a la nube:
```bash
cd actor
apify push
```
- La CLI empaquetará el código fuente, los modelos `.joblib` y el geo-caché de CABA.
- Se compilará la imagen Docker en la infraestructura de Apify.
- Al finalizar, verás la URL de tu Actor en la consola (formato: `tu-usuario/zonaprop-curator-inference`).

### Paso 3.3: Permisos de Acceso entre Datasets (Crítico)
Por diseño seguro, Apify restringe el acceso de los contenedores a su propio almacenamiento temporal (`LIMITED_PERMISSIONS`). Para que tu Actor de Inferencia pueda leer los datasets generados por el Actor Scraper de Zonaprop, debe contar con permisos completos de cuenta:

1. Entra a [console.apify.com/actors](https://console.apify.com/actors).
2. Selecciona tu Actor `zonaprop-curator-inference` > pestaña **Settings**.
3. En la sección **Access & Permissions**:
   - Cambia **Actor permissions** a **`Full permissions`** (o mediante CLI: `apify api put actors/<ACTOR_ID> -d '{"actorPermissionLevel": "FULL_PERMISSIONS"}'`).
4. Guarda los cambios.

---

## 4. Preparación de Google Drive

1. Ingresa a tu [Google Drive](https://drive.google.com/).
2. Crea las carpetas destino donde se depositarán los datos:
   - **`01_mensual_enriquecido`**: Recibirá mensualmente el archivo `alquileres_caba_enriquecido_YYYY_MM.csv` con las 29 columnas y scores de decisión corporativa.
   - **`02_anual_gcba_raw`**: Recibirá anualmente el archivo `delitos_gcba_anual_YYYY.csv` si el catálogo CKAN reporta actualizaciones.

---

## 5. Configuración y Conexión en n8n

### Paso 5.1: Conectar Credenciales en n8n

1. **Credencial de Apify (Header Auth)**:
   - En n8n, ve a **Credentials** > **Add Credential** > busca **Header Auth**.
   - **Name**: `Authorization`
   - **Value**: `Bearer TU_API_TOKEN_DE_APIFY` *(obtenido en console.apify.com > Settings > Integrations)*.
   - Nómbrala `Apify Header Auth` y guarda.

2. **Credencial de Google Drive (OAuth2)**:
   - En n8n, ve a **Credentials** > **Add Credential** > busca **Google Drive OAuth2 API**.
   - Haz clic en **Sign in with Google**, selecciona tu cuenta y autoriza el acceso a Drive.
   - Guarda la credencial (por defecto llamada `Google Drive account`).

---

### Paso 5.2: Importar el Workflow

1. En n8n, crea un nuevo workflow.
2. Haz clic en el menú de 3 puntos (`...`) arriba a la derecha > **Import from File**.
3. Selecciona el archivo `workflows/n8n/Pipeline Completo Anual y Mensual.json`.

---

### Paso 5.3: Vinculación Rápida de Nodos en n8n

Al abrir el flujo importado, solo debes verificar la asignación de tus cuentas y carpetas:

1. **Nodos de Apify (Scraper, Inferencia y Descarga CSV)**:
   - En el campo **Credential for Header Auth**, selecciona tu credencial `Apify Header Auth`.
   - En el nodo **"Apify: Actor Curado & Inferencia"**, confirma que la URL apunte a tu Actor:
     `https://api.apify.com/v2/acts/tu-usuario~zonaprop-curator-inference/runs?waitForFinish=120`
2. **Nodo "Descargar CSV Enriquecido"**:
   - Asegúrate de que bajo **Options** tenga activa la opción **Response**:
     - **Response Format**: `File` (garantiza que descargue el CSV como archivo binario y no como texto plano).
3. **Nodos de Google Drive**:
   - En **Credential to connect with**, selecciona tu `Google Drive account`.
   - En **Parent Folder**:
     - n8n permite seleccionarlo directamente desde la lista (**"From list"**):
       - En el nodo mensual, selecciona tu carpeta `01_mensual_enriquecido`.
       - En el nodo anual, selecciona tu carpeta `02_anual_gcba_raw`.

---

## 6. Verificación y Prueba de Extremo a Extremo

Para comprobar que todo el pipeline funciona de punta a punta sin esperar a la activación programada:

1. Haz clic en el botón inferior del lienzo: **`Test workflow`** (o *Execute workflow*).
2. Observa el flujo de ejecución en tiempo real:
   - El Scraper Zonaprop recolectará los avisos mediante la URL directa `startUrls`.
   - El Circuit Breaker validará que el estado sea `SUCCEEDED` y que exista un dataset válido.
   - La compuerta condicional evaluará `proceed === true` y disparará tu Actor en Apify.
   - Tu Actor procesará las propiedades, cruzará el geo-caché y calculará el score corporativo.
   - n8n descargará el archivo binario y lo transferirá a Google Drive.
3. Entra a tu carpeta `01_mensual_enriquecido` en Google Drive: encontrarás el CSV generado listo para su consumo o visualización.
4. **Activar para Producción:** Una vez verificado el resultado, activa el interruptor superior **Active** en n8n para que los disparadores Cron continúen ejecutándose automáticamente en sus fechas estipuladas.

---

## 7. Matriz de Troubleshooting Rápido

| Síntoma / Error | Causa Raíz | Solución |
|---|---|---|
| `Apify CLI requires Node.js >= 22` | La shell activa una versión pre-release o alpha de Node. | Ejecutar `nvm use 22` o `nvm alias default 22`. |
| `ForbiddenError: Insufficient permissions for the dataset (exit code 91)` | El Actor de Apify tiene `LIMITED_PERMISSIONS` y no puede leer el dataset del scraper. | Configurar `actorPermissionLevel: "FULL_PERMISSIONS"` en Apify Console > Settings del Actor. |
| Scraper finaliza con 0 items | El cuerpo JSON del scraper usó parámetros obsoletos. | Utilizar la propiedad canónica `startUrls` con la URL de departamentos de CABA. |
| Drive: `expects binary file 'data', but none was found` | El nodo HTTP de descarga devolvió texto plano en lugar de un archivo binario. | En el nodo HTTP de descarga, ir a `+ Add option` > `Response` > `Response Format: File`. |
| Flujo anual siempre dice "Hay Novedades" en pruebas manuales | En pruebas manuales en el editor, n8n no persiste `$getWorkflowStaticData()`. | Comportamiento esperado en canvas de prueba. En ejecuciones automáticas de cron sí persiste y filtra novedades idénticas. |
