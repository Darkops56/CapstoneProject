# 🏙️ Observatorio Inmobiliario CABA — Monorepo

Sistema integral de inteligencia inmobiliaria para la Ciudad Autónoma de Buenos Aires. El proyecto combina curación geoespacial con datos abiertos del GCBA, modelado predictivo y MLOps (XGBoost y KMeans), un pipeline mensual de enriquecimiento en la nube (Apify + n8n) y un dashboard interactivo de visualización geoespacial en tiempo real (Streamlit + PyDeck WebGL).

---

## 🏛️ Arquitectura Limpia del Monorepo

El repositorio está estructurado bajo una arquitectura modular desacoplada:

```
.
├── README.md                      # Documentación maestra del sistema
├── requirements.txt               # Referencia a dashboard/requirements.txt para Streamlit Cloud
├── pytest.ini                     # Arnés de pruebas unificado (ML + Dashboard)
├── .gitignore                     # Exclusión de archivos pesados (>50MB) y cachés
│
├── dashboard/                     # 🌐 Aplicación Interactiva de Visualización (Streamlit)
│   ├── app.py                     # Entrypoint de producción (Streamlit Cloud)
│   ├── requirements.txt           # Dependencias mínimas de UI (pandas, pydeck, streamlit, etc.)
│   ├── .streamlit/config.toml     # Configuración de rendimiento (fileWatcherType = "none")
│   ├── src/                       # Componentes modulares de la interfaz
│   │   ├── config.py              # Paleta accesible WCAG 2.2 y bounding box CABA
│   │   ├── data_loader.py         # Conector exclusivo a Google Drive (sin fallback local)
│   │   ├── map_view.py            # Capas Deck.gl (Scatterplot + ColumnLayer 3D)
│   │   ├── normalizer.py          # Validación defensiva de columnas y tipos
│   │   └── ui_components.py       # KPIs dinámicos, filtros y tarjetas de alto contraste
│   └── tests/                     # Suite de pruebas unitarias e integración de UI
│
├── mlops/                         # 🧠 MLOps: Entrenamiento, Inferencia y Model Registry
│   ├── train_models.py            # Reentrenamiento periódico (XGBoost + KMeans)
│   ├── inference.py               # Script de inferencia por lotes
│   ├── artifacts/                 # Modelos serializados (.joblib)
│   ├── figures/                   # Curvas de evaluación y explicabilidad SHAP
│   └── model_metrics.json         # Métricas de validación del modelo
│
├── actor/                         # 🐳 Actor de Producción Apify
│   ├── Dockerfile                 # Contenedor para ejecución serverless
│   ├── requirements.txt           # Dependencias de scraping y scoring
│   └── src/                       # Ingesta, parseo NLP y cálculo de scores de oportunidad
│
├── etl/                           # 🗺️ Ingesta y Curación Geoespacial
│   ├── etl_pipeline.py            # Cruce espacial con subtes, escuelas, delitos y ruido GCBA
│   └── output/                    # Datasets curados intermedios
│
├── Datasets/                      # 📍 Datos Geográficos de Referencia CABA
│   ├── Originales/                # Datos oficiales GCBA (ruido, subte, escuelas, delitos)
│   └── Curados/                   # Versiones estandarizadas en WGS84
│
├── eda/                           # 📊 Análisis Exploratorio Estadístico
│   ├── eda_phase2.py              # Script de validación de hipótesis y VIF
│   └── figures/                   # Gráficos y matrices de correlación
│
├── docs/                          # 📚 Documentación Centralizada Unificada
│   ├── architecture/              # Guías de arquitectura, ETL, EDA y MLOps
│   ├── business_questions.md      # Formulación de preguntas de negocio
│   ├── feature_selection.md       # Tabla de features seleccionadas y VIF
│   ├── README_DEPLOYMENT_N8N.md   # Guía de orquestación en n8n
│   └── evidence/                  # Reportes de verificación continua
│
├── scripts/                       # 🛠️ Utilidades y Scripts Auxiliares
│   ├── prepare_geo_cache.py       # Precomputación de KD-Trees y BallTrees geoespaciales
│   └── fetch_apify_raw.py         # Script seguro de descarga cruda vía env var APIFY_TOKEN
│
├── tests/                         # 🧪 Suite de Pruebas de Backend
│   ├── fixtures/                  # Muestras JSON y CSV para tests de integración
│   └── test_*.py                  # Tests unitarios deterministas
│
├── config/                        # ⚙️ Configuración y Constantes Globales
│   └── settings.py                # Resolución centralizada de paths y parámetros
│
└── workflows/                     # ⚙️ Automatización y Orquestación
    └── n8n/                       # Flujos mensuales de scraping, inferencia y retención Drive
```

---

## 🔄 Ciclos de Vida y Desacoplamiento

El sistema desacopla el ciclo de Machine Learning del ciclo de Visualización mediante un **contrato por artefacto (CSV enriquecido en Google Drive)**:

```
[ Reentrenamiento MLOps ]
  (mlops/train_models.py) -> Exporta modelos a artifacts/ (.joblib)
             │
             ▼
[ Ingesta Mensual Cloud ]
  (actor/ + n8n) -> Ingiere publicaciones -> Enriquece con ML y GCBA
             │
             ▼ Publica archivo mensual en Google Drive:
               alquileres_caba_enriquecido_YYYY_MM.csv
             │
             ▼
[ Visualización en Vivo ]
  (dashboard/app.py en Streamlit Cloud)
  -> Consume exclusivamente el CSV mensual publicado en Google Drive.
  -> Sin fallback a archivos locales: desacoplamiento e higiene 100% cloud.
  -> 100% libre de dependencias pesadas de ML (arranque en segundos).
```

---

## 🚀 Despliegue en Streamlit Community Cloud

Para desplegar este monorepo en Streamlit Community Cloud:

1. **Nuevo Despliegue**: Ve a [share.streamlit.io](https://share.streamlit.io/) e inicia sesión con tu cuenta de GitHub.
2. **Configuración de la App**:
   * **Repository**: Selecciona tu repositorio.
   * **Branch**: `main`
   * **Main file path**: `dashboard/app.py`  *(Ruta obligatoria para monorepo)*
   * **App URL**: Personaliza tu subdominio deseado.
3. **Variables de Entorno (Secrets)**:
   En los ajustes avanzados (*Advanced settings -> Secrets*), ingresa:
   ```toml
   # Opción 1: Enlace directo al CSV mensual exportado
   gdrive_csv_url = "https://drive.google.com/uc?export=download&id=TU_ID_DE_ARCHIVO"

   # Opción 2: ID directo del archivo de Drive
   gdrive_file_id = "TU_ID_DE_ARCHIVO"
   ```
4. **Deploy**: Haz clic en **Deploy**. Streamlit Cloud detectará automáticamente `dashboard/requirements.txt` y levantará la aplicación sin instalar librerías pesadas de entrenamiento.

---

## 💻 Ejecución Local

### 1. Levantar el Dashboard
```bash
pip install -r dashboard/requirements.txt
streamlit run dashboard/app.py
```
Accede a `http://localhost:8501`.

### 2. Reentrenar Modelos de Machine Learning
```bash
pip install scikit-learn xgboost shap joblib
python mlops/train_models.py
```

### 3. Ejecutar Pruebas Automatizadas
```bash
# Ejecutar todas las pruebas (ML + Dashboard)
pytest

# Ejecutar únicamente las pruebas del dashboard
pytest dashboard/tests/ -v
```
