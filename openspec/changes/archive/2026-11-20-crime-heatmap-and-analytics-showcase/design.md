# Design: Crime Heatmap Layer & Executive Analytics Showcase Notebook

## Context

Ver motivación en `proposal.md` y contrato de comportamiento en `specs/crime-heatmap-and-showcase/spec.md`.
El dashboard Streamlit (`dashboard/app.py`) consume únicamente el CSV mensual enriquecido desde Google Drive (`dashboard/src/data_loader.py` vía Drive API Key / URL directa) y renderiza propiedades sobre Carto Positron mediante un único `ScatterplotLayer` en PyDeck (`dashboard/src/map_view.py`). Por su parte, `actor/src/pipeline.py` ya carga `delitos_tree.joblib` (que contiene `tree`, `cantidad` y `peso_gravedad`), pero aún no escribe `indice_gravedad_delitos_500m` en el CSV exportado.

---

## Goals / Non-Goals

**Goals:**
- Renderizar un mapa de calor delictivo toggleable (Volumen y Gravedad) en escala roja sin penalizar la carga inicial (`0 ms / 0 KB` en estado OFF) y con payload acotado (`<= 110 KB` para ~1,000 puntos) en estado ON.
- Garantizar retrocompatibilidad 100% con CSVs históricos ya alojados en Google Drive mediante degradación elegante y tokens canónicos 1:1.
- Producir un notebook ejecutivo ejecutable y autocontenido (`notebooks/observatorio_caba_showcase.ipynb`) sin instalar dependencias nuevas.

**Non-Goals:**
- No agregar archivos locales de delitos al dashboard ni romper la política Drive-only.
- No reentrenar artefactos ML `v1` ni modificar el esquema de `mlops/registry.json`.

---

## Decisions

### 1. Proyección Slim de 3 Columnas + Caché de Pesos en `normalizer.py`
- **Decisión:** Pre-calcular `crime_weight_vol` y `crime_weight_grav` una sola vez dentro de `normalize_schema()` (ejecutado dentro de `@st.cache_data(ttl=900)`), y construir `HeatmapLayer` recibiendo únicamente un DataFrame proyectado de 3 columnas `["longitud", "latitud", weight_col]` con coordenadas redondeadas a 5 decimales (~1.1 m) y peso a 4 decimales. Si `len(heatmap_df) > 2000`, agrupar espacialmente por `(lat.round(4), lon.round(4))` (~11 m) promediando el peso.
- **Alternativa descartada:** Pasar `clean_df` completo (53 columnas) a `HeatmapLayer` → genera `1,841.3 KB` y `25.9 ms` por rerun vs. `101.7 KB` y `3.4 ms` con proyección slim (**-94.5% payload**).

### 2. Normalización Robusta con Winsorización en Percentil 95 (`p95`)
- **Decisión:** `w = np.clip(vals / p95, 0.0, 1.0)` cuando `p95 > 0`, o `0.0` si `p95 <= 0` (con coerción previa `pd.to_numeric(..., errors="coerce").fillna(0.0).clip(lower=0.0)`).
- **Justificación:** `densidad_delitos_500m` presenta asimetría positiva (`skew = 1.61`). Sin recorte en `p95`, los hotspots extremos (Microcentro/Constitución) comprimen el 90% de CABA hacia el extremo bajo de la paleta, haciendo invisible la variación intermedia.

### 3. Parámetros WebGL Justificados para `HeatmapLayer` y Contraste en `ScatterplotLayer`
- **`color_range` (rampa roja de 6 niveles en `dashboard/src/config.py`):**
  `[[255, 245, 240, 40], [254, 224, 210, 110], [252, 146, 114, 165], [251, 106, 74, 200], [222, 45, 38, 225], [165, 15, 21, 245]]` — progresión perceptualmente monótona (ColorBrewer Reds) con baja opacidad en zonas seguras para no ensuciar el mapa base Carto Positron y rojo intenso en zonas críticas.
