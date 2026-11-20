# Design: Sincronización Integral de Documentación y Arquitectura Viva

## Context
Tras la consolidación del monorepo (`actors/` para Apify serverless, `src/` para el núcleo analítico/ML, `notebooks/` para experimentación y `dashboard/` para Streamlit), la documentación maestra ha quedado desfasada. Existen referencias a directorios eliminados (`producto1/`, `producto2/`, `actor/`, `trainer/`), conteos de tests obsoletos y discrepancias en la guía de despliegue n8n.

## Goals / Non-Goals

**Goals:**
- Unificar `README.md` como el portal maestro de arquitectura viva con índice interactivo y navegación fluida.
- Alinear `docs/README_DEPLOYMENT_N8N.md` con los 31 nodos de producción del lienzo unificado y los comandos de Apify CLI en `actors/`.
- Actualizar `docs/architecture/00` a `04` con rutas `src/` y el contexto real del arnés de pruebas (70 tests).
- Erradicar la duplicación de las preguntas de negocio Q1-Q5 entre `docs/business_questions.md` y `docs/feature_selection.md`.
- Sincronizar `openspec/specs/apify-inference-pipeline/spec.md` reflejando `actors/inference/`.

**Non-Goals:**
- No modificar código ejecutable en `src/`, `actors/`, `dashboard/` ni `notebooks/`.
- No alterar la suite de pruebas unitarias/integración en `tests/`.

## Decisions

### 1. Índice Maestro Jerárquico en `README.md`
- **Decisión:** Estructurar el `README.md` con un índice temático claro al inicio (Arquitectura, Componentes, Flujos Cloud, Despliegue Streamlit, Ejecución Local y Testing).
- **Alternativa Descartada:** Mantener una lista plana o texto continuo que dificulta la lectura ejecutiva y técnica.

### 2. Delegación Exclusiva de Configuración de Secrets a `docs/README_DASHBOARD_CONFIG.md`
- **Decisión:** En `README.md`, referenciar `docs/README_DASHBOARD_CONFIG.md` como la única fuente de verdad (Single Source of Truth) para la configuración de Google Drive en Streamlit Cloud (`gdrive_folder_id` + `gdrive_api_key`), eliminando bloques TOML en conflicto que sugieran `gdrive_csv_url` o `gdrive_file_id`.
- **Alternativa Descartada:** Duplicar la tabla de variables en ambos archivos, lo cual causó desincronización previa.

### 3. Explicación Didáctica del Umbral $R^2$ en `03_MODELADO`
- **Decisión:** Clarificar en `docs/architecture/03_MODELADO_KMEANS_XGBOOST_Y_SHAP.md` que la versión inicial `v1` (entrenada sobre el dataset base de 964 filas) alcanzó $R^2 = 0.7775$, mientras que la guarda del Model Registry fija $R^2 \ge 0.80$ como criterio de promoción para futuros ciclos anuales con datos acumulados.
- **Alternativa Descartada:** Alterar retroactivamente `registry.json` o dejar la contradicción sin explicar.

### 4. Discriminador Causal en `04_SCORE_DECISION` y Handoff
- **Decisión:** Reemplazar la sección conceptual de "Make/n8n" en `04` por la descripción técnica del handoff productivo real: `actors/inference` procesando publicaciones mensuales, publicando a Google Drive y consumiendo modelos desde Apify Production KV Store o locales.

## Protocolo Grill-Me Exhaustivo (Análisis de Vectores de Falla)

1. **Vector 1: Deriva de rutas relativas en enlaces Markdown**:
   - *Falla:* Enlaces rotos `[link](./ruta)` que apunten a ubicaciones previas a la migración.
   - *Mitigación:* Verificación estática automatizada de todos los links en `docs/` y `README.md` contra el filesystem real.
2. **Vector 2: Confusión de credenciales en n8n**:
   - *Falla:* Usuario intenta ejecutar despliegues con rutas viejas `cd actor` fallando con `Directory not found`.
   - *Mitigación:* Documentar explícitamente `cd actors/inference` y `cd actors/trainer` con ejemplos verificados.
3. **Vector 3: Colapso semántico en la tabla de nodos de n8n**:
   - *Falla:* La documentación menciona un nodo inexistente o con nombre divergente del archivo JSON.
   - *Mitigación:* Cruzar los nombres de nodos directamente contra `workflows/n8n/*.json` (e.g. `CKAN API: Consultar Datasets GCBA`).
4. **Vector 4: Inconsistencia en conteo de tests**:
   - *Falla:* Documentar un número de tests obsoleto (e.g., 11 o 49).
   - *Mitigación:* Citar exactamente la salida canónica de `pytest`: 70 tests colectados (68 passed, 2 skipped).
5. **Vector 5: Duplicación divergente en preguntas de negocio**:
   - *Falla:* `docs/business_questions.md` y `docs/feature_selection.md` presentan redacciones divergentes de Q1-Q5.
   - *Mitigación:* `business_questions.md` es el dueño de las preguntas de negocio; `feature_selection.md` solo contiene la matriz de features, VIF y correlación.
6. **Vector 6: Instrucciones contradictorias de Streamlit Secrets**:
   - *Falla:* El usuario configura `gdrive_csv_url` y rompe la autodetección mensual por carpeta.
   - *Mitigación:* Unificar en torno a la recomendación canónica de `gdrive_folder_id` + `gdrive_api_key`.
7. **Vector 7: Desincronización de Spec en OpenSpec**:
   - *Falla:* `openspec/specs/apify-inference-pipeline/spec.md` mantiene referencias a `actor/`.
   - *Mitigación:* Actualizar el spec con los contratos en `actors/inference/`.
8. **Vector 8: Ruptura de diagramas Mermaid por caracteres especiales**:
   - *Falla:* Sintaxis Mermaid inválida en `README.md` o `00_INDICE`.
   - *Mitigación:* Validar que todos los nodos Mermaid utilicen delimitadores estándar ASCII sin tags HTML.
9. **Vector 9: Omisión de los nuevos notebooks en el índice**:
   - *Falla:* El usuario no sabe dónde está el flujo end-to-end reproducible.
   - *Mitigación:* Sección destacada en `README.md` documentando `notebooks/pipeline_observatorio_caba.ipynb` y `notebooks/observatorio_caba_showcase.ipynb`.
10. **Vector 10: Ambigüedad en la política de retención de Google Drive**:
    - *Falla:* Confusión entre la carpeta de 90 días (`01_mensual_enriquecido`) y el histórico (`04_historico_alquileres_anual`).
    - *Mitigación:* Diagrama explícito de flujo dual de persistencia en `README_DEPLOYMENT_N8N.md` y `README.md`.

## Risks / Trade-offs
- **[Riesgo de sobrecarga visual en README]** → Mitigado utilizando tablas comparativas concisas, bloques de código colapsables y badges semánticos.
