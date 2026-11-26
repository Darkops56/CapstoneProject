# Zonaprop CABA Curator & Corporate Relocation Inference Engine

Actor serverless hermético de Apify diseñado para transformar publicaciones crudas de alquileres en la **Ciudad Autónoma de Buenos Aires (CABA)** en decisiones accionables de **relocalización corporativa**.

Combina limpieza tabular defensiva, extracción NLP de atributos inmobiliarios, enriquecimiento geoespacial **sin llamadas de red externas** (mediante geo-caché embebido del GCBA), segmentación urbana con **K-Means**, estimación de precio justo con **XGBoost** y cálculo de **Score de Decisión Corporativa (0–100)** para los perfiles `FAMILIA` y `SOLTERO_EJECUTIVO`.

---

## Qué hace este Actor

1. **Ingesta flexible:** Lee publicaciones desde un `datasetId` de Apify (por ejemplo, la salida de un scraper de Zonaprop) o directamente desde un arreglo JSON en `properties`.
2. **Curación tabular y NLP (`nlp_parser.py`):**
   - Unifica alquileres publicados en `USD` o `ARS` a **Pesos Argentinos (ARS)** incluyendo impuesto de sellos.
   - Extrae expensas desde campos estructurados o expresiones regulares sobre la descripción.
   - Detecta admisión real de mascotas (`apto_mascotas`) con resolución explícita de negaciones en texto libre (*"no se aceptan mascotas"* prevalece sobre etiquetas contradictorias).
   - Calcula `score_amenities` (`0–10`) ponderando seguridad, cochera, pileta, gimnasio, parrilla, SUM/coworking y balcón/terraza.
3. **Cruce geoespacial local con datos abiertos del GCBA (`reference_geo/`):**
   - **Ruido diurno (`ruido_db_promedio`):** *spatial join* contra `medicion_ruido.parquet`.
   - **Seguridad (`densidad_delitos_500m`, `indice_gravedad_delitos_500m`):** búsqueda radial Haversine (`BallTree`, 500 m) contra `delitos_tree.joblib`.
   - **Educación (`distancia_escuela_m`):** vecino más cercano al establecimiento educativo oficial más próximo.
   - **Conectividad (`lineas_subte_600m`):** líneas únicas de subterráneo dentro de un radio de 600 m.
   - **Imputación defensiva:** registros con coordenadas nulas o fuera del *bounding box* de CABA (`lat ∈ [-34.705, -34.525]`, `lon ∈ [-58.535, -58.345]`) se imputan al centroide de CABA dejando trazabilidad en `tag_auditoria`.
4. **Inferencia ML y Scoring (`scoring.py`):**
   - Carga modelos `kmeans_model.joblib`, `xgb_price_model.joblib` y `model_metadata.joblib` desde un **Apify Key-Value Store** dinámico (`modelStoreName` / `modelKvStoreId`) o desde los artefactos embebidos en el contenedor como *fallback*.
   - Emite `precio_justo_ars`, `desvio_precio_pct`, `pct_ahorro`, `cluster_habitabilidad`, `cluster_label` y puntajes `0–100` con clasificación automática para ambos perfiles.

---

## Parámetros de Entrada

| Campo | Tipo | Obligatorio | Descripción |
| :--- | :--- | :--- | :--- |
| `datasetId` | `string` | Condicional* | ID del Dataset de Apify generado por el scraper de Zonaprop. |
| `properties` | `array` | Condicional* | Lista JSON directa de publicaciones crudas (alternativa a `datasetId`). |
| `limit` | `integer` | No (default `1000`) | Cantidad máxima de publicaciones a procesar en la corrida. |
| `modelStoreName` | `string` | No | Nombre del Key-Value Store en Apify (ej. `mlops-production-models`) para cargar modelos actualizados sin reconstruir el contenedor. |
| `modelKvStoreId` | `string` | No | ID del Key-Value Store en Apify (alternativa por ID a `modelStoreName`). |

*\*Debe enviarse `datasetId` o `properties`. Si ambos se envían, `properties` tiene prioridad.*

### Ejemplo de Input JSON

```json
{
  "datasetId": "abc123DatasetId",
  "limit": 1000,
  "modelStoreName": "mlops-production-models"
}
```

---

## Estructura de Salida (`output_schema.json` y `dataset_schema.json`)