- **`radius_pixels=55`, `intensity=1.2`, `threshold=0.05`, `opacity=0.6`:** calibrados para zoom inicial `11.6` sobre CABA (~15 km de ancho) con ~964 puntos; `radius_pixels=55` suaviza huecos entre manzanas sin diluir barrios enteros, `threshold=0.05` elimina ruido visual de fondo y `opacity=0.6` mantiene legibles calles y avenidas.
- **Orden y contraste de capas:** `layers = [heatmap_layer, scatter_layer]`. `HeatmapLayer` usa `pickable=False` para no interceptar clicks; `ScatterplotLayer` conserva `id="ScatterplotLayer"`, `pickable=True`, y habilita `stroked=True`, `get_line_color=[15, 23, 42, 210]`, `line_width_min_pixels=1` para que puntos rojos de *Sobreprecio* sigan diferenciándose sobre hotspots rojos.

### 4. Fuente del Heatmap Independiente de Filtros de Propiedades (`clean_df`)
- **Decisión:** `app.py` pasa `df=df_filtered` para los puntos y `heatmap_df=clean_df` para la capa de calor.
- **Alternativa descartada:** Usar `df_filtered` para ambos → al filtrar por criterios restrictivos (ej. 3 ambientes + mascotas + cochera = 10 propiedades), el mapa delictivo de CABA desaparecería y sesgaría visualmente la percepción de seguridad.

### 5. Notebook Ejecutivo Autocontenido sin Dependencias Nuevas
- **Decisión:** Implementar `notebooks/observatorio_caba_showcase.ipynb` usando exclusivamente `pandas`, `numpy`, `scipy`, `matplotlib`, `seaborn`, `scikit-learn`, `xgboost` (TreeSHAP exacto vía `booster.predict(dmat, pred_contribs=True)` sin paquete `shap`) y `pydeck`. Se genera y ejecuta vía script Python determinista que escribe outputs (`image/png` y texto) directamente en el JSON del `.ipynb` (evitando requerir `nbconvert`).

---

## Matriz de Mapeo de Frontera (No-Colapso Semántico)

Toda transición en la frontera `normalizer.py -> ui_components.py -> map_view.py` conserva un discriminador causal 1:1 `{ tipo, razon }`:

| Causa de Entrada | `meta["crime_heatmap_status"]` (`razon`) | `available_crime_metrics` | Comportamiento UI (`ui_components.py`) | Comportamiento Mapa (`map_view.py`) |
| :--- | :--- | :--- | :--- | :--- |
| Ambas columnas presentes (`densidad_delitos_500m`, `indice_gravedad_delitos_500m`) | `INFO_CRIME_FULL_AVAILABLE` | `["VOLUMEN", "GRAVEDAD"]` | Toggle habilitado + selector `Volumen` / `Gravedad` | Renderiza `HeatmapLayer` con métrica elegida |
| Solo `densidad_delitos_500m` presente (CSV histórico) | `INFO_CRIME_GRAVITY_UNAVAILABLE` | `["VOLUMEN"]` | Toggle habilitado en `Volumen` + badge `data-testid="crime-heatmap-status"` avisando gravedad no disponible | Si se solicita `GRAVEDAD`, degrada determinísticamente a `crime_weight_vol` |
| Solo `indice_gravedad_delitos_500m` presente | `INFO_CRIME_VOLUME_UNAVAILABLE` | `["GRAVEDAD"]` | Toggle habilitado en `Gravedad` + badge informativo | Si se solicita `VOLUMEN`, degrada determinísticamente a `crime_weight_grav` |
| Ninguna columna de delitos presente | `INFO_CRIME_HEATMAP_UNAVAILABLE` | `[]` | Toggle deshabilitado + badge `data-testid="crime-heatmap-status"` | Omite `HeatmapLayer`, retorna solo `[ScatterplotLayer]` |

---

## Protocolo Grill-Me Exhaustivo (12 Vectores de Falla Crítica)

