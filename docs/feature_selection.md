# Preguntas de Negocio
## Fase 1: 5 Preguntas de Negocio y Auditoría ETL
- 5 Preguntas de Negocio Clave (Corporate Relocation / RR.HH.)
- Q1: ¿Qué zonas y segmentos de departamentos de CABA ofrecen el mejor equilibrio entre calidad ambiental (<= 65 dBA, menor gravedad delictiva) y conectividad/servicios según el perfil (FAMILIA vs. SOLTERO_EJECUTIVO)?
- Q2: ¿Cuál es el impacto estadísticamente significativo de las externalidades urbanas (ruido diurno, delito, subte, escuelas) sobre el precio/m² y el costo total mensual?
- Q3: ¿Qué proporción de la oferta presenta sobreprecio o subvaluación frente al costo total teórico (alquiler_ars + expensas_ars) explicado por atributos físicos, amenities y entorno?
- Q4: ¿Cómo afectan las inconsistencias de publicación (etiquetas contradictorias sobre mascotas, expensas omitidas y coordenadas fuera de CABA) a la elegibilidad real para relocalización corporativa?
- Q5: ¿Qué subconjunto de máximo 10 variables ortogonales (VIF controlado) concentra mayor poder predictivo e información mutua para predecir costo_total_ars sin redundancia?

| # | Feature Final | Pilar | Score Combinado (RF + MI) | VIF Final |
| ---: | --- | --- | ---: | ---: |
| 1 | `m2_totales` | Físico | 0.9734 | 2.36 |
| 2 | `banos` | Físico | 0.1629 | 1.81 |
| 3 | `score_amenities` | Amenities (obligatoria) | 0.1551 | 1.55 |
| 4 | `ambientes` | Físico | 0.1498 | 1.78 |
| 5 | `cocheras` | Físico | 0.1152 | 1.74 |
| 6 | `distancia_escuela_m` | Entorno · Educación | 0.0586 | 1.07 |
| 7 | `lineas_subte_600m` | Entorno · Transporte | 0.0472 | 2.24 |
| 8 | `densidad_delitos_500m` | Entorno · Seguridad | 0.0348 | 2.31 |
| 9 | `ruido_db_promedio` | Entorno · Acústico | 0.0253 | 1.09 |
| 10 | `apto_mascotas` | Elegibilidad (obligatoria) | 0.0110 | 1.01 |