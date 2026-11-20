# 03 · Modelado: K-Means, XGBoost Regressor, SHAP y Model Registry

Implementado en `src/mlops/train_models.py` y versionado mediante el Model Registry en `src/mlops/registry.py`.

---

## 1. Clustering de Habitabilidad (K-Means)
- **Variables de Entorno (5):** `ruido_db_promedio`, `densidad_delitos_500m`, `distancia_escuela_m`, `lineas_subte_600m`, `score_amenities`.
- **Preprocesamiento:** `StandardScaler` dentro de un `Pipeline` de scikit-learn (`kmeans_model.joblib`), indispensable para ecualizar magnitudes dispares.
- **Selección de $k$ óptimo:**
  - Evaluación de Inercia y Coeficiente de Silueta para $k \in [2, 6]$.
  - **$k=5$ seleccionado como óptimo:** Inercia `2170.53`, Silhouette `0.2343` (mayor Silhouette para $k \ge 3$ con separación nítida en el gráfico de codo).

### Perfil de los 5 Clústeres
Validados sobre `costo_total_ars` con **Kruskal-Wallis** ($H = 172.67, p = 2.79 \times 10^{-36}$):
- `Cluster 1`: **Zona Familiar Tranquila** (Ruido mediano 62.5 dBA, delitos bajos, alta afinidad escolar).
- `Cluster 2`: **Hub Ejecutivo Conectado** (Score amenities 8.5, edificios de alta gama).
- `Cluster 0`: **Zona Urbana Conectada** (Alta cercanía a subte, vida comercial activa).
- `Cluster 4`: **Zona Residencial Equilibrada** (Entornos de densidad media balanceados).
- `Cluster 3`: **Zona Ruidosa / Alta Densidad** (Ruido elevado, alta densidad delictiva, penalizado para familias).

---

## 2. Regresión de Precio Justo (XGBoost Regressor)
- **Transformación de Escala:**
  - Se utiliza `TransformedTargetRegressor(regressor=XGBRegressor(), func=np.log1p, inverse_func=np.expm1)`.
  - La asimetría severa del target ($4.36$) provocaría que el entrenamiento en escala lineal minimice el error a costa de sobredimensionar el peso de las propiedades de lujo. La escala logarítmica optimiza el error relativo porcentual (MAPE).
- **Esquema de Validación Cruzada:**
  - `RandomizedSearchCV` con 5-Fold Cross Validation (`KFold(n_splits=5, shuffle=True)`).
  - Hiperparámetros regulados (`max_depth=3`, `min_child_weight=5`, `subsample=0.75`) para prevenir sobreajuste.

### Métricas de Evaluación
| Métrica | Definición e Interpretación | Hold-out Test (20%) | 5-Fold CV OOF |
|---|---|---:|---:|
| **MAE** | Error absoluto medio en pesos argentinos. | \$331,223.19 | \$283,010.12 |
| **RMSE** | Penaliza desviaciones grandes en propiedades de alta gama. | \$682,586.24 | \$551,401.06 |
| **MAPE** | Error porcentual medio (métrica clave de negocio). | **15.20%** | **14.99%** |
| **$R^2$** | Varianza explicada del costo mensual. | **0.7775** | **0.7640** |

---

## 3. Gobernanza del Model Registry y Umbral de Regresión ($R^2$)

El módulo `src/mlops/registry.py` administra el ciclo de vida de los modelos en producción:

1. **Baseline Inicial (`v1`):**
   - El modelo fundacional `v1` fue entrenado con las 964 observaciones del dataset curado inicial, alcanzando un $R^2 = 0.7775$.
2. **Guarda de Calidad para Producción ($R^2 \ge 0.80$):**
   - Para los reentrenamientos periódicos anuales ejecutados por el Actor Trainer sobre el acumulador histórico (`04_historico_alquileres_anual`), el sistema exige un umbral estricto de **$R^2 \ge 0.80$**.
   - Si un modelo recién entrenado degrada su rendimiento por debajo de este límite, emite la excepción canónica `ERR_METRIC_REGRESSION` y aborta la promoción a producción.
3. **Idempotencia por Hash SHA-256:**
   - Previo al reentrenamiento, se calcula el hash SHA-256 del dataset. Si no hay registros nuevos respecto a la versión en producción, el sistema emite `SKIP_IDENTICAL_DATASET` evitando bumps redundantes.

---

## 4. Explicabilidad con SHAP
Mediante `shap.Explainer` se determinó la contribución marginal de cada variable:
- **Top 3 de Mayor Impacto:** `m2_totales` (magnitud dominante con mean $|SHAP| = 0.2158$), seguido de `score_amenities` ($0.0888$) y `banos` ($0.0490$).
- Las figuras explicativas (`03_shap_summary_beeswarm.png` y `04_shap_feature_importance_bar.png`) se encuentran persistidas en `src/mlops/figures/`.
