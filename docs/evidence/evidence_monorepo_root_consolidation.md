# Evidencia de Verificación: Consolidación de Raíz del Monorepo en `actors/` y `src/`

**Fecha:** 2026-11-20  
**Cambio OpenSpec:** `consolidate-monorepo-root-src-actors`  
**Estado:** Exitoso (100% de tests aprobados, Exit Code 0)  
**Aislamiento:** Cero pruebas manuales requeridas (Zero Manual Testing Directive).

---

## 1. Topología Final Consolidada de la Raíz

```
CapstoneProject/
├── actors/                      # Contenedores autónomos Apify (Serverless)
│   ├── inference/               # Actor de scoring mensual (ex actor/)
│   └── trainer/                 # Actor de reentrenamiento anual (ex trainer/)
├── dashboard/                   # Aplicación Web Streamlit Cloud (UI interactiva)
├── docs/                        # Documentación centralizada, arquitectura y evidencias
├── notebooks/                   # Notebooks interactivos y showcase ejecutivo
│   ├── observatorio_caba_showcase.ipynb
│   └── pipeline_observatorio_caba.ipynb
├── openspec/                    # Especificaciones formales, diseño y gobernanza
├── scripts/                     # Scripts y utilidades CLI
├── src/                         # Núcleo analítico unificado (src-layout)
│   ├── config/                  # settings.py con BASE_DIR = parents[2]
│   ├── eda/                     # eda_phase2.py y figuras estadísticas
│   ├── etl/                     # etl_pipeline.py y curación geoespacial
│   └── mlops/                   # train_models.py, inference.py, registry.py, artifacts/
├── tests/                       # Suite de pruebas automatizadas deterministas
├── workflows/                   # Flujos de orquestación n8n
├── .gitignore                   # Reglas de exclusión actualizadas
├── pytest.ini                   # pythonpath = src dashboard .
└── requirements.txt             # Dependencias del monorepo
```

---

## 2. Auditoría de Eliminaciones y Limpieza
- **Eliminación de `producto2/`**: Shim legado erradicado. Imports actualizados a `from mlops import inference`.
- **Reubicación de Notebooks**: `pipeline_observatorio_caba.ipynb` relocalizado en `notebooks/`. Cero archivos de código sueltos en la raíz.
- **Ajuste de `BASE_DIR`**: `src/config/settings.py` resuelve rutas absolutas a través de `Path(__file__).resolve().parents[2]`.

---

## 3. Resultado de la Suite Determinista (`pytest`)

Comando ejecutado:
```bash
pytest
```

Salida del arnés de pruebas:
```
============================= test session starts ==============================
platform linux -- Python 3.14.4, pytest-9.2.0, pluggy-1.7.0
rootdir: /home/luka/Documents/CapstoneProject
configfile: pytest.ini
testpaths: dashboard/tests, tests
plugins: anyio-4.16.0, typeguard-4.4.4
collecting ... collected 70 items

dashboard/tests/test_dashboard.py ...................                    [ 27%]
tests/test_apify_actor.py ........                                       [ 38%]
tests/test_end_to_end_notebook.py ............                           [ 55%]
tests/test_etl_and_eda.py .......ss                                      [ 68%]
tests/test_geo_cache.py .                                                [ 70%]
tests/test_inference_scoring.py ..                                       [ 72%]
tests/test_model_registry.py .......                                     [ 82%]
tests/test_n8n_workflows.py ....                                         [ 88%]
tests/test_showcase_notebook.py ..                                       [ 91%]
tests/test_trainer_actor.py ......                                       [100%]

================== 68 passed, 2 skipped, 11 warnings in 4.88s ==================
Exit Code: 0
```

---

## 4. Prueba Hermética del Actor de Inferencia

Comando ejecutado:
```bash
pytest tests/test_apify_actor.py -k test_actor_hermetic_isolation
```

Salida:
```
======================= 1 passed, 7 deselected in 2.03s ========================
Exit Code: 0
```
Comprueba que `actors.inference.src.pipeline` es 100% autónomo y funciona sin dependencias hacia `etl` ni `mlops` en `sys.path`.
