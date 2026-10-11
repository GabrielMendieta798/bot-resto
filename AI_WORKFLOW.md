# AI_WORKFLOW.md — Cómo se trabaja

Define qué herramienta conviene usar para cada task y cómo elegir el nivel de
razonamiento. Los procedimientos de propose, apply, verify, handoff, archive y
cierre de sesión están en `PLAYBOOK.md`.

---

## 1. Herramientas y roles

El proyecto utiliza:

- OpenCode
- Codex
- Claude Code

OpenCode cumple el rol de agente de ejecución para tareas simples,
mecánicas o cuyo diseño ya está definido.

Codex y Claude Code pueden cumplir el rol de **Reasoning Agent**.

Cada desarrollador puede elegir cuál utilizar como Reasoning Agent
según su preferencia, disponibilidad o contexto de trabajo.

Cuando este documento diga `Reasoning Agent`, significa:

- Codex; o
- Claude Code.

La elección entre ambos no modifica el workflow ni representa una
decisión arquitectónica del proyecto.

Las specs, tasks, reglas y criterios de verificación deben ser
independientes del agente utilizado.

---

## 2. Matriz OpenCode vs Reasoning Agent

| Dimensión | OpenCode | Reasoning Agent |
|---|---|---|
| Herramientas | OpenCode | Codex o Claude Code |
| Mejor para | Tareas acotadas, repetitivas y con patrón existente | Problemas que requieren análisis o decisiones |
| Ejemplos | CRUD existente, wiring, imports, config, docs, tests simples, renames | Arquitectura, concurrencia, seguridad, state machines, migraciones delicadas, debugging complejo |
| Contexto necesario | Corto a medio | Medio a largo |
| Costo esperado | Bajo | Mayor |
| Dónde brilla | Ejecutar una solución ya definida | Diseñar, analizar o descubrir la solución |
| Señal de escape | Se traba varias veces en el mismo problema | Puede sobre-diseñar tareas triviales |

**El criterio de ruteo es la complejidad del APPLY, no la herramienta preferida por el desarrollador.**

La cantidad de líneas de código no determina la complejidad.

Una modificación de pocas líneas puede requerir Reasoning Agent si implica
una decisión importante.

Una modificación grande puede ir a OpenCode si consiste en aplicar
mecánicamente un patrón ya aprobado.


## 3. Niveles de razonamiento

El nivel de razonamiento se decide por task.

No se define un nivel alto para todo un change solamente porque el
change tenga partes complejas.

Los niveles representan la cantidad de análisis que debería dedicarse
al problema.

### LOW

Usar para:

- entender código existente;
- consultas sobre el repositorio;
- revisión de diffs pequeños;
- implementación de una task bien especificada;
- debugging sencillo;
- tests con comportamiento claro;
- modificaciones locales;
- revisión de trabajo generado por OpenCode.

LOW es el punto de partida cuando una tarea necesita Reasoning Agent
pero no presenta una complejidad importante.

---

### MEDIUM

Usar para:

- diseño de features;
- cambios entre varias capas;
- migraciones no triviales;
- máquinas de estado;
- debugging cuya causa no está clara;
- decisiones de diseño;
- revisión de changes importantes;
- diseño o revisión de `design.md`;
- problemas con varias soluciones razonables.

MEDIUM es el nivel normal para problemas de ingeniería no triviales.

---

### HIGH

Reservar para:

- concurrencia;
- race conditions;
- locking;
- idempotencia crítica;
- seguridad;
- autenticación y autorización;
- integridad crítica de datos;
- migraciones riesgosas;
- bugs difíciles después de varios intentos;
- decisiones arquitectónicas de alto impacto;
- revisión profunda de changes sensibles.

HIGH no debe utilizarse como nivel por defecto.

---

### XHIGH / máximo disponible

Solo utilizar cuando:

- HIGH no haya sido suficiente;
- el problema sea excepcionalmente complejo;
- exista una razón concreta para gastar más razonamiento.

No utilizar durante el desarrollo normal.


## 4. Escalamiento

Usar siempre el nivel mínimo que permita resolver correctamente la tarea.

Flujo recomendado:

OpenCode
    ↓
¿la tarea dejó de ser mecánica?
    ↓
Reasoning Agent — LOW
    ↓
¿requiere análisis real o varias decisiones?
    ↓
MEDIUM
    ↓
¿es crítica, sensible o sigue sin resolverse?
    ↓
HIGH

No mantener HIGH para las siguientes tasks si ya no lo necesitan.

El nivel se decide por task, no por sesión completa ni por change completo.


### Regla de routing

```text
¿La solución ya está claramente definida?
        │
        ├── sí
        │    ↓
        │ OpenCode
        │
        └── no
             ↓
        Reasoning Agent
```
