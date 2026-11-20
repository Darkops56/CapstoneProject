# Matriz de Selección de Features, Importancia y VIF

Este documento detalla la justificación estadística y matemática del conjunto final de **10 variables predictivas ortogonales** seleccionadas para estimar el costo total mensual (`costo_total_ars`) y alimentar los modelos de Machine Learning (K-Means y XGBoost).

---

## 📊 Tabla Consolidada de Features Seleccionadas

El proceso de selección combinó la señal predictiva conjunta de **Random Forest** y **Mutual Information (`mutual_info_regression`)** con un proceso iterativo de descarte por Factor de Inflación de la Varianza (**VIF**), manteniendo estrictamente un $\text{VIF} \le 2.36$ (muy por debajo del límite crítico de $5.0$).

| # | Feature Final | Pilar de Información | Score Combinado (RF + MI) | VIF Final | Justificación de Selección y Negocio |
| :---: | :--- | :--- | :---: | :---: | :--- |
| **1** | `m2_totales` | Atributo Físico | 0.9734 | 2.36 | Predictor principal de tamaño y costo ($\rho = 0.821$). Superó a `m2_cubiertos` por menor colinealidad. |
| **2** | `banos` | Atributo Físico | 0.1629 | 1.81 | Diferencia tipologías familiares y de alta gama frente a monoambientes a igual superficie. |
| **3** | `score_amenities` | Amenities *(Obligatoria)* | 0.1551 | 1.55 | Resume comodidades clave (pileta, gimnasio, SUM, parrilla) sin redundancia. |
| **4** | `ambientes` | Atributo Físico | 0.1498 | 1.78 | Captura la compartimentación funcional de la vivienda mejor que dormitorios. |
| **5** | `cocheras` | Atributo Físico | 0.1152 | 1.74 | Activo altamente escaso en CABA con impacto directo en el perfil corporativo. |
| **6** | `distancia_escuela_m` | Entorno Urbano (Educación) | 0.0586 | 1.07 | Mayor señal RF+MI dentro del pilar educativo que el conteo en radio de 500m. |
| **7** | `lineas_subte_600m` | Entorno Urbano (Transporte) | 0.0472 | 2.24 | Representa la conectividad multimodal y accesibilidad a transporte masivo. |
| **8** | `densidad_delitos_500m` | Entorno Urbano (Seguridad) | 0.0348 | 2.31 | Representante del eje delictivo con menor colinealidad tras descartar gravedad y robos. |
| **9** | `ruido_db_promedio` | Entorno Urbano (Acústica) | 0.0253 | 1.09 | Externalidad ambiental estadísticamente significativa (prueba H1: $p = 6.96 \times 10^{-4}$). |
| **10** | `apto_mascotas` | Restricción *(Obligatoria)* | 0.0110 | 1.01 | Criterio crítico de elegibilidad corporativa depurado mediante NLP anti-negaciones. |

---

## 🔬 Variables Candidatas Descartadas por Colinealidad (VIF > 5.0)

Durante la eliminación secuencial por multicolinealidad, se descartaron las siguientes variables que inflaban artificialmente la varianza del modelo:

1. `indice_gravedad_delitos_500m` ($\text{VIF} = 148.14$) — Fuertemente colineal con `densidad_delitos_500m`.
2. `densidad_robos_500m` ($\text{VIF} = 370.27$) — Redundante respecto a `densidad_delitos_500m`.
3. `score_amenities_soltero` ($\text{VIF} = 47.04$) y `score_amenities_familia` ($\text{VIF} = 22.48$) — Sub-índices capturados por `score_amenities`.
4. `dormitorios` ($\text{VIF} = 6.67$) — Colineal con `ambientes` y `m2_totales`.
5. `m2_cubiertos` ($\text{VIF} = 8.02$) — Descartado a favor de `m2_totales`, que demostró mayor correlación con el target.
