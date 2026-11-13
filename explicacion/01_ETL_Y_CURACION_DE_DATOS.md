# 01 · ETL, NLP y Enriquecimiento Geoespacial (Fase 1)

## 1. Definición de la Variable Objetivo (`costo_total_ars`) y Unificación Monetaria
Para una empresa que relocaliza empleados, el costo mensual real no es solo el alquiler publicado sino **`alquiler_ars + expensas_ars`**.
- **Parámetros configurables en `config/settings.py`:**
  - `TIPO_CAMBIO_BASE = 1200.0`
  - `FACTOR_IMPUESTOS_USD = 1.0`
  - `IMPUESTO_SELLOS_ALQUILER = 0.0`
- **Fórmula aplicada en `parse_price_ars()`:**
  - Si `moneda == "USD"`: `alquiler_ars = precio * TIPO_CAMBIO_BASE * FACTOR_IMPUESTOS_USD * (1 + IMPUESTO_SELLOS_ALQUILER)`
  - Si `moneda == "ARS"`: `alquiler_ars = precio * (1 + IMPUESTO_SELLOS_ALQUILER)`
- **Prevención de Data Leakage:** al definir `costo_total_ars = alquiler_ars + expensas_ars` como target de regresión, **`alquiler_ars`, `expensas_ars` y `precio_m2_*` se excluyen del conjunto de features predictivas**. De lo contrario, el modelo "haría trampa" usando componentes directos del target.

---

## 2. Limpieza y NLP sobre `zonaprop_alquileres_caba_1000.json`
De **972 registros crudos** (755 en ARS y 217 en USD):
1. **Deduplicación (`listing_id`):** `0` duplicados.
2. **Precios inválidos:** se descartó `1` registro con `USD 0` ("Consultar precio", ID `60636646`).
3. **Rescate y validación de coordenadas:**
   - `23` publicaciones tenían `list_latitude`/`list_longitude` nulos, pero sí poseían coordenadas válidas en `location.latitude` / `location.longitude` (`visibility == "ZONE"`). Se rescataron marcando `ubicacion_aproximada = 1`.
   - Se filtraron **`5` publicaciones con coordenadas corruptas fuera del bounding box de CABA** (`lat ∈ [-34.72, -34.50]`, `lon ∈ [-58.58, -58.32]`):
     - `60237881` (duplicó longitud en latitud: `-58.41, -58.41`), `60596461` (`-34.99, -64.96` Córdoba), `59410226` (`-34.726, -58.34`), `60169250` (`-33.32, -60.21` San Nicolás), `59512081` (`-34.76, -58.42` Lomas de Zamora).
     - **Por qué se eliminaron:** mantener coordenadas erróneas a cientos de kilómetros corrompe `sjoin_nearest` y `BallTree`, asignando ruido/delitos/escuelas falsos.
4. **Superficie (`m2_totales`, `m2_cubiertos`) y atributos físicos:**
   - Se descartaron `2` registros con `m2` inválidos (`<= 10 m²` o `> 2000 m²` o faltantes irrecuperables), quedando **`964` propiedades válidas**.
   - Si faltaba `m2_cubiertos`, se imputó usando la razón mediana `m2_cubiertos / m2_totales`; si `m2_cubiertos > m2_totales`, se ajustó por coherencia física.
   - `dormitorios` faltantes (`5` monoambientes) se imputaron como `max(ambientes - 1, 0)`; `banos` (`5`) por mediana según `ambientes`; `antiguedad_anios` (`25`, convirtiendo `"A estrenar"` a `0`) por mediana del `barrio`.
5. **Extracción e imputación de Expensas (`extract_expenses_ars()`):**
   - `903` desde campo estructurado `prices.detailPricesArray[0].expenses`.
   - `6` detectadas como `"EXPENSAS INCLUIDAS"` / `"sin expensas"` (`0.0 ARS`, evitando capturar por error el valor del alquiler previo en frases como `"VALOR MENSUAL: $2.200.000 – EXPENSAS INCLUIDAS"`).
   - `4` extraídas mediante regex estricta *posterior* a la palabra `"expensas"` (ej. `"EXPENSAS (oct 26) $ 172.000"`).
   - `51` faltantes imputadas con la **mediana de `expensas/m²` del mismo `barrio` multiplicada por `m2_totales`**, dejando la bandera `expensas_imputadas = 1`.
6. **NLP de Mascotas (`apto_mascotas`) — Prioridad de negaciones:**
   - Se combinaron `detailExtraTopLevel.pills` (`ADMITS_PETS`), `featuresListCardSimplified` (`1000002`) y regex sobre `description`.
   - **Hallazgo crítico:** `4` publicaciones tenían la etiqueta estructurada "Permite mascotas" pero el texto decía explícitamente *"No se aceptan mascotas"* / *"No acepta mascotas"* (IDs `59614714`, `60310854`, `60398145`, `60581124`). La regla NLP de negación prevalece y corrige esos 4 falsos positivos (`nlp_negation_override`).
   - Resultado final: `266` apto mascotas (`240` estructurado + `26` NLP positivo) y `698` no apto.
