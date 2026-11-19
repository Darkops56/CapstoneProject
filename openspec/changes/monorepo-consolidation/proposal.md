# Proposal: Consolidación Monorepo y Desacoplamiento de Despliegue

## Tier de Complejidad
**Tier M (Arquitectónico / Estructural)**: Reorganización integral del repositorio para unificar la rama de visualización (`interactive_property_map_dashboard`) y la rama de producción (`main`) en un monorepo modular y desacoplado, sin introducir sobre-ingeniería ni microservicios innecesarios (estricto cumplimiento YAGNI).

## Why
Actualmente el proyecto inmobiliario se encuentra fragmentado en dos ramas divergentes:
1. `origin/main` aloja el pipeline ETL (`etl/`), el contenedor de scoring Apify (`actor/`), los modelos y scripts de inferencia (`producto2/`), y workflows n8n, pero carece de la interfaz de usuario.
2. `interactive_property_map_dashboard` aloja la aplicación Streamlit validada (`app.py`, `src/`, `data/fallback_data.csv`, `tests/`), pero está aislada en la raíz del repositorio, impidiendo que el ciclo de reentrenamiento y el de visualización convivan bajo un mismo flujo de trabajo continuo.

Además, `main` arrastra archivos pesados (~500 MB en `apuntes/` y volcados de datos locales) que ralentizan la clonación y amenazan los límites de despliegue en entornos como Streamlit Community Cloud.

Esta consolidación unifica ambos mundos en la rama `main` aislando la aplicación web en el subdirectorio `dashboard/`, preservando el contrato de datos mediante el CSV mensual enriquecido y aligerando el repositorio para despliegues instantáneos.

## What Changes
- **Aislamiento del Dashboard**: Migrar todos los componentes de la interfaz (`app.py`, `src/`, `data/fallback_data.csv`, `tests/`, `.streamlit/`, `requirements.txt`) a un subdirectorio autónomo `dashboard/`.
- **Estructuración MLOps**: Formalizar el módulo de modelado (`mlops/`, derivado de `producto2/`), preservando `train_models.py`, `inference.py`, `artifacts/` (.joblib) y métricas.
- **Configuración de Despliegue**: Documentar y verificar el entrypoint de Streamlit Cloud apuntando a `dashboard/app.py` con `dashboard/requirements.txt`.
- **Saneamiento y Exclusión**: Actualizar `.gitignore` en la raíz para excluir permanentemente `apuntes/` (~500 MB de PDFs de cátedra), cachés de matplotlib y datasets crudos sobredimensionados, manteniendo `main` por debajo de 25 MB.
- **Documentación Centralizada**: Crear un `README.md` maestro en la raíz con arquitectura del monorepo, instrucciones de ejecución local y guía de despliegue continuo.

## Capabilities

### New Capabilities
- `monorepo-workspace`: Define la arquitectura modular del monorepo, las fronteras de aislamiento de dependencias entre MLOps y el Dashboard, y el contrato de despliegue en Streamlit Cloud mediante `dashboard/app.py`.

### Modified Capabilities
*(Ninguna. El pipeline Apify conserva intacto su contrato de enriquecimiento y schema de salida).*

## Assumptions Eradication
- **Supuesto 1**: *El dashboard necesita scikit-learn o XGBoost en tiempo de ejecución para mostrar mapas y KPIs.*  
  **Hecho comprobado**: Falso. `src/data_loader.py` y `src/normalizer.py` solo consumen el CSV enriquecido (vía Google Drive o fallback local) usando Pandas/Numpy. El dashboard no requiere bibliotecas pesadas de ML.
- **Supuesto 2**: *Streamlit Community Cloud exige que `app.py` esté en la raíz del repositorio.*  
  **Hecho comprobado**: Falso. Streamlit Cloud dispone del parámetro de configuración nativo *Main file path*, permitiendo especificar `dashboard/app.py`.
- **Supuesto 3**: *Se requiere una base de datos SQL o API REST intermedia para conectar el reentrenamiento con el dashboard.*  
  **Hecho comprobado**: Falso. El contrato desacoplado por archivo CSV (`alquileres_caba_enriquecido_YYYY_MM.csv`) en Google Drive es suficiente y de costo de mantenimiento cero (YAGNI).

## Non-Goals
- No se reescribirán los algoritmos de inferencia (`actor/` o `mlops/`), ni se cambiarán las variables del modelo XGBoost/KMeans.
- No se levantará una base de datos relacional (PostgreSQL/MySQL) ni un servidor FastAPI intermedio; se mantiene la arquitectura orientada a artefactos curados.
- No se borrarán los apuntes del historial local, sino que se excluirán del seguimiento en Git para aligerar la rama principal.

## Impact
- **Archivos inspeccionados**:
  - `origin/main:producto2/train_models.py`, `origin/main:producto2/inference.py`, `origin/main:actor/src/pipeline.py`.
  - `app.py`, `src/config.py`, `src/data_loader.py`, `src/map_view.py`, `src/ui_components.py`, `tests/test_dashboard.py`.
- **Compatibilidad**: Compatible al 100% hacia atrás. El pipeline de Apify seguirá depositando el dataset mensual en Drive, y el dashboard seguirá consumiéndolo sin disrupción.