| # | Vector de Falla | Riesgo | Mitigación Concreta |
|---|---|---|---|
| 1 | CSV histórico en Drive sin `indice_gravedad_delitos_500m` | `KeyError` al activar modo Gravedad | Detección explícita en `normalizer.py` + fallback a `crime_weight_vol` en `map_view.py` |
| 2 | CSV corrupto sin ninguna columna delictiva | Crash en `app.py` o `map_view.py` | Estado `INFO_CRIME_HEATMAP_UNAVAILABLE`, toggle deshabilitado y omisión segura de `HeatmapLayer` |
| 3 | Todos los delitos = `0.0` o `NaN` | `ZeroDivisionError` o `NaN` en pesos WebGL | Guard `p95 > 0.0`, coerción `fillna(0.0).clip(lower=0.0)` |
| 4 | Valores negativos o strings sucios (`"N/A"`) en CSV | Excepción al normalizar o serializar JSON | `pd.to_numeric(..., errors="coerce").fillna(0.0).clip(lower=0.0)` |
| 5 | Outliers extremos (`skew = 1.61`) | Toda la ciudad se ve plana excepto 1 esquina | Recorte winsorizado en percentil 95 (`p95`) |
| 6 | Payload WebSocket inflado al activar heatmap | Lag en cada interacción de sliders/filtros | Proyección slim de 3 columnas redondeadas (`-94.5%` payload: `101.7 KB`) |
| 7 | Crecimiento del dataset (>2,000 propiedades) | Degradación en serialización y GPU | Agrupación espacial por `(lat.round(4), lon.round(4))` si `len > 2000` |
| 8 | Interceptación de clicks por `HeatmapLayer` | Se rompe selección de propiedades en `app.py` | `HeatmapLayer(pickable=False)` debajo de `ScatterplotLayer(id="ScatterplotLayer", pickable=True)` |
| 9 | Puntos rojos de Sobreprecio invisibles sobre heatmap rojo | Pérdida de legibilidad WCAG 2.2 | `stroked=True` con borde oscuro de alto contraste (`[15, 23, 42, 210]`) en `ScatterplotLayer` |
| 10 | Filtros restrictivos vacían `df_filtered` o dejan 5 puntos | Mapa delictivo desaparece o distorsiona CABA | `heatmap_df=clean_df` desacoplado de `df_filtered` |
| 11 | Falta de `shap`/`plotly`/`nbconvert` al ejecutar notebook | Falla de importación o notebook sin gráficos | Uso exclusivo de `matplotlib`, `seaborn`, `scipy`, `xgboost` (`pred_contribs=True`) y runner Python puro |
| 12 | Rutas relativas rotas al abrir el notebook desde `notebooks/` vs raíz | `FileNotFoundError` en datasets/artefactos | Resolución robusta de `PROJECT_ROOT` buscando `config/settings.py` hacia arriba |

---

## Análisis de Impacto: Memoria, Latencia, Concurrencia y Observabilidad

- **Memoria:** 2 columnas `float64` adicionales en `clean_df` (~15 KB para 964 filas). La proyección slim en `map_view.py` ocupa ~23 KB efímeros.
- **Latencia:**
  - Carga inicial (`toggle=False`): **+1.6 ms** una única vez dentro de `@st.cache_data`; **0 ms** en reruns subsecuentes.
  - Rerun con `toggle=True`: **+3.4 ms** de serialización JSON + `< 5 ms` GPU WebGL.
- **Concurrencia:** `@st.cache_data(ttl=900, max_entries=4)` comparte `clean_df` entre sesiones concurrentes sin estado mutable global; `map_view.py` opera sobre copias slim sin mutar `clean_df`.
- **Observabilidad:** Tokens deterministas `crime_heatmap_status` en `norm_meta`, atributos `data-testid="crime-heatmap-toggle"`, `data-testid="crime-heatmap-legend"` y `data-testid="crime-heatmap-status"` verificables por tests automatizados y `browser_subagent`.

---

## Risks / Trade-offs & Rollback

- **Sesgo de muestreo espacial (A1):** Al basarse en `densidad_delitos_500m` / `indice_gravedad_delitos_500m` de propiedades publicadas, zonas sin avisos inmobiliarios (ej. parques o zonas industriales) no muestran calor. → *Mitigación:* documentado explícitamente en la leyenda del dashboard y contrastado con los 138,528 delitos completos de CABA en el Notebook Showcase B1.
- **Rollback:** Todos los cambios son aditivos con parámetros por defecto seguros; revertir el commit o poner `show_crime_heatmap=False` restaura el comportamiento previo sin migraciones de datos.
