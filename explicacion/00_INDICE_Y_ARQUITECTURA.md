# 00 · Índice General, Objetivo de Negocio y Arquitectura del Proyecto

## 1. Objetivo de Negocio (Corporate Relocation / RR.HH. en CABA)
El proyecto resuelve un problema real de **asimetría de información inmobiliaria** para empresas que relocalizan empleados en la Ciudad Autónoma de Buenos Aires (CABA). Recursos Humanos necesita alquilar departamentos adecuados según dos perfiles concretos:
- **`FAMILIA`**: prioriza entornos tranquilos (`<= 65 dBA`), menor densidad delictiva, cercanía a escuelas iniciales/primarias/secundarias, mayor cantidad de ambientes, cochera y admisión real de mascotas.
- **`SOLTERO_EJECUTIVO`**: prioriza conectividad con subte, acceso a amenities (gimnasio, SUM/coworking, balcón/terraza, seguridad) y eficiencia de costo total.

Para evitar pagar sobreprecios o elegir zonas con mala calidad ambiental, la solución se divide en **dos productos secuenciales**:
1. **Producto 1 (Analytics):** Limpieza ETL de 5 fuentes heterogéneas, enriquecimiento geoespacial, auditoría estadística completa y selección matemática de un dataset curado de **10 features ortogonales + target (`costo_total_ars`)**.
2. **Producto 2 (Inference — Opción A):**
   - **Clustering K-Means:** segmentación de propiedades/entornos en 5 perfiles de habitabilidad.
   - **Regresión XGBoost:** estimación del **Precio Justo Teórico (`precio_justo_ars`)** para detectar sobreprecio o ahorro (`%`).
   - **Score de Decisión (`0–100`):** puntaje accionable por perfil (`FAMILIA` vs. `SOLTERO_EJECUTIVO`) empaquetado en artefactos `.joblib` + módulo `inference.py`.

---

## 2. Las 5 Preguntas de Negocio Clave
1. **Q1:** ¿Qué zonas y segmentos de departamentos de CABA ofrecen el mejor equilibrio entre calidad ambiental (`<= 65 dBA`, menor gravedad delictiva) y conectividad/servicios según el perfil (`FAMILIA` vs. `SOLTERO_EJECUTIVO`)?
2. **Q2:** ¿Cuál es el impacto estadísticamente significativo de las externalidades urbanas (ruido diurno `> 65 dBA`, densidad/gravedad delictiva, distancia al subte y oferta escolar) sobre el precio/m² y el costo total mensual?
3. **Q3:** ¿Qué proporción de la oferta presenta sobreprecio o subvaluación frente al costo total teórico (`alquiler_ars + expensas_ars`) explicado por atributos físicos, amenities y entorno?
4. **Q4:** ¿Cómo afectan las inconsistencias de publicación (etiquetas contradictorias sobre mascotas, expensas omitidas y coordenadas fuera de CABA) a la elegibilidad real para relocalización corporativa?
5. **Q5:** ¿Qué subconjunto de máximo 10 variables ortogonales (VIF controlado) concentra mayor poder predictivo e información mutua para estimar `costo_total_ars` sin redundancia?

---

## 3. Mapa Completo de Carpetas y Contenido de Cada Archivo

