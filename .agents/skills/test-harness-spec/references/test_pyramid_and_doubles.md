# Pirámide de Pruebas Deterministas y Dobles In-Memory

Este documento establece la distribución de tipos de pruebas y la política de aislamiento mediante dobles de prueba sin dependencias de librerías externas.

---

## 1. La Pirámide de Pruebas Deterministas

```
              / \
             /   \
            / E2E \           <- 10% (Flujos críticos punta a punta, máxima lentitud)
           /-------\
          /  INTEG  \         <- 30% (Fronteras de I/O con adaptadores in-memory)
         /-----------\
        /    UNIT     \       <- 60% (Lógica de dominio pura, ejecución instantánea)
       /---------------\
```

1. **Pruebas Unitarias (60%)**:
   - Prueban funciones puras, entidades y reglas invariantes del dominio.
   - **Velocidad**: Deben ejecutarse en milisegundos. Cero operaciones de red, disco o procesos externos.
2. **Pruebas de Integración (30%)**:
   - Validan que los casos de uso orquesten correctamente los adaptadores.
   - Utilizan implementaciones en memoria (*In-Memory Fakes*) para bases de datos o clientes HTTP.
3. **Pruebas End-to-End / Sistema (10%)**:
   - Validan el arnés completo desde la frontera externa (CLI o subagente web) hasta la salida del sistema.

---

## 2. Dobles de Prueba: Fakes In-Memory vs Mocks de Librería

### La Regla de Oro:
> **"Prioriza siempre Fakes In-Memory puros implementados a mano por sobre librerías complejas de Mocking dinámico."**

```
+------------------+-------------------------------------------------------------+
| Tipo de Doble    | Comportamiento y Uso Recomendado                            |
+------------------+-------------------------------------------------------------+
| Dummy            | Objetos pasados solo para rellenar parámetros obligatorios. |
| Stub             | Respuestas pre-enlatadas con valores fijos para una prueba. |
| Spy              | Registra si un método fue llamado y con qué argumentos.     |
| Fake In-Memory   | Implementación funcional simplificada (ej. Map en memoria). |
+------------------+-------------------------------------------------------------+
```

### Por qué el Agente debe evitar Mocks Dinámicos Pesados:
1. **Fragilidad ante Refactorización**: Los mocks basados en reflection o proxies dinámicos se acoplan a nombres internos de métodos. Si un método cambia de firma, los tests fallan aunque la lógica de negocio siga intacta.
2. **Cuarentena de Dependencias**: El uso de librerías externas de mocking introduce paquetes de terceros no autorizados. Un Fake in-memory escrito con estructuras nativas del lenguaje es 100% portable y no requiere dependencias.
3. **Fidelidad de Estado**: Un Fake in-memory (ej. un repositorio respaldado por una tabla hash o diccionario en memoria) reproduce el comportamiento real de inserción, consulta y eliminación con fidelidad superior a un mock estático.
