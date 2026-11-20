# 5 Preguntas de Negocio Clave (Corporate Relocation / RR.HH.)

Este documento establece las directrices analíticas y objetivos cuantitativos del proyecto para resolver el problema de asimetría de información en relocalización corporativa en la Ciudad Autónoma de Buenos Aires (CABA).

---

## 🎯 Formulación de las Preguntas de Negocio

### Q1: Calidad Ambiental vs. Conectividad Urbana
> ¿Qué zonas y segmentos de departamentos de CABA ofrecen el mejor equilibrio entre calidad ambiental ($\le 65\text{ dBA}$, menor gravedad delictiva) y conectividad/servicios según el perfil corporativo (**FAMILIA** vs. **SOLTERO_EJECUTIVO**)?

- **Propósito:** Segmentar la oferta identificando clústeres residenciales óptimos para empleados con hijos (que priorizan bajo ruido, proximidad escolar y seguridad) frente a ejecutivos (que demandan transporte rápido y vida urbana).

---

### Q2: Impacto Estadístico de Externalidades Urbanas
> ¿Cuál es el impacto estadísticamente significativo de las externalidades urbanas (ruido diurno, delito, subte, escuelas) sobre el precio por metro cuadrado ($\text{precio/m}^2$) y el costo total mensual?

- **Propósito:** Cuantificar el efecto de las variables de entorno mediante contrastes de hipótesis formales (Mann-Whitney U, Kruskal-Wallis, Spearman) para verificar si las primas ambientales o de transporte justifican la variación de precios.

---

### Q3: Detección de Sobreprecio y Oportunidades de Ahorro
> ¿Qué proporción de la oferta presenta sobreprecio o subvaluación frente al costo total teórico ($\text{alquiler\_ars} + \text{expensas\_ars}$) explicado por atributos físicos, amenities y entorno?

- **Propósito:** Proveer a Recursos Humanos un modelo predictivo riguroso que estime el Precio Justo Teórico para evitar sobrepagos contractuales y detectar unidades con ahorro significativo ($\ge 10\%$).

---

### Q4: Inconsistencias de Publicación y Restricciones de Elegibilidad
> ¿Cómo afectan las inconsistencias de publicación (etiquetas contradictorias sobre mascotas, expensas omitidas y coordenadas fuera de CABA) a la elegibilidad real para relocalización corporativa?

- **Propósito:** Auditar y sanear las anomalías de los portales inmobiliarios mediante procesamiento de lenguaje natural (NLP) defensivo, anulando falsos positivos en aceptación de mascotas y rescatando expensas omitidas.

---

### Q5: Ortogonalidad y Parquedad Predictiva (VIF Controlado)
> ¿Qué subconjunto de máximo 10 variables ortogonales ($\text{VIF} < 5.0$) concentra mayor poder predictivo e información mutua para predecir $\text{costo\_total\_ars}$ sin redundancia?

- **Propósito:** Garantizar que el modelo de Machine Learning sea interpretable, parsimonioso y estable, eliminando la colinealidad entre métricas físicas y espaciales.
