# 🏙️ Observatorio Inmobiliario CABA — Monorepo

Sistema integral de inteligencia inmobiliaria para la Ciudad Autónoma de Buenos Aires (CABA). El proyecto combina curación geoespacial con datos abiertos del GCBA, modelado predictivo y MLOps (K-Means, XGBoost, SHAP y Model Registry con control de regresión métrica), un pipeline serverless dual en la nube (Apify + n8n) y un dashboard interactivo de visualización geoespacial en tiempo real (Streamlit + PyDeck WebGL + Heatmap de Delitos).

---

## 📑 Índice General

1. [🏛️ Arquitectura del Monorepo (`src-layout`)](#-arquitectura-del-monorepo-src-layout)
2. [🔄 Ciclos de Vida y Desacoplamiento](#-ciclos-de-vida-y-desacoplamiento)
3. [🌐 Despliegue en Streamlit Community Cloud](#-despliegue-en-streamlit-community-cloud)
4. [📓 Notebooks de Ciencia de Datos y Showcase](#-notebooks-de-ciencia-de-datos-y-showcase)
5. [💻 Ejecución Local y Testing](#-ejecución-local-y-testing)
6. [📚 Documentación Técnica Detallada](#-documentación-técnica-detallada)

---

## 🏛️ Arquitectura del Monorepo (`src-layout`)

El repositorio sigue una arquitectura desacoplada bajo el estándar canónico `src-layout` para Python y aislamiento hermético para contenedores serverless:

```
.
├── README.md                      # Documentación maestra del sistema
├── requirements.txt               # Referencia a dashboard/requirements.txt (Streamlit Cloud)
├── pytest.ini                     # Configuración de pruebas unificadas (pythonpath = src dashboard .)
├── .gitignore                     # Exclusión de datos pesados (>50MB), apuntes y cachés
│
├── actors/                        # 🐳 Contenedores Serverless Apify
│   ├── inference/                 # Actor mensual ligero: curación, geo-caché y scoring
│   │   ├── Dockerfile             # Contenedor apify/actor-python:3.11 hermético
│   │   ├── requirements.txt       # Dependencias mínimas de inferencia
│   │   ├── reference_geo/         # Caché geoespacial WGS84 indexado (Parquet + BallTree)
│   │   ├── artifacts/             # Modelos congelados fallback (.joblib)
│   │   └── src/                   # pipeline, nlp_parser, scoring y entrypoint main.py
│   └── trainer/                   # Actor anual serverless: reentrenamiento y registry
│       ├── Dockerfile             # Contenedor con XGBoost, Scikit-Learn y Google Drive API
│       ├── requirements.txt       # Dependencias científicas completas
│       └── src/                   # train_pipeline, gdrive_exporter y entrypoint main.py
│
├── src/                           # 🧠 Núcleo de Procesamiento y Machine Learning (src-layout)
│   ├── config/                    # Parámetros monetarios y bounding boxes (settings.py)
│   ├── etl/                       # Pipeline geoespacial base y cruces espaciales
│   ├── eda/                       # Análisis exploratorio, pruebas de hipótesis y VIF
│   └── mlops/                     # Entrenamiento, inferencia batch y Model Registry
│       ├── registry.py            # Versionador incremental, hash SHA-256 y guarda R2 >= 0.80
│       ├── registry.json          # Metadatos del registro de producción
│       ├── artifacts/             # Binarios serializados (.joblib) versionados (v1, ...)
│       └── figures/               # Curvas de evaluación y explicabilidad SHAP
│
├── dashboard/                     # 🌐 Aplicación Interactiva de Visualización (Streamlit)
│   ├── app.py                     # Entrypoint de producción (Streamlit Cloud)
│   ├── requirements.txt           # Dependencias mínimas de UI (pandas, pydeck, streamlit, requests)
│   ├── .streamlit/config.toml     # Configuración de rendimiento (fileWatcherType = "none")
│   ├── src/                       # Componentes modulares de interfaz
│   │   ├── config.py              # Paleta accesible WCAG 2.2 y bounding box CABA
│   │   ├── data_loader.py         # Conector exclusivo a Google Drive (autodetección mensual)
│   │   ├── map_view.py            # Capas Deck.gl (Scatterplot, Column 3D y HeatmapLayer de Delitos)
│   │   ├── normalizer.py          # Validación defensiva de columnas, tipos y aliases
│   │   └── ui_components.py       # KPIs dinámicos, filtros y tarjetas de habitabilidad
│   └── tests/                     # Suite de 19 tests unitarios e integración de UI
│
├── notebooks/                     # 📓 Entornos de Experimentación y Demostración
│   ├── pipeline_observatorio_caba.ipynb # Notebook Maestro End-to-End reproducible
│   └── observatorio_caba_showcase.ipynb # Showcase interactivo y analítico para defensa
│
├── workflows/                     # ⚙️ Automatización y Orquestación Cloud
│   └── n8n/                       # Flujos de orquestación mensual, anual y lienzo unificado
│
├── scripts/                       # 🛠️ Utilidades de Soporte y Preparación
│   ├── fetch_apify_raw.py         # Descarga segura de datasets crudos vía APIFY_TOKEN
│   ├── notebook_helpers.py        # Helpers para ingesta CKAN y mocks en notebooks
│   └── prepare_geo_cache.py       # Precomputación de Parquet y KD-Trees geoespaciales
│
├── tests/                         # 🧪 Suite Unificada de Pruebas Backend (51 tests)
│   ├── fixtures/                  # Muestras JSON y CSV para tests de integración
│   └── test_*.py                  # Tests unitarios deterministas
│
└── docs/                          # 📚 Documentación Técnica Centralizada
    ├── architecture/              # Guías detalladas 00 a 04 (ETL, EDA, ML, Handoff)
    ├── business_questions.md      # Las 5 preguntas de negocio (Corporate Relocation)
    ├── feature_selection.md       # Matriz de 10 features, VIF y correlación
    ├── README_DEPLOYMENT_N8N.md   # Runbook operativo de Apify y n8n
    ├── README_DASHBOARD_CONFIG.md # Guía canónica de secretos de Google Drive para Streamlit
    └── evidence/                  # Reportes de verificación continua determinista
```

---

## 🔄 Ciclos de Vida y Desacoplamiento

El sistema desacopla el ciclo mensual de scoring del ciclo anual de reentrenamiento serverless y del consumo en visualización:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ORQUESTACIÓN CLOUD EN N8N                         │
├──────────────────────────────────────┬──────────────────────────────────────┤
│       CICLO MENSUAL (Día 1)          │        CICLO ANUAL (1 de Marzo)      │
├──────────────────────────────────────┼──────────────────────────────────────┤
│ 1. Scraper Zonaprop (Apify)          │ 1. Auditoría CKAN GCBA (4 Datasets)  │
│ 2. Circuit Breaker & Idempotencia    │ 2. Resguardo Raw en Google Drive     │
│ 3. Actor Inferencia (actors/inference│ 3. Actor Trainer (actors/trainer/)   │
│ 4. Guardar CSV en 01_mensual         │ 4. Registro atómico 03_model_registry│
│ 5. Purga Retención Trimestral        │ 5. Publicación en Apify KV Store     │
│ 6. Acumular en 04_historico_anual    │ 6. Carga dinámica en actor inferencia│
└──────────────────────────────────────┴──────────────────────────────────────┘
                   │
                   ▼ Archivo publicado en Google Drive:
                     01_mensual_enriquecido/alquileres_caba_enriquecido_YYYY_MM.csv
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    VISUALIZACIÓN EN STREAMLIT CLOUD                         │
├─────────────────────────────────────────────────────────────────────────────┤
│ - Consume exclusivamente el CSV mensual publicado en Google Drive.         │
│ - Autodetecta el archivo más reciente (YYYY_MM) vía API Key de Drive.       │
│ - 100% libre de dependencias pesadas de ML (arranque en segundos).          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🌐 Despliegue en Streamlit Community Cloud

Para desplegar la interfaz interactiva en Streamlit Community Cloud:

1. **Nuevo Despliegue**: Ingresa a [share.streamlit.io](https://share.streamlit.io/) con tu cuenta de GitHub.
2. **Configuración del Repositorio**:
   - **Repository**: Tu repositorio.
   - **Branch**: `main`
   - **Main file path**: `dashboard/app.py`  *(Ruta obligatoria para el monorepo)*
3. **Variables de Entorno (Secrets)**:
   La forma recomendada es configurar una carpeta pública de Google Drive mediante **API Key**, lo que permite la **autodetección automática del último CSV mensual**:
   ```toml
   gdrive_folder_id = "TU_ID_O_URL_DE_CARPETA"
   gdrive_api_key = "TU_API_KEY_DE_GOOGLE_DRIVE"
   ```
   > 📖 **Guía Completa de Configuración de Secrets:** Consulta [docs/README_DASHBOARD_CONFIG.md](docs/README_DASHBOARD_CONFIG.md) para el paso a paso detallado sobre cómo generar la API Key, los permisos de carpeta y el orden de prioridad de conexión.

---

## 📓 Notebooks de Ciencia de Datos y Showcase

Ubicados en `notebooks/`, proveen entornos reproducibles y visuales:

- **`notebooks/pipeline_observatorio_caba.ipynb`**: Notebook Maestro End-to-End que reproduce todo el flujo de ingesta en vivo (CKAN API + Apify Scraper), ETL geoespacial, EDA estadístico con VIF, entrenamiento de modelos con comparativa (Baseline vs. Ridge vs. RF vs. XGBoost) y generación de los 8 gráficos para la defensa ejecutiva.
- **`notebooks/observatorio_caba_showcase.ipynb`**: Cuaderno interactivo enfocado en la visualización exploratoria y analítica de datos.

---

## 💻 Ejecución Local y Testing

### 1. Iniciar el Dashboard Localmente
```bash
# Instalar dependencias de UI
pip install -r dashboard/requirements.txt

# Ejecutar dashboard
streamlit run dashboard/app.py
```
Accede a `http://localhost:8501`.

### 2. Ejecutar Modelado y MLOps Localmente
```bash
# Reentrenar modelos e interactuar con el Model Registry
python src/mlops/train_models.py --registry --bump --min-r2 0.80
```

### 3. Ejecución de Pruebas Automatizadas
El proyecto cuenta con un arnés de pruebas deterministas de **70 tests**:
```bash
# Ejecutar la suite completa (Backend + UI)
pytest

# Ejecutar únicamente pruebas de la UI de Streamlit (19 tests)
pytest dashboard/tests/ -v

# Ejecutar únicamente pruebas de Backend, MLOps y Actores (51 tests)
pytest tests/ -v
```

---

## 📚 Documentación Técnica Detallada

- **[docs/architecture/00_INDICE_Y_ARQUITECTURA.md](docs/architecture/00_INDICE_Y_ARQUITECTURA.md)**: Índice general, perfiles de negocio (`FAMILIA` vs. `SOLTERO_EJECUTIVO`) y mapa de responsabilidades.
- **[docs/architecture/01_ETL_Y_CURACION_DE_DATOS.md](docs/architecture/01_ETL_Y_CURACION_DE_DATOS.md)**: Unificación monetaria, NLP de expensas/mascotas y cruces geoespaciales.
- **[docs/architecture/02_EDA_ESTADISTICO_Y_SELECCION_FEATURES.md](docs/architecture/02_EDA_ESTADISTICO_Y_SELECCION_FEATURES.md)**: Pruebas de hipótesis, análisis VIF y justificación de las 10 features.
- **[docs/architecture/03_MODELADO_KMEANS_XGBOOST_Y_SHAP.md](docs/architecture/03_MODELADO_KMEANS_XGBOOST_Y_SHAP.md)**: K-Means (k=5), XGBoost Regressor ($R^2$, MAE, MAPE), explicabilidad SHAP y gobernanza de Model Registry.
- **[docs/architecture/04_SCORE_DECISION_INFERENCIA_Y_HANDOFF.md](docs/architecture/04_SCORE_DECISION_INFERENCIA_Y_HANDOFF.md)**: Algoritmo de Score 0–100, recomendaciones y contrato de entrega operativa.
- **[docs/business_questions.md](docs/business_questions.md)**: Formulación de las 5 preguntas de negocio (Q1 a Q5).
- **[docs/feature_selection.md](docs/feature_selection.md)**: Matriz de features seleccionadas y VIF final.
- **[docs/README_DEPLOYMENT_N8N.md](docs/README_DEPLOYMENT_N8N.md)**: Runbook operativo de n8n, Apify CLI y Google Drive.
- **[docs/README_DASHBOARD_CONFIG.md](docs/README_DASHBOARD_CONFIG.md)**: Manual de configuración de acceso a Google Drive en Streamlit.
