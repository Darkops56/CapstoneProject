# Isomorfismo Conceptual Políglota de Clean Architecture

Este documento define la correspondencia entre los conceptos universales de Clean Architecture y las estructuras idiomáticas en los principales ecosistemas tecnológicos, asegurando que el agente aplique el patrón de forma natural sin imponer sintaxis extraña.

---

## 1. Matriz de Equivalencias Isomórficas

| Concepto Universal | TypeScript / JS | C# / .NET | Go | Python | Rust |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Entidad Pura** | Objeto inmutable tipado (`type` / `readonly`) | Clase pura o `record` sin atributos ORM | `struct` con métodos receptores puros | `dataclass(frozen=True)` o clase pura | `struct` con métodos `impl` |
| **Puerto de Salida (Interfaz)** | `interface DataRepository` | `interface IDataRepository` | `type DataRepository interface` | `class DataRepository(Protocol)` | `trait DataRepository` |
| **Caso de Uso** | Función pura o clase `Execute(cmd)` | Clase `Handler` o servicio de aplicación | Función o struct `Service` | Función o clase `UseCase` | Función o struct `Handler` |
| **Inyección de Dependencias** | Paso de parámetros en constructor o fábrica | Constructor Injection vía DI Container nativo | Paso explícito de structs/interfaces | Inyección vía constructor o decorador | Paso de referencias o genéricos `T: Trait` |
| **Errores de Dominio** | Tipos de error discriminados o `Result<T, E>` | Excepciones de dominio tipadas o `Result<T>` | `error` con tipos centinela o custom `struct` | Excepciones personalizadas derivadas de `Exception` | `Result<T, DomainError>` con `enum` |

---

## 2. Anti-Patrones de Acoplamiento por Ecosistema

### Errores Frecuentes que el Agente Debe Evitar:
1. **En Entornos Go**: No forzar jerarquías de herencia ni carpetas de 10 niveles. Go utiliza interfaces implícitas; el paquete que consume debe definir la interfaz pequeña (1 o 2 métodos), no el paquete que la implementa.
2. **En Entornos C# / .NET**: No decorar entidades de dominio con atributos de Entity Framework (`[Key]`, `[Table]`, `[ForeignKey]`). El mapeo relacional pertenece exclusivamente a la capa de persistencia en `Infrastructure`.
3. **En Entornos Node / TypeScript**: No importar librerías de enrutamiento (Express, Fastify, NestJS) dentro de los casos de uso. El caso de uso debe operar con objetos de comando planos.
4. **En Entornos Python**: No acoplar lógica de negocio con modelos de Django ORM o SQLModel. Si se usa Clean Architecture, los modelos de dominio deben ser clases de Python puro.
