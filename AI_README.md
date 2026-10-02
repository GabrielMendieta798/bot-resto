# AI_README.md — Cómo se desarrolla este proyecto con agentes

Onboarding del ecosistema de desarrollo asistido. Si sos un humano nuevo o un agente arrancando frío, esto te explica cómo está armado el andamiaje y por qué.

---

## 1. Jerarquía de gobierno

Cinco capas, de mayor a menor autoridad. Cada una tiene un trabajo distinto y no se pisan.

| # | Capa | Archivo | Qué contiene | Quién la cambia |
|---|---|---|---|---|
| 1 | **Constitución** | `.instructions.md` | Reglas normativas obligatorias y verificables. Invariantes de negocio y técnicos. | Solo el humano, explícitamente |
| 2 | **Contrato del change** | `openspec/changes/<change>/` | Qué se construye ahora, con escenarios verificables. | El agente propone, el humano aprueba |
| 3 | **Contexto operativo** | `AGENTS.md` · `CLAUDE.md` | Stack, comandos, estructura, convenciones. | Se actualiza cuando cambia el repo |
| 4 | **Procedimientos** | `.opencode/skills/` · `.claude/skills/` | Secuencias repetibles con criterio de corte. | El humano |
| 5 | **Especialistas** | `.opencode/agents/` · `.claude/agents/` | Subagentes read-only con herramientas restringidas. | El humano |

Regla de desempate: `.instructions.md` §PRI-1. La versión corta también está en `.opencode/HIERARCHY.md`.

**Por qué esta separación:** las reglas duran todo el proyecto, las specs duran un change, el contexto cambia con el repo. Meter todo en un archivo hace que el agente no distinga entre "esto es ley" y "esto es cómo se llama la carpeta".

## 2. SDD con OpenSpec

No se escribe una línea de código sin un change abierto y su spec aprobada por el humano (`SDD-1`).

```
/opsx-propose  →  [REVISIÓN HUMANA]  →  /opsx-apply  →  verificación  →  [@security]  →  /opsx-archive
```

- **propose** genera `proposal.md`, `design.md`, `specs/` y `tasks.md`. Es barato: corré esto en la herramienta que tengas a mano.
- **La revisión humana es el checkpoint que hace que todo esto funcione.** Es donde encontrás que el agente entendió mal el negocio, antes de que escriba 800 líneas. No se delega, no se saltea, no se asume (CP-4 del documento de arquitectura).
- **apply** ejecuta `tasks.md` en orden, con `run-verify` después de cada tarea.
- **archive** mueve el change a histórico y consolida las specs en `openspec/specs/`.

Los prompts listos para copiar y pegar, change por change, están en el **playbook** (Fase C).

## 3. Skills

Procedimientos repetibles. Cada una referencia las secciones de `.instructions.md` que hace cumplir, y todas terminan con el mismo criterio de corte: **si algo falla, frená, explicá archivo y línea, proponé la corrección, y no marques la tarea como completa.**

| Skill | Qué hace | Reglas que hace cumplir |
|---|---|---|
| `run-verify` | ruff + format + mypy + pytest, en ese orden. Corta al primer rojo. | `VER-1` |
| `write-tests` | Tests unit e integración siguiendo los patrones del repo; test en paralelo para las reglas de concurrencia. | `VER-2`, `VER-3` |
| `security-audit` | Checklist de auth, roles, validación, secretos, logs y firma de webhook. | `SEC-*`, `PAN-*`, `WA-3` |
| `add-domain-module` | Módulo de dominio completo: `models` + `repository` + `service` + `schemas` + migración + tests. | `GEN-1`, `DAT-2`, `DAT-6` |
| `add-conv-state` | Suma un estado a la máquina de conversación con sus transiciones, comandos globales y tests. | `CONV-1`, `CONV-3`, `CONV-4` |
| `migrate-safe` | Migración de Alembic con revisión del autogenerate y prueba de `upgrade` + `downgrade`. | `DAT-6`, `VER-4` |
| `update-estado` | Actualiza `ESTADO.md` con el snapshot de cierre de sesión. | `SDD-5` |

> **Duplicación obligatoria:** cada skill existe con contenido idéntico en `.opencode/skills/` y `.claude/skills/`. **Si editás una, espejá la otra.** No hay sincronización automática; es tu responsabilidad.

**No hay skill de tablero.** El documento de arquitectura descartó explícitamente los MCPs de tablero para este alcance.

**Regla para sumar una skill nueva:** solo si el patrón se repite de verdad **y** tiene reglas propias que, sin escribirlas, se rompen. Una skill "por las dudas" es andamiaje muerto: nadie la corre, queda desactualizada, y ensucia el contexto de todas las sesiones.

## 4. Subagentes

Read-only por diseño: informan, no modifican. El que modifica es el agente principal, con la spec delante.

| Subagente | Herramientas | Qué hace | Cuándo |
|---|---|---|---|
| `@security` | Read, Grep, Glob | Corre `security-audit` y reporta **riesgo · archivo:línea · recomendación**. No toca código. | Antes de archivar los changes 00, 02, 03, 05 y 08 |
| `@test-writer` | Read, Grep, Glob, Write (solo `tests/`) — **sin bash** | Propone y escribe tests. No puede ejecutarlos ni tocar `backend/app/`. | Cuando `write-tests` necesita cobertura de un escenario nuevo |
| `@api-explorer` | Read, Grep, Glob, Bash (solo `curl`) | Arma y corre los curls de la verificación funcional contra la app levantada. | Paso 6 de la rutina por change |

## 5. MCPs

Los dos que el documento de arquitectura justificó, y nada más.

| Servidor | Tipo | Rol en el flujo | Dónde pesa |
|---|---|---|---|
| `postgres` | Interno | Inspeccionar el schema real: tablas, constraints, índices, estados persistidos, snapshots. En vez de asumir, mirar. | Changes 01, 02, 03, 05, 08. Clave para verificar `DAT-9` (índice parcial) y los snapshots de `DAT-4` |
| `sequential-thinking` | Externo | Diseñar paso a paso la máquina de estados y el guard de concurrencia, que es donde está la lógica más enredada. | Fase de **propose** de los changes 02 y 03 |
| `github` | Externo | Abrir PRs, leer el diff, consultar el estado de los checks y los comentarios de revisión sin salir de la herramienta. | Paso 8 de la rutina por change, en los 10 changes |

El flujo es por Pull Requests: nada se mergea a `main` directo. `github` entra por eso, no "por las dudas".

## 6. Módulo de IA

**No hay.** El MVP no tiene ningún componente de IA (`IA-1`). No hay LLM, no hay embeddings, no hay base vectorial, y no hay un caso de RAG ni de búsqueda semántica que la justifique hoy.

La interpretación de texto libre está explícitamente fuera de alcance y entra en fase 2. Hasta entonces, la navegación es por botones y listas (`WA-6`, `IA-3`).

La regla de oro ya está escrita para cuando entre (`IA-2`): **el modelo interpreta y propone; nunca decide ni persiste.** El código valida, deriva y persiste. Toda salida del LLM pasa por validación de esquema y por las reglas de dominio antes de tocar la DB.

Ojo con la confusión de nombres: la IA **de este repo como producto** no existe. La IA **como herramienta de desarrollo** (OpenCode, Claude Code, este andamiaje entero) sí, y es de lo que trata este documento.
