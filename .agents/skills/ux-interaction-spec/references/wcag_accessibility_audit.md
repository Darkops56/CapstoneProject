# Auditoría de Accesibilidad WCAG 2.2 y Verificación Semántica en DOM

Este documento provee la matriz de comprobación de los cuatro principios POUR de accesibilidad web, estructurada para ser evaluada de forma determinista por agentes de IA y subagentes de navegador (`browser_subagent`).

---

## 1. Matriz de Principios POUR y Criterios Comprobables

| Principio | Criterio de Éxito | Comprobación Automatizada en el DOM |
| :--- | :--- | :--- |
| **P - Perceivable** | Contraste de Color (1.4.3) | Ratio mínimo de 4.5:1 para texto normal y 3:1 para texto grande/componentes UI. |
| **P - Perceivable** | Texto Alternativo (1.1.1) | Todo elemento `<img>` o ícono informativo debe portar atributo `alt` no vacío o `aria-label`. |
| **O - Operable** | Acceso por Teclado (2.1.1) | Todos los controles interactivos deben ser alcanzables y accionables vía tecla Tab y Enter/Espacio. |
| **O - Operable** | Foco Visible (2.4.7) | Ningún elemento interactivo debe tener `outline: none` sin proveer un reemplazo visual evidente de foco. |
| **U - Understandable**| Identificación de Errores (3.3.1)| Todo input inválido debe asociarse a su mensaje de error mediante `aria-describedby="error-id"`. |
| **U - Understandable**| Etiquetas Claras (3.3.2) | Todo campo de formulario debe tener un `<label for="id">` asociado explícitamente. |
| **R - Robust** | Roles Semánticos (4.1.2) | Uso de elementos HTML5 nativos (`<button>`, `<dialog>`, `<nav>`) o roles ARIA equivalentes con sus estados (`aria-expanded`). |

---

## 2. Contrato de Selectores Semánticos para el DOM

Para que el `browser_subagent` pueda interactuar sin fragilidad:

```
Prioridad de Localización de Elementos:
  1. data-testid="submit-transaction-btn"  (Identificador explícito e inmune a cambios de diseño)
  2. role="button" + nombre accesible      (ej.getByRole('button', { name: 'Guardar' }))
  3. id="unique-element-id"                (Identificador único de documento)

Anti-Patrón Prohibido:
  ❌ NUNCA interactuar con selectores frágiles como:
     "div.flex > div:nth-child(3) > span.text-blue-500"
     Cualquier cambio de estilo rompe la prueba silenciosamente.
```

---

## 3. Protocolo de Auditoría con `browser_subagent`

1. **Paso 1 (Navegación)**: Iniciar navegador headless en la ruta local correspondiente.
2. **Paso 2 (Inspección de Consola)**: Monitorear el stream de logs de consola de JavaScript. Si se detecta cualquier `TypeError`, `Uncaught Exception` o advertencia crítica de accesibilidad, la prueba falla de inmediato.
3. **Paso 3 (Aserciones de Estados)**:
   - Disparar la interacción.
   - Verificar la presencia de `[aria-busy="true"]` durante la carga.
   - Verificar la aparición del estado final con su rol semántico correspondiente (`role="alert"` en error, o contenedor de datos en éxito).
