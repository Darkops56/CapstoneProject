# monorepo-workspace Specification

## Purpose
Define el contrato de arquitectura y desacoplamiento para el monorepo inmobiliario CABA, garantizando el aislamiento de dependencias entre los pipelines de MLOps y el dashboard de visualización interactivo en Streamlit.

## Architecture & Interaction

```mermaid
sequenceDiagram
    autonumber
    participant Dev as Desarrollador / Cron
    participant MLOps as MLOps Module (mlops/)
    participant Actor as Apify Actor (actor/)
    participant Storage as Google Drive / Fallback Seed
    participant Dashboard as Streamlit UI (dashboard/)
    participant User as Usuario Final

    Dev->>MLOps: Reentrenar modelos periódicos (train_models.py)
    MLOps-->>Actor: Exportar modelos (.joblib) a artifacts/
    Dev->>Actor: Ejecutar pipeline mensual de enriquecimiento
    Actor->>Storage: Publicar CSV alquileres_caba_enriquecido_YYYY_MM.csv
    User->>Dashboard: Acceder a Observatorio CABA (dashboard/app.py)
    Dashboard->>Storage: Cargar dataset mensual (o data/fallback_data.csv)
    Dashboard-->>User: Renderizar mapa interactivo y listado filtrable
```

## Requirements

### Requirement: Dashboard Directory Isolation
The system MUST isolate all executable components, seed data, and tests of the dashboard into the `dashboard/` subdirectory without runtime dependencies on heavy ML training libraries (`xgboost`, `scikit-learn`, `shap`).

#### Scenario: Local dashboard invocation
- **WHEN** un desarrollador o agente ejecuta `streamlit run dashboard/app.py` desde la raíz del monorepo
- **THEN** la aplicación se inicia correctamente, cargando componentes desde `dashboard/src/` y datos desde `dashboard/data/fallback_data.csv` con Exit Code 0 y sin errores de importación.

#### Scenario: Running isolated test suite
- **WHEN** se ejecuta el comando determinista `pytest dashboard/tests/`
- **THEN** los 11 tests unitarios y de integración se ejecutan exitosamente con código de salida 0 (11 passed).

### Requirement: Cloud Deployment Path Contract
The system MUST support the Streamlit Community Cloud monorepo specification via the main file path configuration.

#### Scenario: Streamlit cloud configuration validation
- **WHEN** se inspecciona la ruta de archivo principal configurada en la plataforma de despliegue
- **THEN** la ruta apunta a `dashboard/app.py` y las dependencias resueltas corresponden exclusivamente a `dashboard/requirements.txt`.

### Requirement: Heavy Asset Exclusion and Git Hygiene
The system MUST exclude heavy academic course materials and large raw datasets from Git tracking to keep the `main` branch lightweight and optimized for rapid deployment.

#### Scenario: Verifying gitignore rules
- **WHEN** se ejecuta `git status --ignored` o se verifica el contenido de `.gitignore`
- **THEN** las rutas `apuntes/`, `.matplotlib_cache/` y archivos `.xlsx` o `.csv` crudos superiores a 50MB no son rastreados por Git, y el peso total del repositorio clonable es inferior a 25 MB.

## Test Plan & Resilience Strategy
- **Verificación Determinista (SVC)**: `pytest dashboard/tests/` para certificar que el traslado de archivos no rompió rutas relativas de carga (`fallback_data.csv` o `src/config.py`).
- **Resiliencia ante Fallo de Red**: Si la descarga del CSV remoto de Google Drive falla (timeout o credenciales inválidas), el componente `dashboard/src/data_loader.py` DEBE degradar suavemente al archivo local `dashboard/data/fallback_data.csv` emitiendo la advertencia controlada en UI sin detener el servicio.
