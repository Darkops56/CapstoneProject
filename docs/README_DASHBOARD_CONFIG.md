# Configuración del Dashboard Streamlit (Google Drive con API Key)

El dashboard del Observatorio Inmobiliario CABA (`dashboard/app.py`) consume los datos enriquecidos **exclusivamente desde Google Drive** (sin respaldo de archivos locales).

La forma recomendada para operar en local y en producción (**Streamlit Community Cloud**) es apuntar a la carpeta pública de Google Drive usando una **API Key de Google Drive**. De este modo:

- El dashboard **autodetecta y descarga automáticamente el CSV mensual más reciente** (`alquileres_caba_enriquecido_YYYY_MM.csv`) cada vez que el pipeline sube un nuevo mes.
- Funciona en cuentas de Google Workspace / educativas donde la política `iam.disableServiceAccountKeyCreation` bloquea la creación de claves JSON de cuentas de servicio.
- No requiere dependencias adicionales de Google SDK (usa únicamente `requests` contra la Google Drive API v3).

---

## 1. Preparar Google Drive y crear la API Key (una sola vez)

### 1.1 Compartir la carpeta como pública (solo lectura)
1. En Google Drive, hacé clic derecho sobre la carpeta donde se guardan los CSV mensuales (por ejemplo `01_mensual_enriquecido`).
2. Seleccioná **Compartir**.
3. En **Acceso general**, cambiá a **Cualquier persona con el enlace** con rol **Lector**.
4. Copiá el enlace o el ID de la carpeta (por ejemplo `10bpShYlE_FSzUtW3xNz5jH0BGbRGF4yo`). El loader acepta tanto el **ID** como la **URL completa** de la carpeta.

### 1.2 Habilitar Google Drive API y crear la API Key en Google Cloud
1. Ingresá a [Google Cloud Console](https://console.cloud.google.com) y seleccioná (o creá) tu proyecto.
2. Ir a **APIs y servicios → Biblioteca**, buscar **Google Drive API** y hacer clic en **Habilitar**.
3. Ir a **APIs y servicios → Credenciales**.
4. Hacer clic en **+ Crear credenciales → Clave de API**.
5. *(Recomendado por seguridad)* Hacer clic en **Editar clave de API**:
   - En **Restricciones de API**, elegí **Restringir clave**.
   - Seleccioná únicamente **Google Drive API**.
   - Hacé clic en **Guardar**.
6. Copiá la clave generada (`AIzaSy...`).

> **Nota sobre nombres de archivos:** La autodetección busca archivos dentro de la carpeta cuyo nombre contenga `alquileres_caba_enriquecido_` y los ordena por `(año, mes)` descendente extraído del patrón `YYYY_MM` (y luego por `modifiedTime`).

---

## 2. Configuración Local

### Opción A: `.streamlit/secrets.toml` (recomendada)

Creá el archivo `.streamlit/secrets.toml` en el directorio desde el cual ejecutás `streamlit run`:
- Si corrés `streamlit run dashboard/app.py` desde la raíz del repositorio: `.streamlit/secrets.toml`
- Si corrés `streamlit run app.py` dentro de `dashboard/`: `dashboard/.streamlit/secrets.toml`

> `.streamlit/secrets.toml` ya está incluido en `.gitignore` para evitar subir credenciales al repositorio.

Contenido del archivo:

```toml
gdrive_folder_id = "10bpShYlE_FSzUtW3xNz5jH0BGbRGF4yo"
gdrive_api_key = "AIzaSyTU_API_KEY_AQUI"
```

*(También es válido pegar la URL completa de la carpeta en `gdrive_folder_id`, por ejemplo `"https://drive.google.com/drive/folders/10bpShYlE_FSzUtW3xNz5jH0BGbRGF4yo"`).*

Luego iniciá el dashboard:

```bash
streamlit run dashboard/app.py
```

### Opción B: Variables de entorno del sistema

En Linux/macOS:

```bash
export GDRIVE_FOLDER_ID="10bpShYlE_FSzUtW3xNz5jH0BGbRGF4yo"
export GDRIVE_API_KEY="AIzaSyTU_API_KEY_AQUI"
streamlit run dashboard/app.py
```

---

## 3. Configuración en Producción (Streamlit Community Cloud)

En **Streamlit Community Cloud** nunca se sube `.streamlit/secrets.toml` a Git; los valores se cargan desde el panel web:

1. Ingresá a [share.streamlit.io](https://share.streamlit.io).
2. **Despliegue nuevo:** al configurar la app (archivo principal: `dashboard/app.py`), hacé clic en **Advanced settings...** antes de pulsar **Deploy**.
   **App ya desplegada:** abrí el menú `⋮` de la app (o **Manage app** → `⋮`) y entrá a **Settings → Secrets**.
3. Pegá exactamente el siguiente bloque TOML (asegurándote de **no dejar** `gdrive_csv_url` ni `gdrive_file_id` definidos):

```toml
gdrive_folder_id = "10bpShYlE_FSzUtW3xNz5jH0BGbRGF4yo"
gdrive_api_key = "AIzaSyTU_API_KEY_AQUI"
```

4. Hacé clic en **Save**. Streamlit Cloud guardará los secrets encriptados y reiniciará la aplicación automáticamente.

---

## 4. Referencia de variables y orden de prioridad

El módulo `dashboard/src/data_loader.py` revisa primero `os.environ` y luego `st.secrets`. Si hay más de un modo configurado, aplica esta prioridad:

| Prioridad | Modo | Variable de entorno | Clave en `secrets.toml` | Cuándo usarlo |
| :--- | :--- | :--- | :--- | :--- |
| 1 | URL directa | `GDRIVE_CSV_URL` | `gdrive_csv_url` | Enlace directo de descarga a un CSV específico. |
| 2 | Archivo individual | `GDRIVE_FILE_ID` | `gdrive_file_id` | ID o URL de un único CSV público en Drive. |
| 3 | **Carpeta + API Key (Recomendado)** | `GDRIVE_FOLDER_ID` + `GDRIVE_API_KEY` | `gdrive_folder_id` + `gdrive_api_key` | Carpeta pública con autodetección del último CSV mensual. |
| 4 | Carpeta + Service Account | `GDRIVE_FOLDER_ID` + `GCP_SERVICE_ACCOUNT` | `gdrive_folder_id` + `[gcp_service_account]` | Carpeta privada (requiere `google-auth` y `google-api-python-client` en `dashboard/requirements.txt`). |

---

## 5. Solución de problemas frecuentes

- **`403 Forbidden` al consultar la carpeta:**
  - Verificá que **Google Drive API** esté habilitada en el proyecto de Google Cloud donde creaste la API Key.
  - Verificá que la carpeta esté compartida como **Cualquier persona con el enlace (Lector)**.
- **`404 Not Found`:**
  - Confirmá que estás usando `gdrive_folder_id` (y no `gdrive_file_id`) para el ID de una carpeta.
- **`No files matching pattern found in folder`:**
  - Asegurate de que el archivo dentro de la carpeta contenga `alquileres_caba_enriquecido_` en su nombre (por ejemplo `alquileres_caba_enriquecido_2026_11.csv`).
- **Cambios en secrets que no se reflejan:**
  - En local: presioná `C` en el navegador (Clear cache) y recargá.
  - En Streamlit Cloud: usá **Manage app → Reboot app**.
