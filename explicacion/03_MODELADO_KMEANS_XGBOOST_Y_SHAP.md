# 03 · Modelado: K-Means, XGBoost Regressor y Explicabilidad SHAP (Fase 3)

Implementado en `producto2/train_models.py`, evaluado y registrado en `producto2/model_metrics.json`.

---

## 1. Clustering de Habitabilidad (K-Means)
- **Variables usadas (5):** `ruido_db_promedio`, `densidad_delitos_500m`, `distancia_escuela_m`, `lineas_subte_600m`, `score_amenities`.
- **Preprocesamiento:** `StandardScaler` dentro de un `Pipeline` (`kmeans_model.joblib`), indispensable en K-Means porque la distancia euclidiana es sensible a la escala (`delitos ~ 800` vs. `subte ~ 0–3`).
- **Selección de $k$ óptimo (Codo + Silhouette para $k = 2..6$):**
  - $k=2$: Inercia `3595.52`, Silhouette `0.2383` *(descartado por ser demasiado binario para perfilar entornos)*
  - $k=3$: Inercia `2993.46`, Silhouette `0.2327`
  - $k=4$: Inercia `2515.21`, Silhouette `0.2281`
  - **$k=5$: Inercia `2170.53`, Silhouette `0.2343` → Óptimo entre $k \ge 3$** (mayor Silhouette + quiebre claro en la curva de codo).
  - $k=6$: Inercia `2004.42`, Silhouette `0.2291`

### Perfil de los 5 Clústeres Resultantes
Validados estadísticamente sobre `costo_total_ars` con **Kruskal-Wallis** ($H = 172.67, p = 2.79 \times 10^{-36}$):

| ID | Etiqueta de Habitabilidad | Propiedades | Mediana Costo Total | Ruido (med.) | Delitos 500m (med.) | Dist. Escuela (med.) | Líneas Subte 600m | Score Amenities |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| `1` | **Zona Familiar Tranquila** | 255 (`26.45%`) | \$1,320,000 | **62.5 dBA** | 469.0 | 166.18 m | 0.0 | 2.5 |
| `2` | **Hub Ejecutivo Conectado** | 181 (`18.78%`) | \$1,944,000 | 67.5 dBA | 644.0 | 138.15 m | 0.0 | **8.5** |
| `0` | **Zona Urbana Conectada** | 294 (`30.50%`) | \$1,200,000 | 72.5 dBA | 865.0 | **118.64 m** | **1.0** | 2.0 |
| `4` | **Zona Residencial Equilibrada** | 122 (`12.66%`) | \$1,321,000 | 72.5 dBA | **462.5** | 292.69 m | 0.0 | 2.5 |
| `3` | **Zona Ruidosa/Alta Densidad** | 112 (`11.62%`) | \$994,000 | 72.5 dBA | **1,707.0** | 113.88 m | **2.0** | 1.5 |

**Por qué funciona para el negocio:** separa claramente opciones de **alta calma ambiental** (`id=1`, `62.5 dBA`), **edificios full-amenities ejecutivos** (`id=2`, `score_amenities=8.5`), **corredores con subte y escuelas** (`id=0`) y **zonas céntricas muy ruidosas/densas en delito** (`id=3`, más económicas pero penalizadas para familias).

---

## 2. Regresión de Precio Justo (XGBoost Regressor)
- **Por qué `TransformedTargetRegressor(func=np.log1p, inverse_func=np.expm1)`:**
  - `costo_total_ars` tiene asimetría `4.36` (propiedades desde ~\$500k hasta >\$10M ARS). Entrenar directamente con RMSE penaliza desproporcionadamente los departamentos de ultra-lujo y degrada el error porcentual en el segmento medio. Predecir en escala `log1p(ARS)` optimiza errores relativos y estabiliza el ajuste.
- **Esquema de validación y tuning:**
  - Split `train_test_split` **80% / 20%** (`random_state=42`).
  - `RandomizedSearchCV` con **30 iteraciones** y **`KFold(n_splits=5, shuffle=True, random_state=42)`** sobre el 80% de entrenamiento.
  - **Mejores hiperparámetros encontrados:** `n_estimators=200`, `max_depth=3`, `learning_rate=0.06`, `subsample=0.75`, `colsample_bytree=1.0`, `min_child_weight=5`, `reg_lambda=1.0`, `reg_alpha=0.0`. *(Árboles poco profundos `max_depth=3` + `min_child_weight=5` evitan sobreajuste en 964 observaciones).*

### Por qué se eligió cada métrica y resultados obtenidos
| Métrica | Qué mide y por qué se eligió | Hold-out Test (20%) | 5-Fold CV OOF (100%) |
|---|---|---:|---:|
| **MAE (ARS)** | Error absoluto promedio en pesos; fácil de interpretar para RR.HH. | \$331,223.19 | \$283,010.12 |
| **RMSE (ARS)** | Penaliza errores grandes (desvíos en propiedades de alto valor). | \$682,586.24 | \$551,401.06 |
| **MAPE (%)** | Error porcentual medio relativo al precio; clave porque el `% de sobreprecio/ahorro` es una métrica porcentual. | **15.20%** | **14.99%** |
| **$R^2$** | Proporción de varianza explicada del costo total mensual. | **0.7775** | **0.7640** |

La cercanía entre Hold-out ($R^2 = 0.7775$, MAPE `15.20%`) y 5-Fold OOF ($R^2 = 0.7640$, MAPE `14.99%`) confirma **excelente generalización sin overfitting**.

---

## 3. Explicabilidad con SHAP (`ExactExplainer` sobre XGBoost)
Se calculó el valor SHAP de cada una de las 10 features sobre la predicción `log1p(costo_total_ars)` (usando `shap.Explainer(final_model.regressor_.predict, bg)` para compatibilidad total con XGBoost 3.2+).

**Ranking Global (`mean |SHAP|`):**
1. `m2_totales`: `0.2158` *(principal determinante del valor)*
2. `score_amenities`: `0.0888` *(segundo factor clave: edificios con pileta/gym/seguridad justifican fuerte prima)*
3. `banos`: `0.0490`
4. `ambientes`: `0.0314`
5. `cocheras`: `0.0290`
6. `densidad_delitos_500m`: `0.0229`
7. `ruido_db_promedio`: `0.0203`
8. `lineas_subte_600m`: `0.0157`
9. `distancia_escuela_m`: `0.0154`
10. `apto_mascotas`: `0.0083`

Los gráficos `03_shap_summary_beeswarm.png` y `04_shap_feature_importance_bar.png` en `producto2/figures/` muestran tanto la magnitud como la dirección de impacto de cada variable.
