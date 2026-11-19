## Context

Ver `proposal.md - Why` para la motivación de negocio y `specs/interactive-property-map-dashboard/spec.md` para los contratos normativos Gherkin.

El sistema debe operar en una rama limpia (`interactive_property_map_dashboard`) dedicada exclusivamente al dashboard de Streamlit para despliegue directo (por ejemplo en Streamlit Community Cloud o contenedor ligero), consumiendo el CSV mensual más reciente de Google Drive (`01_mensual_enriquecido/alquileres_caba_enriquecido_YYYY_MM.csv`) o conmutando sin fricción a un dataset local consolidado (`data/fallback_data.csv`, generado a partir del cruce por `listing_id` de `producto1/dataset_enriquecido_completo.csv` y `producto2/resultados_inferencia_caba.csv`). Aunque hoy existen `964` registros, el diseño debe escalar sin rediseño arquitectónico a `10.000`–`50.000+` registros.

## Goals / Non-Goals

**Goals:**
- Garantizar renderizado cartográfico fluido (`60 FPS` en navegador) y filtrado en memoria `< 50 ms` (`10k` filas) / `< 150 ms` (`50k` filas).
- Proveer una interfaz Split-Screen estilo Zonaprop limpia, intuitiva y no saturada mediante divulgación progresiva (Progressive Disclosure) y cumplimiento de accesibilidad WCAG 2.2 (color + símbolo + etiqueta textual).
- Soportar ingesta dual desde Google Drive (Service Account API para listado de carpeta `01_mensual_enriquecido` + descarga por File ID/URL compartida) con Circuit Breaker y fallback local determinista.
- Mantener el Principio de No-Colapso Semántico en todas las fronteras mediante discriminadores causales `{ tipo, razon }`.

**Non-Goals:**
- Ejecutar inferencia ML (`kmeans_model.joblib` / `xgb_price_model.joblib`) en vivo en cada request de UI (los scores y precios justos ya vienen precalculados en el CSV mensual).
- Conservar en esta rama archivos históricos ajenos al despliegue del dashboard (`apuntes/`, `Datasets/Originales/`, notebooks de entrenamiento, etc., que permanecen intactos en `main`).

## Decisions

### 1. Motor Cartográfico: PyDeck (`st.pydeck_chart` / Deck.gl WebGL) vs. Folium vs. Plotly
- **Decisión**: Utilizar **PyDeck (`ScatterplotLayer` WebGL)** con mapa base `Carto Positron` (`https://basemaps.cartocdn.com/gl/positron-gl-style/style.json`, que no requiere token propietario de Mapbox para renderizar teselas vectoriales limpias).
- **Alternativas descartadas**:
  - `folium` (`streamlit-folium`): serializa cada marcador como nodo DOM/HTML dentro de un `iframe`; a partir de `~3.000` puntos el payload supera `10 MB` y congela el hilo principal del navegador.
  - `plotly` (`scatter_map`): aunque usa WebGL, tiene menor control estético sobre radios en metros reales, bordes concéntricos por score y superposición de capas a gran escala que Deck.gl.
- **Justificación de Escalabilidad (para el informe del proyecto)**: Deck.gl transfiere arrays tipados binarios a buffers de GPU, permitiendo actualizar `50.000+` puntos con color RGBA y radio dinámico sin sobrecargar el DOM.

