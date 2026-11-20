# Evidence Report: Crime Heatmap Layer & Executive Analytics Showcase Notebook

**Change:** `crime-heatmap-and-analytics-showcase`  
**Tier:** `Tier M`  
**Date:** `2026-11-19`  
**Status:** `VERIFIED (Exit Code 0)`

---

## 1. Automated Verification Summary (`pytest`)

Full monorepo regression suite executed after final UI polish:

```text
Command: pytest -v
Result:  58 passed, 11 warnings in 5.68s (Exit Code 0)
Final:   58 passed, 11 warnings in 5.92s (Exit Code 0)
```

### New Deterministic Tests Verified (+8 tests over baseline 50)
- `dashboard/tests/test_dashboard.py::test_crime_heatmap_full_available_and_p95_winsorization` — **PASSED** (`INFO_CRIME_FULL_AVAILABLE`, p95 saturation `>= 5%` in `[0.0, 1.0]`)
- `dashboard/tests/test_dashboard.py::test_crime_heatmap_historical_csv_gravity_unavailable` — **PASSED** (`INFO_CRIME_GRAVITY_UNAVAILABLE` graceful degradation)
- `dashboard/tests/test_dashboard.py::test_crime_heatmap_both_columns_missing` — **PASSED** (`INFO_CRIME_HEATMAP_UNAVAILABLE` without crash)
- `dashboard/tests/test_dashboard.py::test_crime_heatmap_zero_nan_and_negative_division_guard` — **PASSED** (zero division guard on `0.0`, `NaN`, negative, dirty strings)
- `dashboard/tests/test_dashboard.py::test_crime_heatmap_pydeck_layers_slim_payload_and_fallback` — **PASSED** (OFF=1 layer, ON=2 layers `[HeatmapLayer(pickable=False), ScatterplotLayer(id="ScatterplotLayer", pickable=True, stroked=True)]`, 3-column slim payload `<= 250 KB`, `clean_df` 964 rows preserved under filtering, `GRAVEDAD` -> `VOLUMEN` fallback)
- `tests/test_apify_actor.py::test_curate_and_enrich_exports_indice_gravedad_delitos_500m` — **PASSED** (`indice_gravedad_delitos_500m` float, 0 NaNs, `>= 0.0`)
- `tests/test_showcase_notebook.py::test_showcase_notebook_exists_and_valid_schema` — **PASSED** (nbformat v4 JSON, 16 cells, zero forbidden imports)
- `tests/test_showcase_notebook.py::test_showcase_notebook_covers_business_questions_and_outputs` — **PASSED** (Q1–Q5, H1–H6, crime volume/gravity, K-Means, XGBoost + native `pred_contribs` TreeSHAP, `registry.json` v1, **7 embedded PNG figures**, 0 execution errors)

---

## 2. Performance & Payload Benchmark (964 rows × 53 cols)

| Metric | Naive Full DataFrame | Implemented Slim 3-Col + Cached Weights | Improvement |
| :--- | ---: | ---: | ---: |
| Initial Load Overhead (Toggle OFF) | 0 ms / 0 KB | **0 ms / 0 KB** | Zero regression |
| Weight Normalization (1× in `@st.cache_data`) | — | **1.60 ms** | Cached across reruns |
| HeatmapLayer Serialization (Toggle ON) | 25.90 ms | **3.41 ms** | **-86.8% CPU** |
| HeatmapLayer JSON WebSocket Payload | 1,841.3 KB | **101.7 KB** | **-94.5% payload** |

---

## 3. Browser Subagent Visual Verification (Zero Manual Testing)

Verified via headless browser subagent (`e29c1c16-78e6-4f63-8630-c7ab236e0442`) against local Streamlit instance (`http://127.0.0.1:18501`) fed with enriched 964-row CSV via `GDRIVE_CSV_URL`:
- **Host-verified origin:** `http://127.0.0.1:18501` (`blocked_origins: none`).
- **Initial Load (OFF):** Toggle `"🔥 Mapa de Calor: Delitos"` visible and unchecked (`checked === false`); `[data-testid="crime-heatmap-legend"]` absent (`count === 0`); 0 Streamlit exceptions/alerts.
- **Toggle ON (`Volumen`):** Radio selector (`Volumen` / `Gravedad`) appeared; `[data-testid="crime-heatmap-legend"]` displayed `"🔥 Volumen de delitos (500 m): Menor ... Mayor (p95+)"` and red WebGL heatmap rendered under stroked property markers.
- **Metric Switch (`Gravedad`):** Legend updated to `"🔥 Gravedad ponderada de delitos (500 m): Menor ... Mayor (p95+)"`; `[data-testid="pydeck-map-container"]` remained visible with active red heatmap blobs and crisp stroked property markers.
- **UI Polish Applied Post-Inspection:** Visual inspection of host-verified screenshot detected slight horizontal cramping when placing 5 columns in a single top row; refactored top bar in `dashboard/src/ui_components.py` into a spacious 4-column top row + dedicated slim heatmap control strip right below it (preserving all `data-testid` hooks and 58/58 green tests).

---

## 4. Deliverables Produced / Modified

- `actor/src/pipeline.py` — Exports `indice_gravedad_delitos_500m` reusing `del_neighbors` & `del_bundle["peso_gravedad"]`.
- `dashboard/src/config.py` — ColorBrewer Reds palette, WebGL heatmap parameters, and scatter stroke color.
- `dashboard/src/normalizer.py` — `compute_crime_weights` with p95 winsorization, zero-division guard, and canonical `crime_heatmap_status`.
- `dashboard/src/map_view.py` — Conditional slim 3-column `HeatmapLayer` (`pickable=False`) under stroked `ScatterplotLayer` (`id="ScatterplotLayer"`).
- `dashboard/src/ui_components.py` & `dashboard/app.py` — Top-bar toggle, `Volumen`/`Gravedad` selector, chromatic legend, and `heatmap_df=clean_df`.
- `notebooks/observatorio_caba_showcase.ipynb` — Executed 16-cell executive showcase notebook with 7 embedded high-resolution figures and zero new dependencies.
- `dashboard/tests/test_dashboard.py`, `tests/test_apify_actor.py`, `tests/test_showcase_notebook.py` — Full deterministic test coverage.
