---
name: test-harness-spec
description: >-
  Diseña la estrategia y pirámide de pruebas automatizadas deterministas (Unit, Integration, E2E) y el SVC.
  Use when defining test suites, implementing automated verification harnesses, writing assertions,
  or establishing regression gates without manual human testing.
---

# Test Harness Engineering Specification

Esta skill norma el diseño, estructuración y ejecución del arnés de pruebas automatizadas deterministas. Impone la **Directiva de Cero Pruebas Manuales** y establece el **System Verification Contract (SVC)** agnóstico al stack.

---

## 1. El System Verification Contract (SVC)

Todo cambio técnico debe contar con un Contrato de Verificación de Sistema compuesto por tres elementos formales:

```
+-----------------------------------------------------------------------------------+
|                        SYSTEM VERIFICATION CONTRACT (SVC)                         |
+-----------------------------------------------------------------------------------+
  1. Boundary Interface  --> Punto de observación (Exit Code CLI, HTTP Status, DOM).
  2. Deterministic Cmd   --> Comando reproducible sin interacción humana.
  3. Assertion Contract  --> Verificación Popperiana: Exit Code 0 en éxito, != 0 en fallo.
```

> **PROHIBICIÓN ESTRICTA**: El agente tiene terminantemente prohibido delegar la verificación en el usuario solicitando confirmaciones manuales. El agente es 100% responsable de verificar sus cambios de forma autónoma con comandos deterministas.

---

## 2. Metodología de Ejecución: Secuencia Verification-First en 5 Fases

Bajo el principio de falsabilidad de Karl Popper, una prueba no es válida porque "pasa"; es válida si es capaz de refutar el sistema cuando este falla. Para erradicar la tautología de mocks adaptados a supuestos del implementador, el arnés impone una secuencia obligatoria en 5 fases:

```
[ FASE 0: STUBS ]        --> Declarar interfaces y tipos. Los stubs DEBEN lanzar
                             excepciones explícitas (NotImplementedError) y NUNCA
                             devolver valores por defecto complacientes.
                                   |
                                   v
[ FASE 1: HARNESS RED ]  --> Ejecutar arnés sobre T=0 y casos de borde.
                             * El arnés DEBE fallar en ejecución (Exit Code != 0).
                             * Asevera la ausencia o rechazo antes de escribir lógica.
                                   |
                                   v
[ FASE 2: CORE DOMAIN ]  --> Implementar lógica de negocio mínima y eventos canónicos.
                                   |
                                   v
[ FASE 3: CONSUMERS ]    --> Implementar frontera, renderizado y discriminador causal.
                                   |
                                   v
[ FASE 4: SVC GREEN ]    --> Re-ejecutar arnés completo. EXIT CODE 0 determinista.
```

---

## 3. Directiva Negative-Path First (Anti Happy-Path Bias)

Los modelos de lenguaje tienden a probar únicamente el camino feliz. Esta skill impone:
1. Diseñar **primero** los escenarios de error: entradas inválidas, desbordamiento, fallas de red simuladas y violaciones de invariantes de dominio.
2. Formular cada escenario bajo sintaxis Gherkin cuantitativa:
   - `GIVEN` un estado del sistema y una entrada corrupta/límite.
   - `WHEN` se ejecuta la operación.
   - `THEN` debe responder con un código de error específico y un estado limpio sin efectos colaterales.

---

## 4. Gobernanza de Pruebas por Tiers

* **Tier S (Ligero)**: 1 prueba unitaria o script determinista de regresión. Cero infraestructura pesada.
* **Tier M (Medio)**: Pruebas unitarias de casos de borde + 1 prueba de integración del endpoint/componente con dobles in-memory.
* **Tier L (Arquitectónico)**: Suite completa de integración + pruebas de resiliencia ante cortes simulados + reporte formal de cobertura.

---

## 5. Referencias Técnicas

* [Ciclo de Arnés Desacoplado y Falsabilidad](./references/clean-harness-lifecycle.md): Protocolo de stubs con NotImplementedError, orden de fases y desacoplamiento de mocks.
* [System Verification Contract & Boundaries](./references/system_verification_contract.md): Especificación de interfaces de frontera (CLI, HTTP, IPC, DOM) y comandos deterministas.
* [Pirámide de Pruebas y Dobles In-Memory](./references/test_pyramid_and_doubles.md): Fakes in-memory puros vs mocks y cuarentena de dependencias de testing.
