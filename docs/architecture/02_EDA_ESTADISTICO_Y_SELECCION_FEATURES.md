# 02 · EDA Estadístico Profundo y Selección de las 10 Features

## 1. Estadísticas Descriptivas y Análisis de Asimetría
Implementado en `src/eda/eda_phase2.py` sobre el dataset curado base:

| Variable | Media | Mediana | IQR | Asimetría (`skew`) | Curtosis | `skew(log1p)` |
|---|---:|---:|---:|---:|---:|---:|
| `costo_total_ars` (Target) | 1,634,886.76 | 1,325,000.00 | 800,000.00 | **4.36** | 29.64 | **1.15** |
| `alquiler_ars` | 1,322,615.97 | 1,065,000.00 | 700,000.00 | 4.13 | 24.79 | 1.16 |
| `expensas_ars` | 312,270.79 | 250,000.00 | 190,000.00 | 5.18 | 54.81 | -6.23 |
| `precio_m2_total_ars` | 25,000.56 | 23,888.89 | 7,416.20 | 1.45 | 3.81 | **0.28** |
| `m2_totales` | 64.37 | 57.00 | 30.00 | 3.57 | 24.20 | 0.81 |
| `ruido_db_promedio` | 70.46 | 72.50 | 5.00 | -0.49 | -0.13 | -0.71 |
| `densidad_delitos_500m` | 812.93 | 695.50 | 603.00 | 1.61 | 3.61 | 0.07 |
| `distancia_escuela_m` | 185.30 | 166.18 | 120.40 | 1.84 | 4.12 | 0.15 |
| `lineas_subte_600m` | 0.85 | 1.00 | 1.00 | 1.12 | 0.54 | 0.62 |
| `score_amenities` | 3.40 | 2.50 | 4.50 | 0.94 | -0.18 | -0.12 |

**Implicancias de la Asimetría:**
1. Invalida el supuesto de normalidad para pruebas paramétricas estándar (Shapiro-Wilk $p < 10^{-15}$).
2. Justifica el uso de **mediana e IQR** como estimadores centrales robustos y pruebas no paramétricas (Mann-Whitney U, Kruskal-Wallis, Spearman).
3. Determina la necesidad de transformar el target con **`log1p` / `expm1`** en el modelo de regresión para estabilizar la varianza frente a propiedades de lujo.

---

## 2. Pruebas de Hipótesis ($\alpha = 0.05$)

| Hipótesis / Contraste | Test(s) Aplicado(s) | Estadístico y $p$-valor | Hallazgo de Negocio |
|---|---|---|---|
| **H1 · Ruido diurno (`> 65 dBA` vs. `<= 65 dBA`) sobre `precio_m2`** | Mann-Whitney U + Welch $t$ | $U = 54,292.5$, $p = 6.96 \times 10^{-4}$ | **Rechazo $H_0$:** las zonas tranquilas presentan una prima ambiental de **+6.9%** en el precio por metro cuadrado. |
| **H2 · Cercanía al subte (`<= 600 m` vs. `> 600 m`) sobre `precio_m2`** | Mann-Whitney U | $U = 98,375.5$, $p = 9.33 \times 10^{-5}$ | **Rechazo $H_0$:** diferencia significativa entre corredores céntricos y barrios residenciales periféricos sin subte. |
| **H3 · `apto_mascotas` (`1` vs. `0`) sobre `precio_m2`** | Mann-Whitney U | $U = 93,916.5$, $p = 0.7795$ | **No rechazo $H_0$:** aceptar mascotas **no encarece el metro cuadrado**; actúa como filtro de elegibilidad corporativa. |
| **H4 · Macro-barrios sobre `precio_m2`** | Kruskal-Wallis + ANOVA | $H = 196.38$, $p = 1.90 \times 10^{-37}$ | **Rechazo $H_0$:** fuerte dispersión territorial liderada por Palermo y Belgrano frente al sur y centro. |
| **H5 · Clústeres urbanos sobre valor inmobiliario** | Kruskal-Wallis | $H = 64.30$, $p = 1.09 \times 10^{-14}$ | **Rechazo $H_0$:** el entorno urbano por sí solo segmenta niveles diferenciados de costo inmobiliario. |

---

## 3. Selección de Features (VIF < 5.0)

Se evaluaron 22 variables iniciales mediante **Random Forest Importance** y **Mutual Information**, aplicando descarte iterativo de multicolinealidad:

1. Descarte de `indice_gravedad_delitos_500m` ($\text{VIF} = 148.14$) y `densidad_robos_500m` ($\text{VIF} = 370.27$) por colinealidad con `densidad_delitos_500m`.
2. Descarte de sub-scores de amenidades por colinealidad con `score_amenities`.
3. Descarte de `dormitorios` y `m2_cubiertos` por alta redundancia frente a `ambientes` y `m2_totales`.

El vector final consolidó **10 features con $\text{VIF} \le 2.36$**, preservando representación completa de dimensiones físicas, ambientales, de conectividad y restricciones de negocio. Las figuras resultantes se encuentran versionadas en `src/eda/figures/`.
