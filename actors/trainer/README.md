# MLOps Annual Retraining Actor (XGBoost, K-Means & Drive)

Actor serverless de Apify encargado del **reentrenamiento anual** de los modelos de Machine Learning del Observatorio Inmobiliario CABA. Entrena de forma reproducible el pipeline de segmentación urbana (**K-Means**) y el regresor de precio justo (**XGBoost**), aplica guardas automáticas contra regresión de calidad y publica los artefactos listos para producción en el **Apify Key-Value Store** y, opcionalmente, en **Google Drive** mediante versionado atómico.

---

## Qué hace este Actor

1. **Ingesta flexible de datasets curados (`load_dataset_from_input`):**
   Acepta múltiples orígenes en orden de prioridad:
   - `trainingData`: arreglo JSON de registros curados.
   - `trainingDataCsvText`: texto CSV único o lista de textos CSV (usado por los workflows de n8n).
   - `trainingDataCsvUrl`: descarga HTTP directa de un CSV.
   - `dataPath`: ruta local opcional dentro del contenedor.
   - Deduplica automáticamente por clave natural (`listing_id`, `(calle_normalizada, m2_cubiertos, ambientes)` o `(latitud, longitud, m2_totales, ambientes)`).
2. **Guardas de calidad e idempotencia:**
   - Exige un volumen mínimo de muestras (`minSamples`, por defecto `500`); si no se alcanza, aborta con `ERR_INSUFFICIENT_DATA` (código de salida `1`).
   - Evalúa K-Means para $k \in \{2, 3, 4, 5, 6\}$ seleccionando el $k$ de mayor coeficiente *Silhouette* y asignando etiquetas interpretables a cada centroide.
   - Entrena `XGBRegressor` con transformación logarítmica (`TransformedTargetRegressor(log1p, expm1)`) sobre división 80/20.
   - Valida $R^2 \ge \text{minR2Threshold}$ (por defecto `0.80`); si no supera el umbral, aborta con `ERR_METRIC_REGRESSION` (código de salida `2`) protegiendo la versión vigente en producción.
   - Calcula el hash SHA-256 determinista del dataset (`dataset_hash`) y realiza subsampling de fondo para SHAP (`<= 100` muestras).
3. **Publicación de artefactos (`Apify KV Store` + `Google Drive`):**
   - Sube al **Default Key-Value Store** de la corrida: `kmeans_model.joblib`, `xgb_price_model.joblib`, `model_metadata.joblib`, `models_manifest.json` y `OUTPUT`.
   - Si se configuran `gdriveFolderId` y credenciales de Service Account (`gdriveServiceAccountJson`), ejecuta exportación atómica en `staging_v(N+1)/` con verificación de idempotencia por `dataset_hash` (`SKIP_IDENTICAL_DATASET`) antes de promover a `v(N+1)/` y actualizar `models_manifest.json`.

---

## Parámetros de Entrada

| Campo | Tipo | Default | Descripción |
| :--- | :--- | :--- | :--- |
| `trainingData` | `array` | - | Registros curados en formato JSON Array. |
| `trainingDataCsvText` | `string \| array` | - | Contenido CSV en texto o lista de CSVs (ideal para orquestación n8n). |
| `trainingDataCsvUrl` | `string` | - | URL pública o enlace directo al CSV de entrenamiento. |
| `dataPath` | `string` | - | Ruta local opcional dentro del contenedor. |
| `minSamples` | `integer` | `500` | Mínimo de observaciones deduplicadas requeridas para entrenar. |
| `minR2Threshold` | `number` | `0.80` | Umbral mínimo de $R^2$ en test para aceptar el modelo. |
| `targetCol` | `string` | `costo_total_ars` | Columna objetivo para el regresor XGBoost. |
| `gdriveFolderId` | `string` | - | ID de la carpeta `03_model_registry` en Google Drive. |
| `gdriveServiceAccountJson` | `string` (secreto) | - | JSON de credenciales de Service Account para escritura en Drive. |

### Columnas requeridas en el dataset de entrenamiento

- **Clustering (`CLUSTER_FEATURES`):** `ruido_db_promedio`, `densidad_delitos_500m`, `distancia_escuela_m`, `lineas_subte_600m`, `score_amenities`.
- **Regresión (`REGRESSION_FEATURES` + target):** `m2_totales`, `ruido_db_promedio`, `densidad_delitos_500m`, `distancia_escuela_m`, `lineas_subte_600m`, `banos`, `ambientes`, `cocheras`, y `costo_total_ars` (o `targetCol`).

### Ejemplo de Input JSON

```json
{
  "minSamples": 500,
  "minR2Threshold": 0.80,
  "trainingDataCsvUrl": "https://ejemplo.com/curated_caba_dataset.csv"
}
```

---

## Estructura de Salida (`output_schema.json`, `dataset_schema.json`, `key_value_store_schema.json`)

El Actor expone los siguientes resultados en el **Output Schema**:

- **`trainingSummary`**: `{{links.apiDefaultKeyValueStoreUrl}}/records/OUTPUT`
- **`modelsManifest`**: `{{links.apiDefaultKeyValueStoreUrl}}/records/models_manifest.json`
- **`kmeansModel`**: `{{links.apiDefaultKeyValueStoreUrl}}/records/kmeans_model.joblib`
- **`xgbPriceModel`**: `{{links.apiDefaultKeyValueStoreUrl}}/records/xgb_price_model.joblib`
- **`modelMetadata`**: `{{links.apiDefaultKeyValueStoreUrl}}/records/model_metadata.joblib`
- **`datasetSummary`**: `{{links.apiDefaultDatasetUrl}}/items`

### Ejemplo de `OUTPUT` / `models_manifest.json`

```json
{
  "generated_at": "2026-03-01T04:02:15.123456+00:00",
  "sample_count": 964,
  "dataset_hash": "e3b0c44298fc1c149afbf4c8996fb924...",
  "metrics": {
    "r2": 0.8412,
    "rmse": 142310.5,
    "mae": 98420.1,
    "silhouette": 0.2343
  },
  "artifacts": [
    "kmeans_model.joblib",
    "xgb_price_model.joblib",
    "model_metadata.joblib"
  ],
  "status": "production"
}
```

---

## Requisitos Operativos y Troubleshooting

- **Permisos del Actor (`LIMITED_PERMISSIONS`):** Opera de forma 100% aislada en sus propios almacenes de ejecución y llamadas externas a Google Drive. **No requiere verificación KYC ni tarjeta de crédito para publicarse como Actor Free en Apify Store**.
- **Memoria recomendada en Apify:** **1024 MB o 2048 MB** (*Settings > Memory*) para cómputo de siluetas K-Means y entrenamiento XGBoost.
- **`ERR_INSUFFICIENT_DATA` (exit code `1`):** El dataset deduplicado tiene menos filas que `minSamples`. En pruebas *Free Tier*, podés ajustar `minSamples: 30`.
- **`ERR_METRIC_REGRESSION` (exit code `2`):** El $R^2$ obtenido fue inferior a `minR2Threshold`; los modelos vigentes en producción no se sobrescriben.
- **`ERR_NO_DATA` / `ERR_GDRIVE_AUTH` (exit code `3`):** No se proveyó ninguna fuente de datos válida o el JSON de Service Account es inválido.
