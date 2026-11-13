# 02 · EDA Estadístico Profundo y Selección de las 10 Features (Fase 2)

## 1. Estadísticas Descriptivas y Análisis de Asimetría
Sobre las **`964` propiedades válidas** (`eda/eda_phase2.py`, guardado en `producto1/eda_stats.json`):

| Variable | Media | Mediana | IQR | Asimetría (`skew`) | Curtosis | `skew(log1p)` |
|---|---:|---:|---:|---:|---:|---:|
| `costo_total_ars` (Target) | 1,634,886.76 | 1,325,000.00 | 800,000.00 | **4.36** | 29.64 | **1.15** |
| `alquiler_ars` | 1,322,615.97 | 1,065,000.00 | 700,000.00 | 4.13 | 24.79 | 1.16 |
| `expensas_ars` | 312,270.79 | 250,000.00 | 190,000.00 | 5.18 | 54.81 | -6.23 *(ceros de exp. incluidas)* |
| `precio_m2_total_ars` | 25,000.56 | 23,888.89 | 7,416.20 | 1.45 | 3.81 | **0.28** |
| `m2_totales` | 64.37 | 57.00 | 30.00 | 3.57 | 24.20 | 0.81 |
| `ruido_db_promedio` | 70.46 | 72.50 | 5.00 | -0.49 | -0.13 | -0.71 |
| `densidad_delitos_500m` | 812.93 | 695.50 | 603.00 | 1.61 | 3.61 | 0.07 |
| `escuelas_familias_500m` | 10.90 | 11.00 | 6.00 | 0.13 | -0.27 | -1.50 |
| `distancia_subte_m` | 897.71 | 544.12 | 610.38 | 2.38 | 5.08 | -0.11 |
| `score_amenities` | 3.40 | 2.50 | 4.50 | 0.94 | -0.18 | -0.12 |

**Por qué importa la asimetría (`4.36` en `costo_total_ars`):**
1. Invalida el supuesto de normalidad para tests paramétricos puros (confirmado por **Shapiro-Wilk**: $W = 0.6182, p = 8.93 \times 10^{-32}$ en `costo_total_ars` y $W = 0.8912, p = 2.49 \times 10^{-18}$ en `precio_m2_total_ars`).
2. Justifica usar **mediana + IQR** como medidas robustas, **pruebas no paramétricas (Mann-Whitney U, Kruskal-Wallis, Spearman)** en el EDA y transformar el target con **`log1p` / `expm1`** en XGBoost para estabilizar la varianza y evitar que pocos departamentos de lujo dominen el error cuadrático.

---

## 2. Pruebas de Hipótesis ($\alpha = 0.05$)

| Hipótesis / Contraste | Test(s) Aplicado(s) | Estadístico y $p$-valor | Hallazgo de Negocio |
|---|---|---|---|
| **H1 · Ruido diurno (`> 65 dBA`, $n=801$ vs. `<= 65 dBA`, $n=163$) sobre `precio_m2_total_ars`** | Mann-Whitney U + Welch $t$ + Levene (`p=0.268`) | $U = 54,292.5$, $p = 6.96 \times 10^{-4}$ · $t = -3.19$, $p = 1.62 \times 10^{-3}$ | **Rechazo $H_0$:** las zonas tranquilas (`<= 65 dBA`) tienen mediana `\$25,229.21/m²` vs. `\$23,611.11/m²` en ruidosas (**+6.9% de prima ambiental**). |
| **H2 · Cercanía al subte (`<= 600 m`, $n=526$ vs. `> 600 m`, $n=438$) sobre `precio_m2_total_ars`** | Mann-Whitney U | $U = 98,375.5$, $p = 9.33 \times 10^{-5}$ | **Rechazo $H_0$:** diferencia significativa entre corredores con subte y zonas residenciales alejadas (`\$23,317.46` vs. `\$24,528.30/m²`, reflejando barrios residenciales de ticket alto sin subte como zonas de Belgrano/Palermo/Devoto). |
| **H3 · `apto_mascotas` (`1`, $n=266$ vs. `0`, $n=698$) sobre `precio_m2_total_ars`** | Mann-Whitney U | $U = 93,916.5$, $p = 0.7795$ | **No rechazo $H_0$:** aceptar mascotas (`\$24,074.87` vs. `\$23,833.33/m²`) **no encarece el m²**; actúa como filtro de elegibilidad corporativa sin sobreprecio sistemático. |
| **H4 · Macro-barrios ($n \ge 15$) sobre `precio_m2_total_ars`** | Kruskal-Wallis + ANOVA | $H = 196.38$, $p = 1.90 \times 10^{-37}$ · $F = 22.35$, $p = 1.11 \times 10^{-34}$ | **Rechazo $H_0$:** fuerte segmentación geográfica; lideran **Palermo** (`\$28,928.57/m²`) y **Belgrano** (`\$26,891.68/m²`) frente a **Balvanera** (`\$20,125.00/m²`). |
| **H5 · Clústeres urbanos preliminares (`K=3` sobre entorno)** | Kruskal-Wallis + ANOVA | $H = 64.30$, $p = 1.09 \times 10^{-14}$ · $F = 35.34$, $p = 1.55 \times 10^{-15}$ | **Rechazo $H_0$:** el entorno urbano por sí solo separa niveles distintos de valor inmobiliario. |
| **H6 · Dolarización por barrio (`barrio` × `moneda_origen`)** | $\chi^2$ de independencia | $\chi^2 = 141.92$, $gl = 9$, $p = 4.13 \times 10^{-26}$ | **Rechazo $H_0$:** la proporción de contratos en USD depende fuertemente del barrio. |

