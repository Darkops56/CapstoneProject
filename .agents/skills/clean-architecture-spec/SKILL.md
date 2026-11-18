---
name: clean-architecture-spec
description: >-
  Define fronteras arquitectónicas estrictas (Domain, Application, Infrastructure) agnósticas al stack.
  Use when designing software components, structuring code modules, isolating business logic,
  or establishing dependency inversion boundaries.
---

# Clean Architecture Specification

Esta skill establece las directivas arquitectónicas para desacoplar las reglas de negocio puras de frameworks, bases de datos, redes o interfaces de usuario, independientemente del lenguaje de programación.

---

## 1. La Regla de Oro de Dependencias (Dependency Rule)

> **"Las dependencias del código fuente siempre deben apuntar únicamente hacia adentro, hacia las políticas de más alto nivel (el Dominio)."**

```
+-------------------------------------------------------------+
|                      INFRASTRUCTURE                         |
|   (Bases de datos, frameworks web, CLI, clientes HTTP)      |
|                                                             |
|       +---------------------------------------------+       |
|       |                 APPLICATION                 |       |
|       |       (Casos de uso, orquestación, puertos) |       |
|       |                                             |       |
|       |       +-----------------------------+       |       |
|       |       |           DOMAIN            |       |       |
|       |       |   (Entidades, reglas puras) |       |       |
|       +-------+-----------------------------+-------+       |
+-------------------------------------------------------------+
```

1. **Capa Domain (Núcleo)**:
   - Contiene la lógica y modelos de negocio invariantes.
   - **Restricción**: 0 dependencias externas. Prohibido importar librerías de infraestructura, frameworks web, ORMs o drivers.
2. **Capa Application (Orquestación)**:
   - Define los casos de uso del sistema.
   - Declara interfaces/puertos de entrada (*Inbound Ports*) y de salida (*Outbound Ports*).
   - Depende exclusivamente del Dominio.
3. **Capa Infrastructure (Adaptadores)**:
   - Implementa los puertos de salida (ej. repositorios con SQL, clientes de API externa).
   - Contiene adaptadores de entrada (ej. controladores HTTP, comandos CLI).

---

## 2. Gobernanza Proporcional Anti Over-Engineering (Tiers)

Para prevenir la trampa de la sobre-ingeniería en proyectos pequeños, aplica Clean Architecture según el Tier de Complejidad:

| Tier | Regla Arquitectónica | Prohibiciones Estrictas |
| :--- | :--- | :--- |
| **Tier S (Ligero)** | **Estricto YAGNI**. Funciones puras modulares en 1 o 2 archivos. | Prohibido crear carpetas separadas de DTOs, mappers o repositorios intermediarios. |
| **Tier M (Medio)** | Separación lógica entre punto de entrada, lógica de negocio y adaptadores. | Prohibido usar más de 1 capa de DTO si la estructura de datos es idéntica a la entidad. |
| **Tier L (Arquitectónico)**| Inversión estricta de dependencias con puertos explícitos y aislamiento total de I/O. | Prohibido cualquier acoplamiento directo entre capas sin interfaz/puerto mediador. |

---

## 3. Checklist de Auditoría de Código y Diseño

Antes de aprobar una estructura de módulos o código generado, audita:
- [ ] ¿El modelo de dominio contiene imports de base de datos o librerías HTTP? *(Si sí $\rightarrow$ RECHAZAR).*
- [ ] ¿Las funciones de negocio reciben estructuras simples e inmutables? *(Si no $\rightarrow$ REFACTORIZAR).*
- [ ] ¿Los efectos secundarios (I/O, persistencia, red) están confinados a adaptadores de infraestructura? *(Si no $\rightarrow$ AISLAR).*
- [ ] ¿La abstracción cumple el "Impuesto a la Complejidad" (justifica qué falla hoy si no se usa)?

---

## 4. Referencias y Modelos Detallados

Para inspeccionar diagramas de interacción y matrices de equivalencia políglota, consulta:
* [Límites de Capas y Puertos Mermaid](./references/boundaries_and_ports.md): Modelos visuales de Inbound vs Outbound Ports y ciclo de inversión.
* [Isomorfismo Conceptual Políglota](./references/polyglot_isomorphism.md): Equivalencias en TypeScript, C#, Go, Python y Rust.
