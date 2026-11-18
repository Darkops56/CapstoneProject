---
name: ux-interaction-spec
description: >-
  Modela los 5 estados obligatorios de componentes interactivos, accesibilidad WCAG 2.2 y verificación con browser_subagent.
  Use when designing frontend UI, building interactive components, validating user experience states,
  or conducting automated browser testing without manual verification.
---

# UX Interaction & Accessibility Specification

Esta skill norma la arquitectura de interfaces de usuario interactivas, la máquina de estados de componentes y las directivas de accesibilidad WCAG 2.2. Establece el protocolo de verificación autónoma mediante `browser_subagent`.

---

## 1. La Máquina de 5 Estados Obligatorios de Brad Frost

Todo componente de interfaz que cargue, transmita o procese datos debe contemplar explícitamente cinco estados de interacción:

```
                  +--------------------------------+
                  |         1. ESTADO IDLE         |
                  |     (Reposo / Inicial / Listo) |
                  +---------------+----------------+
                                  |
                           (Disparo Acción)
                                  v
                  +--------------------------------+
                  |       2. ESTADO LOADING        |
                  |  (Spinners, skeletons, disabled)|
                  +-------+---------------+--------+
                          |               |
               (Error / Fallo)       (Éxito / Datos)
                          v               v
            +-------------------+   +--------------------+
            |  3. ESTADO ERROR  |   | ¿Hay registros?    |
            | (Mensaje + Reintento) |   +---+------------+---+
            +-------------------+       |                |
                                    (Colección = 0)  (Colección > 0)
                                        v                v
                             +-------------------+   +--------------------+
                             |  4. ESTADO EMPTY  |   | 5. ESTADO SUCCESS  |
                             | (Empty State + CTA)|  | (Datos Renderizados)
                             +-------------------+   +--------------------+
```

> **Regla de Rechazo**: Si un componente se queda congelado sin feedback ante una carga lenta o muestra una pantalla blanca cuando no hay datos, la interfaz es rechazada.

---

## 2. Invariante de Cero-Interacción en T=0 (Taxonomía Dual)

Para erradicar efectos secundarios prematuros en el ciclo de vida, todo componente interactivo o cliente debe respetar la Invariante de Reposo Inicial en $T=0$:

* **Componentes Input-Driven / Transaccionales** (Formularios, Modales, Búsquedas):
  - *Invariante de Red*: Cero llamadas de red o conexiones automáticas.
  - *Invariante de Error*: Cero contenedores de alerta o mensajes de error activos o visibles.
* **Componentes Read-Driven / Bootstrap** (Vistas principales, Dashboards, Widgets):
  - *Invariante de Carga*: Permite consulta de lectura inicial (Query) transicionando de inmediato a `LOADING`.
  - *Invariante de Mutación*: Prohibición estricta de mutaciones transaccionales (`POST/PUT/DELETE`) y estados de error prematuros.
  - *Cancelación Determinista*: Obligatoriedad de anular suscripciones o abortar peticiones (`AbortController`) ante desmontaje temprano.

---

## 3. Contrato de Verificación con `browser_subagent`

Para certificar la funcionalidad UI sin pedir pruebas manuales al usuario:
1. **Identificadores Únicos Deterministas**: Todo elemento interactivo (botones, inputs, paneles) debe portar un identificador semántico explícito (`id` o `data-testid`).
2. **Ciclo de Verificación**:
   - Iniciar subagente de navegador (`browser_subagent`) apuntando a la URL local.
   - Interactuar con el elemento (click, tipiado).
   - Validar la transición visible al estado `LOADING` y posteriormente al estado final (`SUCCESS` o `ERROR`).
   - Capturar logs de consola para certificar cero excepciones no controladas.
   - Generar video o snapshot de evidencia.

---

## 4. Principios Clave WCAG 2.2 (POUR)

* **Perceivable (Perceptible)**: Contraste de color mínimo 4.5:1 para texto normal; soporte visual para personas con daltonismo (no usar color como único indicador).
* **Operable (Operable)**: Navegación completa por teclado (Tab, Enter, Escape, flechas); foco visualmente evidente (`outline` visible).
* **Understandable (Comprensible)**: Mensajes de error claros que indiquen qué falló y cómo corregirlo.
* **Robust (Robusto)**: Etiquetas ARIA semánticas (`role`, `aria-expanded`, `aria-busy`, `aria-live="polite"`).

---

## 5. Referencias y Guías Detalladas

* [Invariantes de Reposo en T=0 y Ciclo de Vida](./references/lifecycle-t0-invariants.md): Taxonomía dual de componentes, abort signals y escenarios de prueba.
* [Ciclo de Vida de los 5 Estados](./references/five_states_lifecycle.md): Especificación detallada de comportamiento, transiciones y micro-animaciones.
* [Auditoría de Accesibilidad WCAG 2.2](./references/wcag_accessibility_audit.md): Matriz de verificación POUR y selectores semánticos para el DOM.
