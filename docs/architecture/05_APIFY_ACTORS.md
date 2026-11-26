# 05 · Actores Serverless en Apify: Arquitectura, Contratos y Output Schemas

Este documento consolida el diseño técnico, los contratos de entrada/salida y la configuración de publicación en **Apify Store** para los dos contenedores serverless ubicados en `actors/`.

---

## 1. Visión General y Desacoplamiento

Ambos Actores están empaquetados sobre `apify/actor-python:3.11` con aislamiento hermético (sin importar módulos externos de `src/` en tiempo de ejecución):

| Actor | Directorio | Nombre en Apify | Frecuencia / Rol | Almacenamiento de Salida |
| :--- | :--- | :--- | :--- | :--- |
| **Inference & Curator** | `actors/inference/` | `zonaprop-curator-inference` | Mensual: limpieza NLP, geo-cruce GCBA, K-Means, XGBoost y Scoring `0–100` | Default Dataset (`30` columnas) |
| **MLOps Annual Trainer** | `actors/trainer/` | `mlops-annual-trainer` | Anual / Bajo demanda: reentrenamiento K-Means + XGBoost, guarda $R^2 \ge 0.80$, KV Store + Drive | Default Key-Value Store (`5` claves) + Default Dataset (`1` ítem resumen) |

---

## 2. Cómo se implementan los Output Schemas en Apify (`@apify/json_schemas`)

En la especificación v1 de Apify (`.actor/actor.json`), la publicación completa en Apify Store distingue **tres esquemas complementarios** dentro de `.actor/`:

```text
.actor/actor.json
 ├── "readme": "../README.md"                          (Obligatorio para Store)
 ├── "input":  "./input_schema.json"                   (UI de parámetros y validación de entrada)
 ├── "output": "./output_schema.json"                  (Obligatorio para Store: enlaces del Run)
 └── "storages":
      ├── "dataset": "./dataset_schema.json"           (Tipado Draft-07 + vistas tabla en Console)
      └── "keyValueStore": "./key_value_store_schema.json" (Claves/colecciones del KV Store)
```

### Reglas clave de `output_schema.json`
Según el esquema oficial `https://apify.com/schemas/v1/output.json`:
- **No** describe las columnas de un registro (eso corresponde a `dataset_schema.json`).
- Define las **propiedades de salida del Run** mediante `actorOutputSchemaVersion: 1` y un objeto `properties` donde cada entrada **solo** puede contener `{ title, type, description, template }`.
- El campo `type` debe ser literalmente `"string"` y `template` debe interpolar variables de corrida:
  - `{{links.apiDefaultDatasetUrl}}/items`
  - `{{links.apiDefaultKeyValueStoreUrl}}/records/<KEY>`

---

## 3. Contrato del Actor de Inferencia (`actors/inference/`)

### Entrada (`actors/inference/.actor/input_schema.json`)
- `datasetId` (`string`): ID de dataset de Apify generado por el scraper de Zonaprop.
- `properties` (`array`, JSON): Arreglo directo de propiedades crudas (alternativa a `datasetId`).
- `limit` (`integer`, default `1000`): Tope de publicaciones a procesar.
- `modelStoreName` (`string`): Nombre de KV Store dinámico (ej. `mlops-production-models` desde n8n).
- `modelKvStoreId` (`string`): ID de KV Store dinámico alternativo.

### Geo-caché embebido (`actors/inference/reference_geo/`)
- `medicion_ruido.parquet` (~27.2 MB): polígonos de ruido diurno GCBA para `gpd.sjoin(..., predicate="within")`.
- `delitos_tree.joblib` (~2.1 MB): `BallTree` Haversine para volumen (`densidad_delitos_500m`) y gravedad (`indice_gravedad_delitos_500m`) en radio 500 m.
- `contexto_urbano.parquet` (~38 KB): escuelas (`distancia_escuela_m`) y bocas de subte (`lineas_subte_600m`).

### Artefactos fallback (`actors/inference/artifacts/`)
- `kmeans_model.joblib`, `xgb_price_model.joblib`, `model_metadata.joblib`. Si `modelStoreName` o `modelKvStoreId` fallan o no se especifican, el Actor cae de forma segura a estos artefactos embebidos.

### Salida (`output_schema.json` + `dataset_schema.json`)
- `output_schema.json` expone `results` (JSON) y `resultsCsv` (`?format=csv&clean=true`).
- `dataset_schema.json` tipa las **30 columnas exactas** emitidas por `actors/inference/src/pipeline.py` y configura la vista `overview` en tabla para Apify Console.

---

## 4. Contrato del Actor Trainer (`actors/trainer/`)

### Entrada (`actors/trainer/.actor/input_schema.json`)
- Fuentes de datos en orden de precedencia (`load_dataset_from_input`): `trainingData` (`array`), `trainingDataCsvText` (`string` o `array` — soporta tanto listas CSV de n8n como string único), `trainingDataCsvUrl` (`string`), `dataPath` (`string`).
- Hiperparámetros y guardas: `minSamples` (default `500`), `minR2Threshold` (default `0.80`), `targetCol` (default `costo_total_ars`).
- Exportación a Google Drive: `gdriveFolderId` (`string`), `gdriveServiceAccountJson` (`string`, `isSecret: true`).

### Salida (`output_schema.json`, `dataset_schema.json`, `key_value_store_schema.json`)
- **Key-Value Store:** `OUTPUT`, `models_manifest.json`, `kmeans_model.joblib`, `xgb_price_model.joblib`, `model_metadata.joblib`.
- **Default Dataset:** `1` ítem resumen (`status`, `kv_artifacts`, `manifest`, `training_results`, `drive_export`).
- **Google Drive (`03_model_registry`):** subida atómica en `staging_v(N+1)/`, idempotencia por `dataset_hash` (`SKIP_IDENTICAL_DATASET`) y promoción a `v(N+1)/`.

---

## 5. Verificación, Permisos y Publicación en Apify Store

- **Aislamiento y Permisos (`LIMITED_PERMISSIONS`):** Ambos `actor.json` declaran `"actorPermissionLevel": "LIMITED_PERMISSIONS"`. Esto permite:
  1. **Publicar en Apify Store como Actor Free sin ingresar datos crediticios ni someterse a verificación de identidad legal (KYC)**.
  2. Cumplir con el principio de menor privilegio (*least privilege*), mejorando el *Quality Score* y ranking en el catálogo de Apify.
  3. En `actors/inference/.actor/input_schema.json`, los campos `datasetId` y `modelKvStoreId` declaran `"resourcePermissions": ["READ"]`, otorgando acceso granular seguro a los datasets y almacenes de modelos seleccionados sin abrir la cuenta completa.
- Ambos `Dockerfile` copian `.actor/` completa (`COPY --chown=myuser:myuser .actor/ ./.actor/`), empaquetando automáticamente `actor.json`, `input_schema.json`, `output_schema.json`, `dataset_schema.json` y `key_value_store_schema.json`.
- Checklist antes de publicar en Apify Console > **Publishing**:
  1. Ejecutar `apify push` dentro de `actors/inference` y `actors/trainer`.
  2. Ejecutar al menos una corrida exitosa de cada Actor en Apify Cloud.
  3. En **Publishing**, seleccionar modelo **Free (Gratuito)** y completar: logo, categoría, descripción corta y ejemplo de salida.
  4. Validación automatizada local: `pytest tests/test_actor_schemas.py`.
