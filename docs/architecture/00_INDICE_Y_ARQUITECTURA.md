# 00 · Índice General, Objetivo de Negocio y Arquitectura del Proyecto

## 1. Objetivo de Negocio (Corporate Relocation / RR.HH. en CABA)
El proyecto resuelve un problema real de **asimetría de información inmobiliaria** para empresas que relocalizan empleados en la Ciudad Autónoma de Buenos Aires (CABA). Recursos Humanos necesita alquilar departamentos adecuados según dos perfiles concretos:
- **`FAMILIA`**: prioriza entornos tranquilos (`<= 65 dBA`), menor densidad delictiva, cercanía a escuelas iniciales/primarias/secundarias, mayor cantidad de ambientes, cochera y admisión real de mascotas.
- **`SOLTERO_EJECUTIVO`**: prioriza conectividad con subte, acceso a amenities (gimnasio, SUM/coworking, balcón/terraza, seguridad) y eficiencia de costo total.

Para evitar pagar sobreprecios o elegir zonas con mala calidad ambiental, la solución se divide en **dos fases secuenciales**:
1. **Fase Analítica & ETL (Core en `src/`):** Limpieza ETL de fuentes heterogéneas, enriquecimiento geoespacial, auditoría estadística completa y selección matemática de un dataset curado de **10 features ortogonales + target (`costo_total_ars`)**.
2. **Fase de MLOps & Producto Productivo (`src/mlops/` y `actors/`):**
   - **Clustering K-Means:** segmentación de propiedades/entornos en 5 perfiles de habitabilidad.
   - **Regresión XGBoost:** estimación del **Precio Justo Teórico (`precio_justo_ars`)** para detectar sobreprecio o ahorro (`%`).
   - **Score de Decisión (`0–100`):** puntaje accionable por perfil (`FAMILIA` vs. `SOLTERO_EJECUTIVO`) empaquetado en artefactos `.joblib` consumibles vía API o inferencia batch.
   - **Dashboard Geoespacial:** visualización WebGL interactiva desacoplada consumiendo datos directamente desde Google Drive en Streamlit Cloud.

---

## 2. Las 5 Preguntas de Negocio Clave
1. **Q1:** ¿Qué zonas y segmentos de departamentos de CABA ofrecen el mejor equilibrio entre calidad ambiental (`<= 65 dBA`, menor gravedad delictiva) y conectividad/servicios según el perfil (`FAMILIA` vs. `SOLTERO_EJECUTIVO`)?
2. **Q2:** ¿Cuál es el impacto estadísticamente significativo de las externalidades urbanas (ruido diurno `> 65 dBA`, densidad/gravedad delictiva, distancia al subte y oferta escolar) sobre el precio/m² y el costo total mensual?
3. **Q3:** ¿Qué proporción de la oferta presenta sobreprecio o subvaluación frente al costo total teórico (`alquiler_ars + expensas_ars`) explicado por atributos físicos, amenities y entorno?
4. **Q4:** ¿Cómo afectan las inconsistencias de publicación (etiquetas contradictorias sobre mascotas, expensas omitidas y coordenadas fuera de CABA) a la elegibilidad real para relocalización corporativa?
5. **Q5:** ¿Qué subconjunto de máximo 10 variables ortogonales (VIF controlado) concentra mayor poder predictivo e información mutua para estimar `costo_total_ars` sin redundancia?

---

## 3. Mapa de Componentes y Responsabilidades del Monorepo

| Carpeta / Módulo | Contenido y Responsabilidad |
|---|---|
| `src/config/settings.py` | Parámetros centralizados (`TIPO_CAMBIO_BASE = 1200.0`, `FACTOR_IMPUESTOS_USD = 1.0`), bounding box de CABA, proyección local y resolución determinista de rutas. |
| `src/etl/etl_pipeline.py` | Limpieza de datos inmobiliarios, unificación monetaria a ARS, extracción NLP de mascotas/expensas/amenities, reproyección CRS y cálculo de distancias Haversine con `BallTree`. |
| `src/eda/eda_phase2.py` | Ejecución de estadísticas descriptivas, pruebas de hipótesis (Mann-Whitney U, Kruskal-Wallis, Spearman), análisis VIF iterativo y selección de las 10 features finales. |
| `src/mlops/train_models.py` | Pipeline de entrenamiento de K-Means y XGBoost Regressor (`RandomizedSearchCV` + `TransformedTargetRegressor`), explicabilidad SHAP y versionado con CLI flags (`--bump`, `--registry`). |
| `src/mlops/registry.py` | Guardián del Model Registry con cálculo de hash SHA-256 para idempotencia y validación de degradación de métricas ($R^2 \ge 0.80$). |
| `src/mlops/inference.py` | Módulo productivo de inferencia (`load_artifacts`, `compute_decision_score`, `predict_property`, `predict_batch`). |
| `actors/inference/` | Contenedor serverless en Apify para ingesta y scoring mensual hermético con geo-caché embebido en `reference_geo/` y soporte de carga dinámica de modelos. |
| `actors/trainer/` | Contenedor serverless en Apify para reentrenamiento anual bajo demanda con exportación atómica a Google Drive (`03_model_registry`). |
| `dashboard/` | Aplicación interactiva en Streamlit Cloud desacoplada de dependencias pesadas de ML, consumiendo datos exclusivamente de Google Drive. |
| `notebooks/` | Entornos de experimentación: `pipeline_observatorio_caba.ipynb` (End-to-End maestro) y `observatorio_caba_showcase.ipynb` (showcase analítico). |
| `workflows/n8n/` | Definiciones JSON de los flujos de orquestación mensual, anual y lienzo unificado de 31 nodos. |
| `tests/` | Suite determinista unificada de **70 tests automatizados** (`pytest`) con código de salida 0. |

---

## 4. Documentos de Esta Carpeta
- [01_ETL_Y_CURACION_DE_DATOS.md](./01_ETL_Y_CURACION_DE_DATOS.md) — Limpieza, NLP, geoprocesamiento y enriquecimiento espacial.
- [02_EDA_ESTADISTICO_Y_SELECCION_FEATURES.md](./02_EDA_ESTADISTICO_Y_SELECCION_FEATURES.md) — Estadística, pruebas de hipótesis, VIF y justificación de las 10 features.
- [03_MODELADO_KMEANS_XGBOOST_Y_SHAP.md](./03_MODELADO_KMEANS_XGBOOST_Y_SHAP.md) — K-Means, XGBoost Regressor, SHAP y gobernanza del Model Registry.
- [04_SCORE_DECISION_INFERENCIA_Y_HANDOFF.md](./04_SCORE_DECISION_INFERENCIA_Y_HANDOFF.md) — Fórmula del Score `0–100`, arquitectura de handoff productivo y testing continuo.
- [05_APIFY_ACTORS.md](./05_APIFY_ACTORS.md) — Contratos de Actores Apify (`actors/inference`, `actors/trainer`), `output_schema.json`, `dataset_schema.json`, `key_value_store_schema.json` y requisitos de publicación en Apify Store.
