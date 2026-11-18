---
name: resilience-threat-spec
description: >-
  Modela amenazas de seguridad STRIDE-A y patrones de tolerancia a fallos (Circuit Breaker, Idempotencia).
  Use when designing APIs, evaluating security risks, architecting distributed systems,
  or resolving the 14 Grill-Me failure vectors before code approval.
---

# Resilience & Threat Modeling Specification

Esta skill norma la evaluación adversaria de seguridad y resiliencia en el diseño de software. Gobierna la aplicación de la taxonomía **STRIDE-A** (*STRIDE + Abuse Cases*) y el **Protocolo Grill-Me** de 14 vectores de falla.

---

## 1. El Protocolo Grill-Me: 14 Vectores de Falla Crítica

En todo cambio Tier M o L, el diseño técnico debe someterse activamente a la evaluación de los 14 vectores de falla antes de iniciar la implementación:

| # | Vector de Falla | Pregunta de Estrés Arquitectónico |
| :- | :--- | :--- |
| **1** | **Concurrencia / Race Conditions** | ¿Qué sucede si 100 hilos o peticiones modifican el mismo recurso en paralelo? |
| **2** | **Agotamiento de Recursos** | ¿El proceso acumula memoria sin liberar o agota descriptores de archivos/sockets? |
| **3** | **Caída de Dependencias Externas**| Si la base de datos o servicio externo no responde, ¿se degrada elegantemente o explota? |
| **4** | **Partición de Red y Timeouts** | ¿Están definidos límites de tiempo estrictos en cada conexión de I/O? |
| **5** | **Pérdida de Idempotencia** | Si una petición HTTP/evento se procesa dos veces, ¿se duplica el efecto de negocio? |
| **6** | **Inyección y Datos Maliciosos** | ¿Se validan y sanitizan todos los datos en la frontera antes de pasar al dominio? |
| **7** | **Escalamiento de Privilegios** | ¿Un usuario autenticado puede acceder o modificar datos de otro inquilino (*tenant*)? |
| **8** | **Tormenta de Reintentos** | ¿Los reintentos aplican Exponential Backoff con Jitter aleatorio para no colapsar el destino? |
| **9** | **Fuga de Información en Logs** | ¿Se imprimen credenciales, tokens o datos personales sensibles en logs o trazas de error? |
| **10**| **Estados Inconsistentes** | Si la aplicación muere abruptamente a la mitad de una operación, ¿queda el estado corrupto? |
| **11**| **Envenenamiento de Colas** | ¿Existe mecanismo de Dead Letter Queue para mensajes con formato inválido? |
| **12**| **Falla en Cascada** | ¿El colapso de un subsistema arrastra al resto del sistema por falta de aislamiento? |
| **13**| **Repudio y Falta de Auditoría** | ¿Las operaciones críticas de negocio emiten eventos de auditoría inmutables? |
| **14**| **Ataques de Denegación de Servicio**| ¿Existen límites de tamaño de payload y rate limiting para prevenir saturación? |

---

## 2. Gobernanza por Tiers de Complejidad

* **Tier S (Ligero)**: 0 circuit breakers o colas complejas. Manejo de errores estándar con fail-fast y mensajes limpios.
* **Tier M (Medio)**: Timeouts explícitos en I/O + Idempotencia en escrituras + Validación de frontera.
* **Tier L (Arquitectónico)**: Resolución formal de los 14 vectores Grill-Me en `design.md` + Circuit Breaker + Matriz STRIDE-A.

---

## 3. Referencias Especializadas

* [Taxonomía STRIDE-A y Catálogo de Mitigaciones](./references/stride_a_taxonomy.md): Matriz de amenazas de seguridad y contramedidas estándar.
* [Patrones de Tolerancia a Fallos](./references/fault_tolerance_patterns.md): Modelos de máquinas de estado para Circuit Breaker, Exponential Backoff con Jitter e Idempotency Keys.