**Correlaciones Spearman más fuertes con `costo_total_ars`:**
`m2_totales` ($\rho = 0.8210$), `m2_cubiertos` ($\rho = 0.8013$), `ambientes` ($\rho = 0.6029$), `banos` ($\rho = 0.5891$), `dormitorios` ($\rho = 0.5880$), `score_amenities` ($\rho = 0.5408$), `cocheras` ($\rho = 0.5332$), `antiguedad_anios` ($\rho = -0.3245$).

---

## 3. Análisis de Multicolinealidad (VIF) + Feature Importance (RF & MI)
Partimos de **22 variables candidatas** (sin leakage). Primero evaluamos su poder predictivo combinando **Random Forest** (sobre `costo_total_ars` y `log1p(costo_total_ars)`) y **Mutual Information (`mutual_info_regression`)**, obteniendo un `combined_signal_score ∈ [0, 1]`.

Luego aplicamos **eliminación iterativa por VIF (`umbral < 5.0`)**, descartando en cada paso la variable redundante de menor señal predictiva (protegiendo los pilares obligatorios `apto_mascotas` y `score_amenities`):
1. `indice_gravedad_delitos_500m` (`VIF = 148.14`, score `0.0272`) — colineal con `densidad_delitos_500m` y `densidad_robos_500m`.
2. `densidad_robos_500m` (`VIF = 370.27`, score `0.0280`) — colineal con `densidad_delitos_500m`.
3. `score_amenities_soltero` (`VIF = 47.04`, score `0.1984`) — colineal con `score_amenities`.
4. `score_amenities_familia` (`VIF = 22.48`, score `0.2366`) — colineal con `score_amenities`.
5. `dormitorios` (`VIF = 6.67`, score `0.1427`) — colineal con `ambientes` y `m2_totales`.
6. `m2_cubiertos` (`VIF = 8.02`, score `0.7080`) — colineal con `m2_totales` (que tenía mayor señal `0.9734`).

---

## 4. Las 10 Features Finales Seleccionadas y su Justificación
Garantizando cobertura de **características físicas**, **entorno urbano completo** (ruido, delito, educación, transporte), **`apto_mascotas`** y **`score_amenities`**:

| # | Feature | Pilar | Score Combinado (RF + MI) | VIF Final | Por qué quedó seleccionada |
|---:|---|---|---:|---:|---|
| 1 | `m2_totales` | Físico | 0.9734 | 2.36 | Predictor #1 de tamaño y precio ($\rho = 0.821$); superó a `m2_cubiertos`. |
| 2 | `banos` | Físico | 0.1629 | 1.81 | Diferencia unidades premium/familiares de monoambientes a igual m². |
| 3 | `score_amenities` | Amenities *(obligatoria)* | 0.1551 | 1.55 | Resume amenidades del edificio sin colinealidad con sub-scores. |
| 4 | `ambientes` | Físico | 0.1498 | 1.78 | Captura distribución interna mejor que `dormitorios` (sin VIF alto). |
| 5 | `cocheras` | Físico | 0.1152 | 1.74 | Activo escaso en CABA con fuerte prima en `FAMILIA` y ejecutivos. |
| 6 | `distancia_escuela_m` | Entorno · Educación | 0.0586 | 1.07 | Mayor señal RF+MI dentro del eje educativo que `escuelas_familias_500m`. |
| 7 | `lineas_subte_600m` | Entorno · Transporte | 0.0472 | 2.24 | Mayor información mutua (`0.0777`) en conectividad que `distancia_subte_m`. |
| 8 | `densidad_delitos_500m` | Entorno · Seguridad | 0.0348 | 2.31 | Representante de menor colinealidad del eje delictivo tras VIF. |
| 9 | `ruido_db_promedio` | Entorno · Acústico | 0.0253 | 1.09 | Externalidad ambiental significativa (H1: $p = 6.96 \times 10^{-4}$). |
| 10 | `apto_mascotas` | Elegibilidad *(obligatoria)* | 0.0110 | 1.01 | Restricción crítica de RR.HH. curada con NLP anti-negaciones. |

Todas las features finales tienen **`VIF <= 2.36`** (muy por debajo del umbral crítico `5.0`–`10.0`), eliminando redundancia antes de entrenar K-Means y XGBoost.
