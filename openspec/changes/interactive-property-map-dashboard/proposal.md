## Why

El proyecto cuenta actualmente con los resultados de inferencia (`producto2/resultados_inferencia_caba.csv`), enriquecimiento geoespacial (`producto1/dataset_enriquecido_completo.csv`) y el pipeline mensual que deposita `alquileres_caba_enriquecido_YYYY_MM.csv` en Google Drive (`actor/src/pipeline.py`), pero carece de una interfaz visual interactiva para que los analistas de Relocalización Corporativa (RR.HH.) y usuarios finales exploren las propiedades geográficamente. Se requiere un dashboard en Streamlit con visualización en mapa estilo Zonaprop (usando PyDeck WebGL para escalar de ~1.000 a 50.000+ registros), codificación visual por perfil (`FAMILIA` vs. `SOLTERO_EJECUTIVO`) y semáforo de precios (`Bajo Precio`, `Precio Justo`, `Sobreprecio`), filtros por features/amenities, consumo automático del CSV más reciente desde Google Drive con fallback local resiliente, y aislamiento de esta rama para despliegue limpio.

## Governance & Complexity Tier

- **Tier Asignado**: **Tier M (Medio)** — Nueva aplicación interactiva autocontenida con ingesta externa (Google Drive + fallback local), motor de normalización de esquema y renderizado WebGL reactivo.
- **Justificación YAGNI**: Se descarta introducir bases de datos externas (PostgreSQL/PostGIS), backends intermedios (FastAPI) o motores de mapas basados en DOM (`folium`/`streamlit-folium`) que colapsan al superar ~3.000 nodos HTML. Se utiliza procesamiento vectorizado en memoria con `@st.cache_data` y renderizado GPU directo vía `pydeck` (`st.pydeck_chart`), más una única capa adaptadora (`src/normalizer.py`) estrictamente necesaria para reconciliar las diferencias reales de columnas entre los CSV de Google Drive y los CSV locales.

## What Changes

- **Aplicación Streamlit Entrypoint (`app.py`)**: Interfaz Split-Screen estilo portal inmobiliario (`65% Mapa PyDeck` | `35% Panel de Tarjetas Paginadas e Inspector de Propiedad`), con barra superior de 1 fila (selector de perfil `FAMILIA` / `SOLTERO_EJECUTIVO`, filtros rápidos de semáforo de precio, toggle de modo de color `Precio` vs. `Recomendación`, y 3 KPIs ejecutivos).
- **Conector Resiliente a Google Drive + Fallback Local (`src/data_loader.py`)**: Selección automática del archivo mensual más reciente `alquileres_caba_enriquecido_YYYY_MM.csv` desde la carpeta `01_mensual_enriquecido` de Google Drive (vía Service Account o File ID/URL compartida en `st.secrets` / variables de entorno) con caché TTL y conmutación automática sin fallo a `data/fallback_data.csv` ante errores de red o ausencia de credenciales.
- **Adaptador y Normalizador de Esquema (`src/normalizer.py`)**: Reconciliación determinista entre el esquema de 29 columnas del Actor (`desvio_precio_pct`, `cluster_habitabilidad`, `score_soltero`, `calificacion_familia`, `calificacion_soltero`) y el esquema local (`pct_sobreprecio`, `cluster_id`, `score_soltero_ejecutivo`, `recomendacion_familia`, `recomendacion_soltero_ejecutivo`), validación de bounding box CABA (`latitud in [-34.71, -34.52]`, `longitud in [-58.54, -58.34]`), clasificación de semáforo bajo cortes estándar (`<= -5%` Bajo Precio, `-5% < x <= +10%` Precio Justo, `> +10%` Sobreprecio) y degradación elegante de filtros de amenities (`has_parrilla`, `has_pileta`, `has_gimnasio`, `has_sum_coworking`, `has_seguridad`, `has_balcon_terraza`, `has_cochera`, `apto_mascotas`).
- **Motor Cartográfico Escalable (`src/map_view.py`)**: Capas PyDeck (`ScatterplotLayer` con colores RGBA accesibles WCAG 2.2 y radio proporcional al score del perfil activo, más soporte para altas densidades) con selección interactiva y tooltips enriquecidos.
- **Aislamiento de Rama para Deployment (`requirements.txt`, `data/fallback_data.csv`)**: Limpieza en esta rama de artefactos pesados de etapas previas (`apuntes/`, `Datasets/Originales/`, notebooks y directorios de entrenamiento no requeridos en producción) para garantizar un despliegue liviano y directo desde la raíz.