El Actor almacena todos los registros procesados en el **Default Dataset** de la corrida y expone dos accesos en el **Output Schema**:

- **`results`**: `{{links.apiDefaultDatasetUrl}}/items` (JSON completo con los 30 campos).
- **`resultsCsv`**: `{{links.apiDefaultDatasetUrl}}/items?format=csv&clean=true` (CSV tabular limpio para consumo en n8n, Google Drive o Streamlit).

### Campos por registro de salida (30 columnas)

- **Identificación y ubicación:** `listing_id`, `latitud`, `longitud`, `barrio`, `subzona`, `moneda_origen`
- **Económicas y físicas:** `alquiler_ars`, `expensas_ars`, `costo_total_ars`, `apto_mascotas`, `score_amenities`, `m2_totales`, `banos`, `ambientes`, `cocheras`, `tag_auditoria`
- **Entorno urbano GCBA:** `ruido_db_promedio`, `densidad_delitos_500m`, `indice_gravedad_delitos_500m`, `distancia_escuela_m`, `lineas_subte_600m`
- **Inferencia ML y Scoring:** `cluster_habitabilidad`, `cluster_label`, `precio_justo_ars`, `desvio_precio_pct`, `pct_ahorro`, `score_familia`, `score_soltero`, `calificacion_familia`, `calificacion_soltero`

### Categorías de recomendación

- **`ALTAMENTE RECOMENDADA`**: `score >= 75` y `desvio_precio_pct <= 5%`
- **`RECOMENDADA`**: `score >= 55` y `desvio_precio_pct <= 15%`
- **`DESCARTAR / SOBREPRECIO ALTO`**: `desvio_precio_pct > 20%`
- **`EVALUAR / ALTERNATIVA`**: Resto de los casos

### Ejemplo de Registro de Salida

```json
{
  "listing_id": "70000000",
  "latitud": -34.59,
  "longitud": -58.43,
  "barrio": "Palermo",
  "subzona": "Palermo",
  "moneda_origen": "USD",
  "alquiler_ars": 401598.0,
  "expensas_ars": 50000.0,
  "costo_total_ars": 451598.0,
  "apto_mascotas": 1.0,
  "score_amenities": 4.5,
  "m2_totales": 35.0,
  "banos": 1.0,
  "ambientes": 1.0,
  "cocheras": 0.0,
  "tag_auditoria": "VALID",
  "ruido_db_promedio": 62.5,
  "densidad_delitos_500m": 480.0,
  "indice_gravedad_delitos_500m": 612.0,
  "distancia_escuela_m": 145.2,
  "lineas_subte_600m": 1.0,
  "cluster_habitabilidad": 1,
  "cluster_label": "Zona Familiar Tranquila",
  "precio_justo_ars": 510000.0,
  "desvio_precio_pct": -11.45,
  "pct_ahorro": 11.45,
  "score_familia": 68.4,
  "score_soltero": 74.2,
  "calificacion_familia": "RECOMENDADA",
  "calificacion_soltero": "RECOMENDADA"
}
```

---

## Permisos, Costos y Troubleshooting

- **Permisos del Actor (`LIMITED_PERMISSIONS`):** Configurado con permisos limitados bajo el principio de menor privilegio (*least privilege*). **No requiere verificación de identidad (KYC) ni tarjeta de crédito para publicarse como Actor Free en Apify Store**.
- **Permisos delegados (`resourcePermissions`):** El Actor recibe acceso explícito de solo lectura (`READ`) al `datasetId` del scraper de Zonaprop y al `modelKvStoreId` seleccionados en el input, garantizando total seguridad sin acceder al resto de la cuenta del usuario.
- **Memoria recomendada:** **1024 MB** (uso pico medido en pruebas de ~528 MB para 1,000 registros y ~573 MB para 10,000 registros).
- **Fallback local de modelos:** Si no se suministra `modelKvStoreId` o el almacén dinámico no está disponible, el Actor carga automáticamente los modelos congelados de `artifacts/` sin interrumpir la corrida.
- **`WARN: Entrada vacía`:** Ni `datasetId` ni `properties` contenían registros; revisa el Circuit Breaker del scraper previo.
- **`tag_auditoria` con `AUDIT_COORD_IMPUTED` / `AUDIT_PRICE_IMPUTED`:** Indica imputación defensiva ante datos faltantes o fuera de CABA; el registro no se descarta y conserva trazabilidad explícita.