### 2. Arquitectura UX/UI: Split-Screen con Divulgación Progresiva y Doble Codificación Visual
- **Decisión**:
  1. **Barra Superior de Control (1 fila)**:
     - Selector de Perfil (`FAMILIA` | `SOLTERO_EJECUTIVO`).
     - Filtro rápido de Semáforo de Precio: **3 checkboxes horizontales directos** (`[X] 🟢 Oportunidad (≤ -5%)`, `[X] 🟡 Precio Justo (-5% a +10%)`, `[X] 🔴 Sobreprecio (> +10%)`) reemplazando el multiselect para agilizar la interacción.
     - Selector de modo de coloración (`Colorear por: Precio | Recomendación del Perfil`).
     - 3 KPIs esenciales: `Propiedades Visibles`, `Mediana Costo Total (ARS)` y `% Oportunidades (Bajo Precio)`.
     - Inyección de CSS compacto (`.block-container { padding-top: 1.5rem !important; }`) para erradicar el margen superior vacío nativo de Streamlit.
  2. **Sidebar Colapsable en 2 Niveles**:
     - *Nivel Primario (visible)*: Rango de presupuesto (`costo_total_ars`), Barrios (`multiselect`), Ambientes mínimos/rango, y checkboxes rápidos de features (`apto_mascotas`, `cocheras >= 1`, más `has_parrilla`, `has_pileta`, `has_gimnasio`, `has_seguridad`, `has_balcon_terraza`, `has_sum_coworking` cuando estén presentes en el dataset).
     - *Nivel Secundario (`st.expander("Filtros de Entorno y Habitabilidad", expanded=False)`)*: `score_amenities` mínimo, `ruido_db_promedio` máximo, `lineas_subte_600m` mínimo, `distancia_escuela_m` máxima y `cluster_label`.
  3. **Cuerpo Principal Split-Screen (`62% Mapa PyDeck` | `38% Panel Derecho Paginado / Inspector`)**:
     - **Layout Viewport-Locked**: El contenedor de tarjetas (`data-testid="property-cards-panel"`) posee `max-height: 680px; overflow-y: auto;` permitiendo desplazamiento vertical independiente de las propiedades sin scrollear la página completa ni perder la vista del mapa.
     - **Contraste Accesible Dark/Light Theme**: Tarjetas estilizadas con fondo oscuro refinado (`#1e293b` con borde `#334155`), tipografía blanca contrastada (`#f8fafc`) y precios destacados en cyan (`#38bdf8`), eliminando textos blancos sobre fondo blanco en modo oscuro. Leyenda del mapa con fondo translúcido y texto legible.
     - **Formateo Precalculado en Tooltips de PyDeck**: Pre-cálculo en DataFrame de `costo_total_fmt`, `precio_justo_fmt`, `desvio_fmt` y `score_fmt` para que el interpolador JS de Deck.gl renderice números exactos sin nombres crudos de variables.
     - Cuando hay una propiedad seleccionada (por clic en el mapa o en una tarjeta), el panel derecho muestra la **Ficha Detallada** (comparativa Costo Publicado vs. Precio Justo XGBoost, barra de Score 0–100 para el perfil activo, métricas de entorno y badges de amenities).
     - Debajo (o en modo lista), se renderizan exactamente **`12` tarjetas por página** ordenadas por `active_score` descendente para evitar saturación visual y DOM bloat.

### 3. Ingesta desde Google Drive + Fallback Local (`src/data_loader.py`)
- **Decisión**: Jerarquía determinista de 3 niveles con caché `@st.cache_data(ttl=900, max_entries=4)`:
  1. **Nivel 1 (Carpeta de Google Drive vía Service Account)**: Si existe `gcp_service_account` y `gdrive_folder_id` en `st.secrets` o variables de entorno, consulta `files.list` filtrando por `name contains 'alquileres_caba_enriquecido_'` y `trashed = false`, ordena por sufijo `YYYY_MM` descendente (y `modifiedTime desc` como desempate) y descarga el archivo más reciente con timeout estricto de `10 s`.
  2. **Nivel 2 (File ID / URL directa de Google Drive)**: Si existe `GDRIVE_FILE_ID` o `GDRIVE_CSV_URL`, descarga vía endpoint directo `https://drive.google.com/uc?export=download&id=<FILE_ID>` con timeout de `10 s`.
  3. **Nivel 3 (Fallback Local Semilla)**: Carga `data/fallback_data.csv` (dataset pre-unificado de las `964` propiedades con las 29 columnas del modelo más las 7 banderas `has_*` de `producto1`), emitiendo el discriminador `{ tipo: "DATA_LOADED", razon: "WARN_DRIVE_FALLBACK_ACTIVE" }`.

### 4. Normalización y Principio de No-Colapso Semántico (`src/normalizer.py`)
- **Decisión**: Toda transición en las fronteras de ingesta, validación y filtrado retorna una estructura tipada con discriminador causal `1:1`:

