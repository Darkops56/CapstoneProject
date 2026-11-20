# Proposal: Crime Heatmap Layer & Executive Analytics Showcase Notebook

**Complexity Tier:** `Tier M` (Feature multi-módulo: capa WebGL toggleable en dashboard Streamlit/PyDeck + columna aditiva en actor de inferencia + notebook ejecutivo end-to-end).  
**Justificación YAGNI:** No requiere servicios externos, bases de datos nuevas, fuentes locales en el dashboard ni dependencias adicionales de Python. Reutiliza el CSV mensual ya consumido desde Google Drive (`densidad_delitos_500m` e `indice_gravedad_delitos_500m`) y las librerías ya instaladas (`pydeck`, `matplotlib`, `seaborn`, `scipy`, `xgboost`, `scikit-learn`).

---

## Why

El Observatorio Inmobiliario CABA ya cuenta con un dashboard cartográfico en Streamlit/PyDeck y pipelines separados de ETL, EDA y MLOps, pero carece de dos piezas de alto impacto para toma de decisiones y presentación final:
1. **Capa espacial de riesgo delictivo en el dashboard:** hoy el mapa solo muestra puntos de propiedades (`ScatterplotLayer`), impidiendo visualizar de un vistazo qué zonas de CABA concentran mayor volumen o gravedad de delitos mediante un mapa de calor en escala roja toggleable.
2. **Notebook ejecutivo de muestra (`.ipynb`):** el conocimiento analítico (Q1–Q5, auditoría ETL, pruebas de hipótesis H1–H6, selección VIF, clustering K-Means, XGBoost + SHAP y MLOps Registry) está disperso entre `docs/architecture/*.md` y tres notebooks técnicos separados, sin un único artefacto narrativo ejecutable de muestra con gráficos avanzados consolidados.

---

## What Changes

1. **Enriquecimiento de gravedad delictiva en el Actor (`actor/src/pipeline.py`):**
   - Calcular y exportar la columna aditiva `indice_gravedad_delitos_500m` reutilizando `del_neighbors` y `del_bundle["peso_gravedad"]` ya cargados en memoria desde `actor/reference_geo/delitos_tree.joblib` (costo adicional ~0 ms).
2. **Capa Heatmap de Delitos Toggleable en el Dashboard (`dashboard/`):**
   - **Normalizador (`dashboard/src/normalizer.py`):** pre-calcular dentro de `@st.cache_data` los pesos normalizados `[0, 1]` con recorte en percentil 95 (`crime_weight_vol`, `crime_weight_grav`) y exponer el estado de disponibilidad (`crime_heatmap_status`: `INFO_CRIME_FULL_AVAILABLE`, `INFO_CRIME_GRAVITY_UNAVAILABLE`, `INFO_CRIME_HEATMAP_UNAVAILABLE`).
   - **Controles superiores (`dashboard/src/ui_components.py`):** agregar en la barra superior el toggle `Mapa de Calor: Delitos` (apagado por defecto) y, cuando está activo, selector de métrica (`Volumen` / `Gravedad`) con degradación elegante ante CSVs históricos de Drive sin `indice_gravedad_delitos_500m`.
   - **Motor PyDeck (`dashboard/src/map_view.py` + `dashboard/src/config.py` + `dashboard/app.py`):** renderizar `HeatmapLayer` en rampa roja (`pickable=False`, proyección slim de 3 columnas `["longitud", "latitud", weight_col]` tomada de `clean_df` para mantener estable la geografía delictiva frente a filtros de deptos) debajo de `ScatterplotLayer` (`id="ScatterplotLayer"`, `pickable=True`, `stroked=True` para contraste rojo-sobre-rojo).
3. **Notebook Showcase Ejecutivo End-to-End (`notebooks/observatorio_caba_showcase.ipynb`):**
   - Crear y ejecutar un notebook maestro autocontenido que responda Q1–Q5, sintetice la evidencia de `docs/architecture/00..04` y `docs/business_questions.md`, e incluya gráficos avanzados de alta calidad (distribuciones + tests H1–H6 anotados, análisis espacial de delitos/ruido/subte, profiling de los 5 clústeres K-Means, diagnóstico de residuales XGBoost + TreeSHAP nativo vía `pred_contribs=True`, simulación de ahorro para RR.HH. y resumen del Model Registry MLOps `v1`).
4. **Tests Deterministas y Evidencia:**
   - Ampliar `dashboard/tests/test_dashboard.py`, `tests/test_apify_actor.py` y agregar `tests/test_showcase_notebook.py` para validar los contratos Gherkin y la ejecución determinista del notebook.

