# Tasks: Consolidación Monorepo y Desacoplamiento de Despliegue

## 1. Infraestructura de Pruebas y Aislamiento

- [x] 1.1 Configurar arnés de testing en la raíz (`pytest.ini`) especificando rutas de resolución para `dashboard/` y verificar resolución con `pytest --collect-only`.
- [x] 1.2 Actualizar fixtures en `conftest.py` para asegurar que las rutas a los datos mock y componentes apunten de forma agnóstica a `dashboard/data/fallback_data.csv`.

## 2. Modularización y Traslado del Dashboard

- [x] 2.1 Crear el subdirectorio `dashboard/` y trasladar los componentes de la interfaz (`app.py`, `src/`, `data/`, `.streamlit/`, `requirements.txt`).
- [x] 2.2 Reubicar la suite de tests a `dashboard/tests/` y verificar que las importaciones relativas `from src...` operen limpiamente.
- [x] 2.3 Ejecutar la suite de tests del dashboard reubicado y verificar código de salida 0 con `pytest dashboard/tests/`.

## 3. Integración en Main y Estructuración MLOps

- [ ] 3.1 Integrar la estructura modular de `dashboard/` en la rama `main` sin alterar los módulos de inferencia (`producto2/` y `actor/`).
- [ ] 3.2 Formalizar la frontera de MLOps (`producto2/train_models.py`, `producto2/inference.py`, `actor/`) documentando el contrato de exportación de modelos.
- [ ] 3.3 Verificar que el entrypoint `dashboard/app.py` no requiera librerías de ML (`xgboost`, `scikit-learn`) mediante verificación estática de imports.

## 4. Higiene de Repositorio y Configuración de Despliegue

- [ ] 4.1 Actualizar `.gitignore` en la raíz de `main` para excluir `apuntes/` (~500 MB) y cachés de matplotlib, verificando con `git status --ignored`.
- [ ] 4.2 Crear un `README.md` maestro en la raíz con arquitectura Monorepo, flujo de reentrenamiento y guía de configuración de Streamlit Cloud (*Main file path*: `dashboard/app.py`).
- [ ] 4.3 Generar `requirements.txt` mínimo en la raíz referenciando o conteniendo las dependencias del dashboard para compatibilidad con plataformas de despliegue.

## 5. Verificación de Sistema (SVC) y Evidencia

- [ ] 5.1 Ejecutar el comando único de verificación (SVC): `pytest dashboard/tests/ -v` asegurando 11/11 tests exitosos (Exit Code 0).
- [ ] 5.2 Levantar el servicio en background con `streamlit run dashboard/app.py` y verificar respuesta HTTP 200 en `http://localhost:8501`.
- [ ] 5.3 Generar artefacto de evidencia `evidence.md` certificando el cumplimiento de todos los escenarios de `specs/monorepo-workspace/spec.md`.