| Frontera | Estado Final (`tipo`) | Discriminador Causal (`razon`) | Condición Disparadora | Acción en UI |
| :--- | :--- | :--- | :--- | :--- |
| **Ingesta** | `SOURCE_READY` | `SOURCE_GDRIVE_LATEST` | Descarga HTTP 200 del CSV mensual más reciente en Drive | Badge verde: `"Fuente: Google Drive (YYYY-MM)"` |
| **Ingesta** | `SOURCE_READY` | `WARN_DRIVE_NOT_CONFIGURED` | Sin credenciales/ID de Drive configurados | Badge neutro: `"Fuente: Dataset Local (Offline)"` |
| **Ingesta** | `SOURCE_READY` | `WARN_DRIVE_TIMEOUT` | Timeout `> 10 s` al conectar con Google Drive | Toast de advertencia + carga de `fallback_data.csv` |
| **Ingesta** | `SOURCE_READY` | `WARN_DRIVE_HTTP_ERROR` | Error HTTP (`401/403/404/5xx`) o carpeta vacía en Drive | Toast de advertencia + carga de `fallback_data.csv` |
| **Validación** | `SCHEMA_INVALID` | `ERR_SCHEMA_MISSING_REQUIRED_COLUMNS` | Faltan columnas en `{listing_id, latitud, longitud, costo_total_ars, precio_justo_ars}` | Renderiza `data-testid="ui-state-error"` con columnas faltantes |
| **Validación** | `SCHEMA_INVALID` | `ERR_EMPTY_DATASET_AFTER_GEO_CLEAN` | `0` filas válidas tras filtrar bounding box CABA | Renderiza `data-testid="ui-state-error"` |
| **Normalización** | `SCHEMA_VALID` | `INFO_FULL_AMENITIES_AVAILABLE` | Presentes las columnas booleanas `has_parrilla`, `has_pileta`, etc. | Habilita todos los checkboxes de amenities |
| **Normalización** | `SCHEMA_VALID` | `INFO_GRANULAR_AMENITIES_UNAVAILABLE` | CSV de 29 columnas sin booleanos `has_*` | Muestra solo `apto_mascotas`, `cocheras` y `score_amenities` |
| **Filtrado UI** | `VIEW_EMPTY` | `EMPTY_FILTER_RESULTS` | Subconjunto filtrado `== 0` filas | Renderiza `data-testid="ui-state-empty"` + CTA Reset |
| **Filtrado UI** | `VIEW_SUCCESS` | `OK_RENDER_READY` | Subconjunto filtrado `>= 1` filas | Renderiza Mapa PyDeck + KPIs + Tarjetas paginadas |

## Protocolo Grill-Me Exhaustivo (14 Vectores de Falla Crítica)

1. **V1 — Timeout o caída de API de Google Drive**: Timeout explícito de `10.0 s` (`REQUEST_TIMEOUT_SECONDS = 10.0`). Al expirar, captura `TimeoutError`/`RequestException` y conmuta a `data/fallback_data.csv` en `< 500 ms` con razón `WARN_DRIVE_TIMEOUT`.
2. **V2 — Credenciales de Drive expiradas o permisos `403 Forbidden`**: Captura controlada sin exponer secretos en pantalla ni en logs; conmuta a fallback local con `WARN_DRIVE_HTTP_ERROR`.
3. **V3 — Múltiples archivos mensuales desordenados en la carpeta de Drive**: El selector extrae regex `r"(\d{4})[_-](\d{2})"` del nombre de archivo, ordena por `(año, mes)` descendente y usa `modifiedTime` como desempate determinista.
4. **V4 — Deriva de nombres de columna entre CSV del Actor y CSV local**: Mapeo canónico bidireccional (`desvio_precio_pct -> pct_sobreprecio`, `cluster_habitabilidad -> cluster_id`, `score_soltero -> score_soltero_ejecutivo`, `calificacion_familia -> recomendacion_familia`, `calificacion_soltero -> recomendacion_soltero_ejecutivo`). Si `pct_sobreprecio` no viniera precalculado, se calcula como `((costo_total_ars - precio_justo_ars) / precio_justo_ars) * 100.0`.
5. **V5 — Ausencia de columnas booleanas `has_*` en CSV de 29 columnas de Drive**: Detección dinámica de capacidades (`available_amenity_flags`). Nunca se indexa `df["has_parrilla"]` sin verificar pertenencia; la UI desactiva limpiamente los filtros ausentes (`INFO_GRANULAR_AMENITIES_UNAVAILABLE`).
6. **V6 — Coordenadas corruptas, `NaN`, `(0, 0)` o invertidas (`lat`/`lon`)**: Coerción `pd.to_numeric(..., errors="coerce")` y filtro estricto de bounding box CABA (`-34.71 <= latitud <= -34.52` y `-58.54 <= longitud <= -58.34`), registrando descartes en `AUDIT_OUT_OF_BOUNDS_DROPPED`.
7. **V7 — División por cero en `precio_justo_ars <= 0`**: El normalizador recorta `precio_justo_ars` a `np.maximum(precio_justo_ars, 1.0)` antes de cualquier cálculo porcentual.
8. **V8 — Explosión del DOM por renderizado de miles de tarjetas en Streamlit**: Paginación dura (`PAGE_SIZE = 12`, justificado porque 12 tarjetas caben en el scroll lateral en menos de `250 KB` de HTML). Aunque el filtro devuelva `50.000` propiedades, el DOM solo instancia `12` tarjetas.
9. **V9 — Saturación de memoria por copias repetidas del DataFrame en sesiones concurrentes**: `@st.cache_data(ttl=900, max_entries=4)` comparte la referencia del DataFrame normalizado y el filtrado opera mediante máscaras booleanas vectorizadas de NumPy sin copiar cadenas innecesarias.
10. **V10 — Estado vacío (`0` resultados tras combinar filtros)**: Se intercepta `len(df_filtered) == 0` antes de invocar capas vacías confusas, mostrando `data-testid="ui-state-empty"` con diagnóstico de filtros activos y botón `data-testid="reset-filters-btn"` que limpia `st.session_state`.
11. **V11 — Inaccesibilidad por daltonismo (rojo-verde)**: Paleta con contraste `>= 4.5:1` combinada con prefijos simbólicos obligatorios (`v Bajo Precio`, `= Precio Justo`, `^ Sobreprecio`) y variación de radio por score (`[35m, 110m]`).
12. **V12 — Desincronización de `st.session_state` al cambiar filtros con una página alta seleccionada (ej. Página 8 y luego filtrar a 5 resultados)**: Todo cambio en los filtros principales reajusta automáticamente `current_page = 1` si `current_page > total_pages`, y limpia `selected_listing_id` si la propiedad seleccionada ya no pertenece al subconjunto filtrado.
13. **V13 — Bloqueo de teselas de mapa por falta de `MAPBOX_API_KEY`**: Se fija explícitamente `map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"` (CartoDB Positron libre de API key) para que el mapa funcione en cualquier entorno local o cloud sin llaves de Mapbox.
14. **V14 — Ruptura en despliegue cloud por artefactos pesados o dependencias conflictivas en la rama**: Se limpia la rama dejando únicamente los módulos del dashboard, `data/fallback_data.csv`, `requirements.txt` acotado, `openspec/` y `tests/test_dashboard.py`.

