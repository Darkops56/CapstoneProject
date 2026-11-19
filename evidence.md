# Reporte de Evidencia de Implementación (SVC Exit Code 0)

**Capacidad:** `interactive-property-map-dashboard`  
**Rama:** `interactive_property_map_dashboard` (aislada y limpia para deployment directo)  
**Fecha:** 2026-11-19  
**Resultado Global:** Aprobado (11/11 tests unitarios y de integración + Verificación E2E autónoma con `browser_subagent`).

---

## 1. Salida de la Suite de Pruebas Deterministas (`pytest tests/test_dashboard.py -v`)

```
============================= test session starts ==============================
platform linux -- Python 3.14.4, pytest-9.2.0, pluggy-1.7.0 -- /usr/bin/python3
cachedir: .pytest_cache
rootdir: /home/luka/.gemini/antigravity/worktrees/CapstoneProject/interactive_property_map_dashboard
plugins: anyio-4.16.0, typeguard-4.4.4
collecting ... collected 11 items

tests/test_dashboard.py::test_classify_price_status_boundaries PASSED    [  9%]
tests/test_dashboard.py::test_normalizer_missing_required_columns PASSED [ 18%]
tests/test_dashboard.py::test_normalizer_caba_bbox_drop PASSED           [ 27%]
tests/test_dashboard.py::test_normalizer_drive_schema_aliases PASSED     [ 36%]
tests/test_dashboard.py::test_normalizer_amenities_graceful_degradation PASSED [ 45%]
tests/test_dashboard.py::test_data_loader_fallback_when_unconfigured PASSED [ 54%]
tests/test_dashboard.py::test_data_loader_fallback_on_drive_error PASSED [ 63%]
tests/test_dashboard.py::test_map_view_deck_structure PASSED             [ 72%]
tests/test_dashboard.py::test_map_view_formatted_tooltips PASSED         [ 81%]
tests/test_dashboard.py::test_ui_components_filter_logic PASSED          [ 90%]
tests/test_dashboard.py::test_filter_performance PASSED                  [100%]

============================== 11 passed in 0.58s ==============================
```

---

## 2. Evidencia de Verificación E2E con Navegador Autónomo (`browser_subagent`)

El subagente de navegador verificó los 5 refinamientos en `http://localhost:8501` en viewport de escritorio (`1440x900`):

1. **Scroll Independiente en Panel de Inmuebles (`st.container(height=580)`)**:
   - `div[data-testid="stVerticalBlock"]` opera con `computedHeight: 580px`, `overflowY: auto`.
   - Se certificó que el panel de tarjetas scrollea verticalmente sin desplazar la página (`window.scrollY = 0`), manteniendo el mapa y la barra superior fijos en pantalla.
2. **Margen Superior Compacto**:
   - Inyección CSS (`padding-top: 1.2rem !important`) redujo el padding a `19.2px`. El encabezado comienza a `35px` del tope del viewport.
3. **Contraste y Compatibilidad con Dark Theme**:
   - Tarjetas diseñadas en azul oscuro (`rgb(30, 41, 59)`) con títulos en blanco puro (`rgb(255, 255, 255)`), precios destacados en cyan brillante (`rgb(56, 189, 248)`) y leyendas translúcidas con contraste accesible WCAG 2.2 superior a 4.5:1.
4. **Formateo Numérico en Tooltips de PyDeck**:
   - Verificado al pasar el mouse por los puntos del mapa: renderiza valores numéricos reales (`$1,150,000 ARS`, `+0.2%`, `64.1 / 100`) sin exponer sintaxis cruda `{costo_total_ars:,.0f}`.
5. **Checkboxes de Precio y KPIs Dinámicos**:
   - Condición de precio implementada con 3 checkboxes (`🟢 Oportunidad`, `🟡 Justo`, `🔴 Sobreprecio`) sin truncamiento de texto.
   - Los KPIs superiores se actualizan reactivamente al desmarcar/marcar opciones (ej. de 964 a 601 al desmarcar Oportunidad).
6. **Auditoría de Consola**: **0 errores JavaScript y 0 excepciones Python**.
