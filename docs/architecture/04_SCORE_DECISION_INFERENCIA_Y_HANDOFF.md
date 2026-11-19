# 04 · Score de Decisión (0–100), Inferencia, Tests TDD y Handoff

## 1. Fórmula Matemática del Score de Decisión (`0–100`)
Implementada en `producto2/inference.py` (`compute_decision_score`), combina **oportunidad económica** y **adecuación al perfil del empleado** (`FAMILIA` vs. `SOLTERO_EJECUTIVO`), acotada estrictamente a `[0, 100]`:

$$\text{Score} = \text{clip}\big(\text{Score}_{\text{Económico}} + \text{Score}_{\text{Clúster}} + \text{Score}_{\text{Perfil}},\ 0,\ 100\big)$$

1. **Componente Económico (0 a 40 puntos):**
   - Calcula $\text{pct\_ahorro} = \frac{\text{precio\_justo\_ars} - \text{costo\_publicado\_ars}}{\text{precio\_justo\_ars}} \times 100$.
   - Se recorta en `[-25%, +25%]`: $\text{Score}_{\text{Económico}} = \frac{\text{clip}(\text{pct\_ahorro}, -25, 25) + 25}{50} \times 40$.
   - A precio justo (`0%`): `20 pts`. Con `>= 25%` de ahorro: `40 pts`. Con `>= 25%` de sobreprecio: `0 pts`.
2. **Componente Clúster de Habitabilidad (0 a 25 puntos):**
   - Para **`FAMILIA`**: `"Zona Familiar Tranquila"` = `25 pts`, `"Hub Ejecutivo Conectado"` / `"Zona Urbana Conectada"` / `"Zona Residencial Equilibrada"` = `16 pts`, `"Zona Ruidosa/Alta Densidad"` = `8 pts`.
   - Para **`SOLTERO_EJECUTIVO`**: `"Hub Ejecutivo Conectado"` / `"Zona Urbana Conectada"` = `25 pts`, zonas tranquilas/equilibradas = `16 pts`, `"Zona Ruidosa/Alta Densidad"` = `10 pts`.
3. **Componente Atributos del Perfil (0 a 35 puntos):**
   - **`FAMILIA`**: prioriza amplitud (`ambientes`, hasta `10 pts`), `score_amenities` (`7 pts`), `apto_mascotas` (`6 pts`), `cocheras` (`5 pts`), calma acústica (`ruido_db_promedio`, `4 pts`) y cercanía escolar (`distancia_escuela_m`, `3 pts`).
   - **`SOLTERO_EJECUTIVO`**: prioriza `score_amenities` (`12 pts`), conectividad de subte (`lineas_subte_600m`, `11 pts`), tipología ágil 1–3 amb. (`6 pts`), `apto_mascotas` (`4 pts`) y `cocheras` (`2 pts`).

### Regla de Recomendación Automática
- **`ALTAMENTE RECOMENDADA`**: `score >= 75` y `pct_sobreprecio <= 5%`
- **`RECOMENDADA`**: `score >= 55` y `pct_sobreprecio <= 15%`
- **`DESCARTAR / SOBREPRECIO ALTO`**: `pct_sobreprecio > 20%`
- **`EVALUAR / ALTERNATIVA`**: resto de los casos

Sobre las `964` propiedades evaluadas en `producto2/resultados_inferencia_caba.csv`:
- **`224` oportunidades** con ahorro `>= 10%` respecto al precio justo teórico.
- **`216` propiedades** con sobreprecio `>= 10%`.
- Score promedio: `48.62` (`FAMILIA`) y `50.21` (`SOLTERO_EJECUTIVO`).

---

## 2. Artefactos `.joblib` y Uso del Módulo `inference.py`
Dentro de `producto2/artifacts/`:
- `kmeans_model.joblib`: `Pipeline(StandardScaler -> KMeans(k=5))`
- `xgb_price_model.joblib`: `TransformedTargetRegressor(XGBRegressor)` entrenado sobre el 100% de los datos curados tras validar en CV.
- `model_metadata.joblib`: diccionario con `regression_features`, `cluster_features`, `cluster_labels` y `target_col`.

Funciones expuestas en `producto2/inference.py`:
- `predict_property(features_dict, profile="FAMILIA", precio_publicado_ars=None)` → devuelve un diccionario con `cluster_id`, `cluster_label`, `precio_justo_ars`, `pct_sobreprecio`, `pct_ahorro`, `decision_score_0_100` y `recomendacion`.
- `predict_batch(df, profile="FAMILIA", published_price_col="costo_total_ars")` → procesa un DataFrame completo de propiedades en milisegundos sin reentrenar.

---

## 3. Calidad de Software: Suite TDD (`pytest`)
Siguiendo la metodología **TDD (Clase 43)**, se escribieron **11 tests automatizados** (`tests/test_etl_and_eda.py` + `tests/test_producto2.py`) que validan:
1. Normalización decimal de coordenadas desplazadas de delitos.
2. Conversión monetaria ARS/USD con parámetros configurables.
3. Extracción de expensas estructuradas, `"expensas incluidas"` y regex post-palabra.
4. Prioridad de negación NLP sobre etiquetas positivas de mascotas.
5. Cálculo de `score_amenities` diferenciado por perfil.
6. Reproyección CRS local CABA → `EPSG:4326` en establecimientos educativos.
7. Spatial join `within` + fallback `sjoin_nearest` en polígonos de ruido.
8. Contrato de `producto1_dataset_curado.csv` (`<= 10` features, 0 nulos, `VIF < 10`) y `eda_stats.json`.
9. Existencia y validez geográfica de los 5 `.csv` en `Datasets/Curados/`.
10. Monotonicidad y acotamiento `[0, 100]` del Score de Decisión.
11. Carga de `.joblib` e inferencia end-to-end individual y batch.

Resultado verificado: **11/11 tests aprobados (`pytest tests/ -v`)**.

---

## 4. Guía de Handoff para el Solutions Engineer (Apify + Make/n8n)
- **Operación `"analytics"` (Producto 1):** usar `config/settings.py`, `etl/etl_pipeline.py` y `eda/eda_phase2.py` (o consumir directamente `producto1/eda_stats.json` y `producto1/producto1_dataset_curado.csv`).
- **Operación `"inference"` (Producto 2):**
  1. Tomar propiedades nuevas scrapeadas por Apify.
  2. Enriquecerlas con `etl/etl_pipeline.py` contra las 4 capas livianas de `Datasets/Curados/` (`medicion_ruido_curado.csv`, `delitos_2022_curado.csv`, `establecimientos_educativos_curado.csv`, `bocas_de_subte_curado.csv`).
  3. Invocar `producto2/inference.py` (`predict_batch` / `predict_property`) pasando los `.joblib` de `producto2/artifacts/`.
  4. Devolver el JSON resultante a Make/n8n y al Insights Dashboard.