| Carpeta / Archivo | Contenido y Responsabilidad |
|---|---|
| `config/settings.py` | Parámetros centralizados (`TIPO_CAMBIO_BASE = 1200.0`, `FACTOR_IMPUESTOS_USD = 1.0`, `IMPUESTO_SELLOS_ALQUILER = 0.0`), bounding box CABA, proyección CRS local, pesos de delito y resolución de rutas (`Datasets/Originales` y `Datasets/Curados`). |
| `etl/etl_pipeline.py` | Limpieza del JSON de Zonaprop, unificación monetaria a ARS, extracción NLP de mascotas/expensas/amenities, normalización decimal de delitos, reproyección CRS de escuelas, `sjoin(within)`/`sjoin_nearest` de ruido, `BallTree` Haversine, detección de outliers (IQR/Z-score) y exportación unificada a CSV. |
| `eda/eda_phase2.py` | Ejecución de Fase 1 + Fase 2: estadísticas descriptivas, pruebas de hipótesis (Shapiro-Wilk, Mann-Whitney U, Welch, Levene, ANOVA, Kruskal-Wallis, $\chi^2$, Spearman), análisis VIF iterativo, Random Forest + Mutual Information, selección de las 10 features finales y generación de gráficos en `eda/figures/`. |
| `eda/figures/` | `01_distribucion_target.png`, `02_barrios_y_ruido.png`, `03_feature_importance.png`, `04_correlacion_top10.png`. |
| `Datasets/Originales/` | Los 5 archivos fuente sin modificar (`zonaprop_alquileres_caba_1000.json`, `medicion_de_ruido_diurno_2018.csv`, `delitos_2022.xlsx`, `establecimientos_educativos.xlsx`, `bocas-de-subte.csv`). |
| `Datasets/Curados/` | Los 5 datasets individuales curados en formato `.csv` unificado y coordenadas `EPSG:4326` (`zonaprop_alquileres_curado.csv`, `medicion_ruido_curado.csv`, `delitos_2022_curado.csv`, `establecimientos_educativos_curado.csv`, `bocas_de_subte_curado.csv`). |
| `producto1/producto1_dataset_curado.csv` | Entregable analítico final: `964` filas × `10` features predictivas + target `costo_total_ars`, sin nulos. |
| `producto1/dataset_enriquecido_completo.csv` | Dataset completo (`964` filas) con `listing_id`, coordenadas, barrios, sub-scores y banderas de auditoría/outliers. |
| `producto1/eda_stats.json` | Reporte JSON completo con auditoría ETL, estadísticas descriptivas, pruebas de hipótesis, tabla VIF y ranking de features. |
| `producto2/train_models.py` | Entrenamiento de K-Means (Codo + Silhouette), XGBoost Regressor (`KFold(5)` + `RandomizedSearchCV` + `TransformedTargetRegressor`), explicabilidad SHAP y exportación de artefactos. |
| `producto2/inference.py` | Módulo productivo de inferencia (`load_artifacts`, `compute_decision_score`, `predict_property`, `predict_batch`). |
| `producto2/artifacts/` | Modelos serializados: `kmeans_model.joblib`, `xgb_price_model.joblib`, `model_metadata.joblib`. |
| `producto2/figures/` | `01_kmeans_elbow_silhouette.png`, `02_xgboost_pred_vs_real.png`, `03_shap_summary_beeswarm.png`, `04_shap_feature_importance_bar.png`. |
| `producto2/model_metrics.json` | Métricas de evaluación de K-Means, XGBoost (Hold-out y 5-Fold OOF), SHAP y resumen de inferencia. |
| `producto2/resultados_inferencia_caba.csv` | Evaluación completa de las `964` propiedades con clúster, `precio_justo_ars`, `% sobreprecio/ahorro`, Score `0–100` y recomendación para ambos perfiles. |
| `tests/` | Suite TDD (`conftest.py`, `test_etl_and_eda.py`, `test_producto2.py`) con **11/11 tests aprobados**. |

---

## 4. Documentos de Esta Carpeta
- [01_ETL_Y_CURACION_DE_DATOS.md](./01_ETL_Y_CURACION_DE_DATOS.md) — Limpieza, NLP, geoprocesamiento y auditoría de los 5 archivos.
- [02_EDA_ESTADISTICO_Y_SELECCION_FEATURES.md](./02_EDA_ESTADISTICO_Y_SELECCION_FEATURES.md) — Estadística, pruebas de hipótesis, VIF y justificación de las 10 features.
- [03_MODELADO_KMEANS_XGBOOST_Y_SHAP.md](./03_MODELADO_KMEANS_XGBOOST_Y_SHAP.md) — K-Means, XGBoost Regressor, K-Fold CV y SHAP.
- [04_SCORE_DECISION_INFERENCIA_Y_HANDOFF.md](./04_SCORE_DECISION_INFERENCIA_Y_HANDOFF.md) — Fórmula del Score `0–100`, uso de `.joblib`/`inference.py`, tests TDD y entrega al Solutions Engineer.
