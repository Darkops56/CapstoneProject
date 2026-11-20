# 04 · Score de Decisión (0–100), Inferencia y Handoff Productivo

## 1. Algoritmo del Score de Decisión (`0–100`)
Implementado en `src/mlops/inference.py` y empaquetado herméticamente en `actors/inference/src/scoring.py`. Combina la oportunidad económica con la adecuación al perfil del empleado corporativo (`FAMILIA` vs. `SOLTERO_EJECUTIVO`):

$$\text{Score} = \text{clip}\big(\text{Score}_{\text{Económico}} + \text{Score}_{\text{Clúster}} + \text{Score}_{\text{Perfil}},\ 0,\ 100\big)$$

1. **Componente Económico (0 a 40 puntos):**
   - Evalúa el porcentaje de sobreprecio o ahorro frente al precio justo teórico:
     $$\text{pct\_ahorro} = \frac{\text{precio\_justo\_ars} - \text{costo\_publicado\_ars}}{\text{precio\_justo\_ars}} \times 100$$
   - Se recorta linealmente en el intervalo $[-25\%, +25\%]$. Con $\ge 25\%$ de ahorro obtiene 40 puntos; a precio justo (0%) obtiene 20 puntos; con $\ge 25\%$ de sobreprecio obtiene 0 puntos.
2. **Componente Clúster de Habitabilidad (0 a 25 puntos):**
   - Asigna puntaje según la afinidad del perfil al entorno urbano determinado por K-Means.
   - Para `FAMILIA`, "Zona Familiar Tranquila" otorga el puntaje máximo (25 pts), mientras que "Zona Ruidosa / Alta Densidad" penaliza con 8 pts.
   - Para `SOLTERO_EJECUTIVO`, "Hub Ejecutivo Conectado" y "Zona Urbana Conectada" otorgan el puntaje máximo (25 pts).
3. **Componente Atributos del Perfil (0 a 35 puntos):**
   - `FAMILIA`: Prioriza ambientes amplios ($\ge 3$ amb), comodidades familiares, aceptación de mascotas y cercanía a escuelas.
   - `SOLTERO_EJECUTIVO`: Prioriza conectividad con subte ($\le 600\text{ m}$), score de amenidades elevado (gimnasio, SUM/coworking) y tipologías ágiles.

### Reglas de Recomendación
- **`ALTAMENTE RECOMENDADA`**: `score >= 75` y `pct_sobreprecio <= 5%`
- **`RECOMENDADA`**: `score >= 55` y `pct_sobreprecio <= 15%`
- **`DESCARTAR / SOBREPRECIO ALTO`**: `pct_sobreprecio > 20%`
- **`EVALUAR / ALTERNATIVA`**: Resto de las observaciones.

---

## 2. Inferencia y Artefactos Versionados
Los binarios serializados residen en `src/mlops/artifacts/` y son desplegados en `actors/inference/artifacts/`:
- `kmeans_model.joblib`: Pipeline con preprocesamiento `StandardScaler` y estimador `KMeans(k=5)`.
- `xgb_price_model.joblib`: Modelo `TransformedTargetRegressor` de XGBoost entrenado para predicción de costos totales.
- `model_metadata.joblib`: Diccionario con la lista de 10 features, columnas de clustering y etiquetas de clústeres.

El módulo `src/mlops/inference.py` expone:
- `predict_property(features_dict, profile="FAMILIA", precio_publicado_ars=None)`
- `predict_batch(df, profile="FAMILIA", published_price_col="costo_total_ars")`

---

## 3. Calidad de Software y Suite de Pruebas Deterministas
El repositorio cuenta con un arnés unificado de **70 tests automatizados** (`pytest`):
- **Dashboard UI (`dashboard/tests/` — 19 tests):** Validaciones de filtros, normalizador defensivo de esquemas de Google Drive, componentes de interfaz y capas Deck.gl WebGL (Scatterplot, Column 3D y HeatmapLayer de Delitos).
- **Backend & MLOps (`tests/` — 51 tests):**
  - Inferencia end-to-end individual y batch desde `.joblib`.
  - Aislamiento hermético de `actors/inference/` sin dependencias externas.
  - Guarda de regresión de métricas ($R^2 \ge 0.80$) e idempotencia en Model Registry.
  - Reproyección de coordenadas y corrección de negaciones NLP en mascotas.
  - Invariantes semánticas de workflows n8n y contratos de notebooks en `notebooks/`.

Resultado verificado: **68 passed, 2 skipped** (omisiones controladas por ausencia opcional de datasets crudos locales) con **Exit Code 0**.

---

## 4. Handoff Productivo: Integración Cloud y Despliegue

La solución opera bajo un flujo desacoplado multi-cloud:

```
[ Ingesta Mensual Zonaprop ]
             │
             ▼
[ n8n: Orquestación & Circuit Breaker ]
             │
             ▼ Invoca vía API
[ Apify: actors/inference/ ]
  - Cruce con geo-caché embebido en reference_geo/
  - Carga modelos desde local o Apify Production KV Store
  - Exporta dataset enriquecido mensual
             │
             ▼
[ Google Drive: 01_mensual_enriquecido/ ]
  - Retención automática de los 3 meses más recientes
  - Acumulación inmutable en 04_historico_alquileres_anual
             │
             ▼ Consumo continuo
[ Streamlit Cloud: dashboard/app.py ]
  - Autodetección del último CSV mensual vía API Key
  - 100% libre de librerías de entrenamiento (arranque instantáneo)
```