## Assumptions Eradication (Hechos Empíricos Verificados)

1. **`producto2/resultados_inferencia_caba.csv`** contiene `964` registros con `pct_sobreprecio`, `score_familia`, `recomendacion_familia`, `score_soltero_ejecutivo`, `recomendacion_soltero_ejecutivo`, pero **no** contiene `latitud`, `longitud` ni las banderas booleanas `has_*`.
2. **`producto1/dataset_enriquecido_completo.csv`** contiene las `964` propiedades con `listing_id`, `latitud`, `longitud`, `barrio`, `subzona`, `cocheras`, `apto_mascotas` y las 7 banderas booleanas de amenities (`has_gimnasio`, `has_pileta`, `has_parrilla`, `has_sum_coworking`, `has_seguridad`, `has_balcon_terraza`, `has_cochera`).
3. **`actor/src/pipeline.py`** y **`docs/README_DEPLOYMENT_N8N.md`** demuestran que el CSV mensual subido a Google Drive (`alquileres_caba_enriquecido_YYYY_MM.csv`) nombra el sobreprecio como `desvio_precio_pct`, las recomendaciones como `calificacion_familia` / `calificacion_soltero`, el score soltero como `score_soltero`, e incluye `apto_mascotas`, `cocheras` y `score_amenities` pero omite los booleanos `has_parrilla`, `has_pileta`, etc.
4. La evaluación empírica de los cortes estándar sobre las `964` propiedades arroja `363` (`37.7%`) en Bajo Precio (`<= -5%`, capturando el `100%` de las `22` propiedades `ALTAMENTE RECOMENDADA`), `385` (`39.9%`) en Precio Justo (`-5% a +10%`) y `216` (`22.4%`) en Sobreprecio (`> +10%`, capturando el `100%` de las `103` propiedades `DESCARTAR / SOBREPRECIO ALTO`).

## Non-Goals

- No se reentrenarán modelos K-Means ni XGBoost dentro del dashboard de Streamlit.
- No se modificará la lógica interna del Actor de Apify ni los flujos JSON de n8n (resguardados en `main`).
- No se utilizará `folium` / `streamlit-folium` debido a su límite de escalabilidad DOM frente a la meta de soportar decenas de miles de registros.
- No se implementará edición ni escritura hacia Google Drive (acceso estrictamente de solo lectura).

## Capabilities

### New Capabilities
- `interactive-property-map-dashboard`: Dashboard geoespacial interactivo en Streamlit con PyDeck WebGL, ingesta resiliente desde Google Drive del corte mensual más reciente con fallback local, normalización de esquema, filtrado multi-feature y codificación visual dual por perfil (`FAMILIA` / `SOLTERO_EJECUTIVO`) y semáforo de precios.

### Modified Capabilities
<!-- Ninguna capacidad existente modifica sus requisitos a nivel de especificación -->

## Impact

- **Rendimiento y Escalabilidad**: Filtrado vectorizado en Pandas (`< 50 ms` para `10.000` registros; `< 150 ms` para `50.000` registros), almacenamiento en caché en memoria (`@st.cache_data`) y renderizado WebGL en GPU vía PyDeck + paginación estricta de tarjetas en el DOM (`12` tarjetas por página).
- **Contratos Públicos y Compatibilidad**: Compatible hacia atrás tanto con el CSV de 29 columnas exportado por el Actor hacia Google Drive como con el dataset consolidado local (`producto1` + `producto2`).
- **Dependencias (`requirements.txt`)**: `streamlit`, `pydeck`, `pandas`, `numpy`, `requests`, `google-api-python-client`, `google-auth` (y `pytest` para la suite de verificación automatizada).
- **Estructura de Rama**: La rama `interactive_property_map_dashboard` queda dedicada exclusivamente al despliegue del dashboard y su suite de pruebas deterministas.