## Impacto en Memoria, Latencia, Concurrencia y Observabilidad

- **Memoria**: `50.000` registros con `36` columnas ocupan `~14 MB` en RAM en Pandas. Con `max_entries=4` en `@st.cache_data`, el techo de caché es `< 60 MB`, apto para instancias gratuitas de Streamlit Cloud (`1 GB` RAM).
- **Latencia**:
  - Carga inicial en frío (fallback local): `< 150 ms`.
  - Carga inicial desde Drive (red): acotada por `REQUEST_TIMEOUT_SECONDS = 10.0 s`; lecturas subsecuentes desde caché: `< 5 ms`.
  - Filtrado vectorizado y cálculo de KPIs: `< 50 ms` para `10.000` filas; `< 150 ms` para `50.000` filas.
- **Concurrencia**: El estado de filtros, página actual y propiedad seleccionada se aísla estrictamente por sesión de usuario en `st.session_state`, mientras que el dataset normalizado de solo lectura se comparte en `@st.cache_data`.
- **Observabilidad**: Cada carga y transición expone el badge `data-testid="data-source-badge"` con el token causal (`SOURCE_GDRIVE_LATEST` o `WARN_DRIVE_FALLBACK_ACTIVE`) y un panel técnico desplegable con conteo de registros válidos, descartados por bounding box (`AUDIT_OUT_OF_BOUNDS_DROPPED`) y disponibilidad de columnas de amenities.

## Risks / Trade-offs

- **[Riesgo] Cuota o latencia de Google Drive en picos de tráfico** -> **Mitigación**: TTL de caché de `900 s` (15 minutos) para evitar golpear Drive en cada interacción o nuevo visitante, más fallback instantáneo a `data/fallback_data.csv`.
- **[Riesgo] CSV mensual futuro en Drive sin banderas individuales `has_parrilla` / `has_pileta`** -> **Mitigación**: Degradación elegante (`INFO_GRANULAR_AMENITIES_UNAVAILABLE`) que mantiene funcionales `apto_mascotas`, `cocheras` y el slider de `score_amenities`, mientras que `data/fallback_data.csv` ya incluye la unión completa con las 7 banderas `has_*`.

## Migration Plan

1. Generar `data/fallback_data.csv` uniendo de forma determinista por `listing_id` las `964` propiedades de `producto1/dataset_enriquecido_completo.csv` (coordenadas + amenities `has_*`) con `producto2/resultados_inferencia_caba.csv` (precios justos, sobreprecio, clusters y scores duales).
2. Limpiar de la rama `interactive_property_map_dashboard` los directorios y archivos heredados que no forman parte del despliegue del dashboard (preservados en `main`), dejando la raíz lista para despliegue directo con `app.py` y `requirements.txt`.
3. Ejecutar la suite determinista `pytest tests/test_dashboard.py` y la verificación autónoma en navegador con `browser_subagent`.