---

## Capabilities

### New Capabilities
- `crime-heatmap-and-showcase`: Capa WebGL toggleable de mapa de calor delictivo (Volumen y Gravedad con degradación elegante y proyección slim de bajo payload) en el dashboard Streamlit/PyDeck, columna aditiva `indice_gravedad_delitos_500m` en el Actor, y notebook ejecutivo end-to-end `notebooks/observatorio_caba_showcase.ipynb`.

### Modified Capabilities
<!-- Ninguna capacidad existente cambia sus requisitos previos; los cambios son estrictamente aditivos y retrocompatibles. -->

---

## Impact

- **Archivos inspeccionados que respaldan el cambio:**
  - `dashboard/app.py`, `dashboard/src/map_view.py`, `dashboard/src/normalizer.py`, `dashboard/src/ui_components.py`, `dashboard/src/config.py`, `dashboard/src/data_loader.py`
  - `actor/src/pipeline.py`, `actor/reference_geo/delitos_tree.joblib`
  - `docs/architecture/00_INDICE_Y_ARQUITECTURA.md`, `02_EDA_ESTADISTICO_Y_SELECCION_FEATURES.md`, `03_MODELADO_KMEANS_XGBOOST_Y_SHAP.md`, `docs/business_questions.md`, `mlops/registry.json`
  - `Datasets/Curados/delitos_2022_curado.csv`, `etl/output/dataset_enriquecido_completo.csv`, `mlops/resultados_inferencia_caba.csv`
- **Rendimiento (benchmark empírico sobre 964 filas × 53 columnas):**
  - Toggle OFF (default al iniciar la app): **0 ms / 0 KB** de overhead.
  - Normalización de pesos (1 sola vez dentro de `@st.cache_data`): **~1.6 ms**.
  - Toggle ON con proyección slim de 3 columnas (`lon`, `lat`, `weight`): **~3.4 ms** y **~101.7 KB** de payload JSON (reducción del **94.5%** respecto a pasar el DataFrame completo de `1,841.3 KB`).
  - Notebook `.ipynb`: **0 ms / 0 KB** en runtime del dashboard.
- **Contratos públicos y compatibilidad hacia atrás:**
  - `build_pydeck_chart(...)` y `render_header_and_controls(...)` agregan parámetros opcionales con defaults seguros (`show_crime_heatmap=False`, `crime_metric="VOLUMEN"`, `heatmap_df=None`), manteniendo 100% compatibilidad con las llamadas y los 50 tests existentes.
  - Política Drive-only del dashboard intacta (cero archivos locales).
  - Cero dependencias nuevas en `requirements.txt` y `dashboard/requirements.txt` (Cuarentena de Dependencias respetada).

---

## Non-Goals

- No cargar los 138,528 registros crudos de `Datasets/Curados/delitos_2022_curado.csv` dentro del dashboard ni romper la política Drive-only de `dashboard/src/data_loader.py`.
- No instalar paquetes externos nuevos (`plotly`, `folium`, `shap`, `statsmodels`, `nbconvert`).
- No modificar los hiperparámetros ni reentrenar los modelos serializados `v1` en `mlops/artifacts/` o `actor/artifacts/`.
- No alterar los workflows de n8n ni el esquema de Google Drive API Key introducido en cambios previos.

---

## Assumptions Eradication (Hechos Empíricos Verificados)

1. `actor/reference_geo/delitos_tree.joblib` **ya contiene** exactamente las claves `['tree', 'cantidad', 'peso_gravedad']` con arrays de forma `(138528,)`.
2. `actor/src/pipeline.py` actualmente escribe `densidad_delitos_500m` pero omite `indice_gravedad_delitos_500m`; CSVs previos ya subidos a Google Drive pueden carecer de `indice_gravedad_delitos_500m`.
3. El entorno Python actual cuenta con `matplotlib 3.11.2`, `seaborn 0.13.2`, `scipy 1.18.1`, `scikit-learn 1.9.1`, `xgboost 3.4.1` (soporta TreeSHAP exacto vía `pred_contribs=True`), `pydeck 0.9.3` y `streamlit 1.67.0`.
4. `dashboard/app.py` captura selección de propiedades leyendo `pydeck_event.selection.get("indices", {}).get("ScatterplotLayer", [])`, por lo que `ScatterplotLayer` debe conservar su `id` y `HeatmapLayer` debe declararse con `pickable=False`.
5. La suite actual cuenta con **50 tests** recolectados por `pytest`.