7. **Amenities (`score_amenities` + diferenciación por perfil):**
   - Se extrajo presencia binaria (estructurado + NLP) de: `gimnasio` (`1000068`), `pileta` (`1000079`), `parrilla` (`1000078`/`1000085`), `sum/coworking` (`1000092`), `seguridad/vigilancia` (`1000097`/`2000142`/`1000039`), `balcon_terraza` (`1000100`/`1000116`/`1000114`) y `cochera` (`CFT7`/`1000018`).
   - Se calcularon `score_amenities` (0–10 balanceado), `score_amenities_soltero` (mayor peso a gimnasio, SUM/coworking, balcón) y `score_amenities_familia` (mayor peso a seguridad, cochera, pileta, parrilla).

---

## 3. Cruce Geoespacial con las 4 Capas Urbanas de CABA
1. **Ruido Diurno (`medicion_de_ruido_diurno_2018.csv` — 167 polígonos WKT `EPSG:4326`):**
   - Se amplió `csv.field_size_limit` (manejando el límite `2^31 - 1` de C `long` en Windows 64-bit).
   - `gpd.sjoin(..., predicate="within")` resolvió `288` propiedades; las `676` restantes se imputaron con `gpd.sjoin_nearest` en proyección métrica local de CABA.
   - **Por qué `676` cayeron en `sjoin_nearest`:** el mapa acústico de CABA modela polígonos de **calzadas/avenidas**, no el centro de la parcela edilicia; por eso el 50% de esos puntos estuvo a menos de **`4.50 m`** de un polígono, el 95% a menos de **`17.81 m`** y el máximo a **`47.65 m`**.
2. **Delitos 2022 (`delitos_2022.xlsx` — 140,918 filas):**
   - Se identificaron **`2,385` nulos** exactos en `latitud`/`longitud` y coordenadas con punto decimal desplazado (ej. `-34584136.0` o `1e16`).
   - `normalize_caba_coord()` divide sucesivamente por `10` hasta caer en el rango CABA; solo `5` registros fueron irrecuperables, quedando **`138,528` delitos válidos**.
   - Con `BallTree(metric="haversine")` a **500 m** se calcularon: `densidad_delitos_500m`, `densidad_robos_500m` y `indice_gravedad_delitos_500m` (Homicidios peso `10`, `uso_arma == 'SI'` peso `4`, Robo/Lesiones peso `2`, otros peso `1`, multiplicados por `cantidad`).
3. **Establecimientos Educativos (`establecimientos_educativos.xlsx` — 2,767 filas):**
   - Su geometría venía en proyección local Gauss-Krüger de CABA (`+proj=tmerc +lat_0=-34.6297166 +lon_0=-58.4627 ...`), **no en WGS84**. Se reproyectó a `EPSG:4326` con `GeoPandas`/`pyproj`.
   - Se filtraron niveles familiares (`Nivel inicial`, `Nivel primario`, `Nivel secundario común`), obteniendo **`1,862` escuelas**, y con `BallTree` Haversine se calculó `escuelas_familias_500m` y `distancia_escuela_m`.
4. **Bocas de Subte (`bocas-de-subte.csv` — 379 bocas, 6 líneas `A, B, C, D, E, H`):**
   - En `EPSG:4326`, con `BallTree` Haversine se calcularon `distancia_subte_m` (distancia mínima) y `lineas_subte_600m` (cantidad de líneas distintas a menos de 600 m).

---

## 4. Auditoría de Outliers (IQR y Z-Score) y Unificación en `Datasets/`
Se detectaron outliers mediante `1.5 * IQR` y `|Z-score| > 3` (dejando banderas `outlier_iqr_*` y `outlier_zscore_*` sin eliminar datos reales de lujo para no sesgar el mercado):
- **`costo_total_ars`**: `Q1 = \$1,030,000`, `Q3 = \$1,830,000`, `IQR = \$800,000` (techo `\$3,030,000`) → `72` IQR (`7.47%`), `19` Z-score (`1.97%`).
- **`precio_m2_total_ars`**: `Q1 = \$20,583.80`, `Q3 = \$28,000.00`, `IQR = \$7,416.20` → `44` IQR (`4.56%`), `14` Z-score (`1.45%`).
- **`m2_totales`**: `Q1 = 45.0`, `Q3 = 75.0`, `IQR = 30.0` (techo `120.0`) → `37` IQR (`3.84%`), `18` Z-score (`1.87%`).

Además, se exportaron los 5 datasets individuales curados en formato `.csv` unificado (`UTF-8`, `EPSG:4326`) en `Datasets/Curados/`, separados de `Datasets/Originales/`.
