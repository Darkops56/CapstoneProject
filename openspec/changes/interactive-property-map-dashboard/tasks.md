## 1. Fase 0: Firmas y Esqueletos de Interfaz (Stubs con NotImplementedError)

- [x] 1.1 Crear dataset consolidado semilla `data/fallback_data.csv` uniendo `producto1` y `producto2` y verificar existencia y encabezados con `python3 -c "import pandas as pd; df=pd.read_csv('data/fallback_data.csv'); assert len(df)==964"`
- [x] 1.2 Definir firmas y contratos de stubs con `NotImplementedError` en `src/config.py`, `src/data_loader.py`, `src/normalizer.py`, `src/map_view.py` y `src/ui_components.py` y verificar sintaxis con `python3 -m py_compile src/config.py src/data_loader.py src/normalizer.py src/map_view.py src/ui_components.py`
- [x] 1.3 Configurar `requirements.txt` acotado al runtime del dashboard y verificar consistencia de dependencias con `python3 -c "open('requirements.txt').read()"`

## 2. Fase 1: Arnés de Pruebas Deterministas en Rojo (Harness Red)

- [x] 2.1 Escribir suite de pruebas unitarias negativas y de frontera en `tests/test_dashboard.py` (simulación de fallas de Google Drive, conmutación por fallback, validación de bounding box CABA, degradación elegante de amenities y umbrales semafóricos `-5%` y `+10%`) y verificar fallo esperado (Red State) con `pytest tests/test_dashboard.py -v`
- [x] 2.2 Diseñar aserciones de escalabilidad y rendimiento vectorizado (filtro `< 50 ms` para `10.000` registros sintéticos) dentro de `tests/test_dashboard.py` y verificar ejecución con `pytest tests/test_dashboard.py -k test_filter_performance -v`

## 3. Fase 2: Implementación del Núcleo Lógico (Core Green)

- [x] 3.1 Implementar constantes de configuración y accesibilidad WCAG 2.2 en `src/config.py` y verificar con `python3 -c "import src.config as cfg; assert cfg.CABA_BBOX['lat_min'] == -34.71"`
- [x] 3.2 Implementar adaptador y normalizador de esquemas en `src/normalizer.py` (reconciliación Drive vs. Local, semáforo estándar, descarte geográfico CABA y discriminadores causales) y verificar paso a verde con `pytest tests/test_dashboard.py -k test_normalizer -v`
- [x] 3.3 Implementar cargador resiliente de Google Drive con conmutación determinista a fallback local en `src/data_loader.py` y verificar paso a verde con `pytest tests/test_dashboard.py -k test_data_loader -v`
- [x] 3.4 Implementar motor cartográfico WebGL en `src/map_view.py` (`pydeck.Deck` con `ScatterplotLayer`, radios por score, colores RGBA y basemap Carto Positron) y verificar instanciación determinista con `pytest tests/test_dashboard.py -k test_map_view -v`

## 4. Fase 3: Consumo en Frontera, Interfaz UI y Limpieza de Rama

- [x] 4.1 Implementar componentes modulares de interfaz y máquina de 5 estados en `src/ui_components.py` (barra superior de 1 fila, KPIs, selector de perfil, chips de precio, sidebar colapsable, ficha detallada y paginación acotada a 12 tarjetas) y verificar con `pytest tests/test_dashboard.py -k test_ui_components -v`
- [x] 4.2 Construir punto de entrada principal `app.py` integrando la tubería completa con `@st.cache_data` y manejo de estados en `st.session_state` y verificar sintaxis con `python3 -m py_compile app.py`
- [x] 4.3 Limpiar la rama eliminando artefactos históricos ajenos al runtime de producción del dashboard para dejar un clon liviano listo para deployment y verificar estado limpio con `git status --short`

## 5. Fase 4: Single Verification Command (SVC Exit Code 0) y Evidencia

- [x] 5.1 Ejecutar suite completa de tests deterministas verificando 100% de aserciones aprobadas con `pytest tests/test_dashboard.py -v`
- [x] 5.2 Levantar servidor local en background y certificar interacción visual y 0 errores de consola mediante `browser_subagent`
- [x] 5.3 Generar artefacto obligatorio de cierre `evidence.md` documentando la salida de los tests deterministas, métricas de latencia y evidencia visual

## 6. Fase 5: Refinamientos UX/UI y Contraste (Feedback Visual)

- [x] 6.1 Implementar formateo numérico de variables en `src/map_view.py` y verificar con `pytest tests/test_dashboard.py -k test_map_view_formatted_tooltips -v`
- [x] 6.2 Adaptar estilos de contraste y compatibilidad Dark Theme en `src/ui_components.py` y verificar con `python3 -m py_compile src/ui_components.py`
- [x] 6.3 Reemplazar multiselect de condición de precio por 3 checkboxes horizontales en `src/ui_components.py` y verificar lógica con `pytest tests/test_dashboard.py -k test_ui_components -v`
- [x] 6.4 Implementar contenedor con scroll independiente en panel derecho y reducción de margen superior con CSS en `app.py` y verificar sintaxis con `python3 -m py_compile app.py`
- [x] 6.5 Ejecutar suite completa y certificar con `pytest tests/test_dashboard.py -v` y verificación en `http://localhost:8501`
