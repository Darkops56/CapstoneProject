# Proposal: Saneamiento y Reestructuración Limpia del Monorepo

## Tier de Complejidad
**Tier M (Estructural / Refactor de Higiene)**: Reorganización integral de la raíz del repositorio para consolidar documentación dispersa, eliminar riesgos de seguridad por scripts con tokens en texto plano, reubicar fixtures de prueba y estandarizar la nomenclatura de módulos hacia convenciones profesionales (`mlops/`, `etl/output/`, `docs/`), garantizando cero regresión mediante la suite de tests existente.

## Why
Actualmente la raíz de `main` acumula 22 carpetas y archivos sueltos. Esta dispersión genera ruido cognitivo y problemas operativos:
1. **Riesgo de Seguridad**: El archivo `ObtenerJsonApify.py` en la raíz contiene un API Token de Apify expuesto en texto plano.
2. **Documentación Fragmentada**: Existen múltiples ubicaciones desconectadas para la documentación (`docs/`, `explicacion/`, `Feature.md`, `PreguntasNegocio.txt`, `evidence.md`).
3. **Ambigüedad en Datos**: La carpeta `data/` en la raíz solo contiene dos muestras de datos que actúan como fixtures de prueba para Apify, generando la falsa expectativa de que el proyecto o el dashboard dependen de ellos localmente.
4. **Nomenclatura Académica**: Los directorios `producto1/` y `producto2/` responden al cronograma de entregas de la cátedra universitaria en lugar de reflejar sus responsabilidades arquitectónicas (`etl/output/` y `mlops/`).

Reestructurar el monorepo bajo estándares limpios hace el proyecto inmediatamente comprensible para cualquier desarrollador, elimina vulnerabilidades de credenciales y prepara la base para el versionado de modelos.

## What Changes
- **Consolidación de Documentación en `docs/`**:
  - Mover los 5 documentos de arquitectura de `explicacion/` a `docs/architecture/`.
  - Mover `Feature.md` a `docs/feature_selection.md`.
  - Mover `PreguntasNegocio.txt` a `docs/business_questions.md`.
  - Mover `evidence.md` a `docs/evidence/evidence_consolidation.md`.
  - Eliminar los directorios y archivos huérfanos resultantes.
- **Saneamiento de Seguridad en Scripts**:
  - Mover `ObtenerJsonApify.py` a `scripts/fetch_apify_raw.py`.
  - Reemplazar el token hardcodeado por `os.environ.get("APIFY_TOKEN")` con validación defensiva.
- **Higiene de Fixtures de Prueba**:
  - Trasladar los archivos de muestra `data/curated_sample_output.csv` y `data/sample_raw_listings.json` a `tests/fixtures/`.
  - Eliminar el directorio `data/` de la raíz.
- **Estandarización de Módulos (MLOps & ETL)**:
  - Renombrar conceptualmente `producto2/` a `mlops/` preservando compatibilidad retroactiva mediante alias o actualización en `config/settings.py`.
  - Mover los artefactos entregables de `producto1/` a `etl/output/`.
  - Actualizar `config/settings.py` para resolver las nuevas rutas manteniendo aliases transparentes para no romper tests existentes.
- **Limpieza de Cachés**:
  - Remover `.matplotlib_cache/` del disco de trabajo.

## Capabilities

### New Capabilities
- `monorepo-hygiene`: Define la topología limpia de directorios del monorepo, los estándares de almacenamiento de documentación en `docs/`, la cuarentena de credenciales en `scripts/` y la resolución centralizada de paths en `config/settings.py`.

### Modified Capabilities
*(Ninguna. El contrato de datos con Google Drive y el dashboard permanecen inalterados).*

## Assumptions Eradication
- **Supuesto 1**: *Mover `producto1` y `producto2` romperá los scripts de tests existentes (`tests/test_producto2.py`, `tests/test_etl_and_eda.py`).*  
  **Hecho comprobado**: `config/settings.py` centraliza la resolución de rutas de todo el proyecto. Si `settings.py` expone las rutas actualizadas y mantiene compatibilidad hacia atrás, todos los tests continuarán pasando sin alteraciones destructivas.
- **Supuesto 2**: *El script `ObtenerJsonApify.py` es necesario en tiempo de ejecución para n8n o Streamlit.*  
  **Hecho comprobado**: Falso. n8n interactúa con Apify vía HTTP Request directamente en la nube, y Streamlit consume Google Drive. El script es una utilidad manual de depuración.

## Non-Goals
- No se reescribirán los algoritmos de inferencia ni la lógica de visualización del dashboard.
- No se alterarán los workflows de n8n existentes.

## Impact
- **Archivos afectados**: `config/settings.py`, `ObtenerJsonApify.py`, `Feature.md`, `PreguntasNegocio.txt`, `evidence.md`, `explicacion/`, `data/`.
- **Compatibilidad**: Se verifica mediante la ejecución de `pytest` asegurando que los 33 tests pasen al 100%.
