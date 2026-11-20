# 01 · ETL, NLP y Enriquecimiento Geoespacial

## 1. Definición de la Variable Objetivo (`costo_total_ars`) y Unificación Monetaria
Para una empresa que relocaliza empleados, el costo mensual real no es solo el alquiler publicado sino **`alquiler_ars + expensas_ars`**.
- **Parámetros configurables en `src/config/settings.py`:**
  - `TIPO_CAMBIO_BASE = 1200.0`
  - `FACTOR_IMPUESTOS_USD = 1.0`
  - `IMPUESTO_SELLOS_ALQUILER = 0.0`
- **Fórmula aplicada en `parse_price_ars()`:**
  - Si `moneda == "USD"`: `alquiler_ars = precio * TIPO_CAMBIO_BASE * FACTOR_IMPUESTOS_USD * (1 + IMPUESTO_SELLOS_ALQUILER)`
  - Si `moneda == "ARS"`: `alquiler_ars = precio * (1 + IMPUESTO_SELLOS_ALQUILER)`
- **Prevención de Data Leakage:** al definir `costo_total_ars = alquiler_ars + expensas_ars` como target de regresión, **`alquiler_ars`, `expensas_ars` y `precio_m2_*` se excluyen del conjunto de features predictivas**. De lo contrario, el modelo "haría trampa" usando componentes directos del target.

---

## 2. Limpieza y NLP sobre Datos Inmobiliarios
Implementado en `src/etl/etl_pipeline.py` y empaquetado para producción en `actors/inference/src/nlp_parser.py`:
1. **Deduplicación (`listing_id`):** Detección e invalidación de duplicados.
2. **Precios inválidos:** Descarte de registros con valor 0 o leyendas "Consultar precio".
3. **Rescate y validación de coordenadas:**
   - Rescate de publicaciones con coordenadas aproximadas en `location` (`ubicacion_aproximada = 1`).
   - Filtrado estricto de coordenadas corruptas fuera del bounding box oficial de CABA (`lat ∈ [-34.72, -34.50]`, `lon ∈ [-58.58, -58.32]`).
4. **Superficie (`m2_totales`, `m2_cubiertos`) y atributos físicos:**
   - Descarte de inconsistencias físicas severas (`m2 <= 10` o `> 2000`).
   - Imputación de `m2_cubiertos` faltantes mediante la razón mediana observada según tipología.
   - Normalización de ambientes y dormitorios.
5. **Extracción e imputación de Expensas (`extract_expenses_ars()`):**
   - Extracción de campos estructurados.
   - Detección de patrones textuales como `"EXPENSAS INCLUIDAS"` / `"sin expensas"` asignando `0.0 ARS`.
   - Extracción mediante regex estricta posterior a la mención de expensas.
   - Imputación de faltantes con la mediana del barrio por $m^2$, dejando la bandera `expensas_imputadas = 1`.
6. **NLP de Mascotas (`apto_mascotas`) — Prioridad de negaciones:**
   - Combinación de tags estructurados con regex sobre la descripción textual.
   - **Regla crítica anti-falsos positivos:** si la publicación tiene tag positivo pero el texto dice explícitamente *"No se aceptan mascotas"* o variantes, la negación prevalece y revierte la etiqueta (`nlp_negation_override`).
7. **Amenities (`score_amenities` + diferenciación por perfil):**
   - Detección binaria de amenidades: gimnasio, pileta, parrilla, SUM/coworking, seguridad y balcón/terraza.
   - Ponderación balanceada (`score_amenities`) y adaptaciones para sub-perfiles (`FAMILIA` vs. `SOLTERO_EJECUTIVO`).

---

## 3. Cruce Geoespacial con las Capas Urbanas de CABA
El pipeline enriquece cada propiedad mediante spatial joins y árboles de distancia Haversine:
1. **Ruido Diurno:**
   - Asociación mediante `gpd.sjoin(..., predicate="within")` contra polígonos acústicos de CABA, con fallback a `sjoin_nearest` para parcelas ubicadas sobre calzadas.
2. **Delitos Oficiales:**
   - Normalización decimal de coordenadas desplazadas en datos policiales.
   - Consulta con `BallTree(metric="haversine")` a **500 m** para obtener `densidad_delitos_500m`.
3. **Establecimientos Educativos:**
   - Reproyección desde la coordenada local histórica de CABA a WGS84 (`EPSG:4326`).
   - Filtrado de niveles formativos (inicial, primario, secundario) y cómputo de `distancia_escuela_m`.
4. **Bocas de Subte:**
   - Cálculo de la distancia mínima a la red de transporte masivo y conteo de `lineas_subte_600m`.

---

## 4. Portabilidad y Caché Productivo
Para la ejecución serverless mensual en Apify (`actors/inference/`), estos cruces espaciales no requieren conectarse a APIs externas ni cargar shapefiles gigantescos; se ejecutan en memoria consumiendo el geo-caché optimizado en Parquet y BallTree (`actors/inference/reference_geo/`), permitiendo enriquecer 1,000 publicaciones en menos de 10 segundos con menos de 512 MB de RAM.
