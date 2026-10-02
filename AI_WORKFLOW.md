# AI_WORKFLOW.md — Cómo se trabaja

Operativa concreta: qué herramienta usás para qué, cómo se rutea cada change, cómo se pasa trabajo de una a la otra y cuál es la rutina que se repite change por change.

---

## 1. Matriz OpenCode vs Claude Code

| Dimensión | OpenCode | Claude Code |
|---|---|---|
| Mejor para | Tareas acotadas, patrones ya establecidos en el repo, CRUD, config, wiring | Lógica enredada, concurrencia, máquinas de estado, seguridad, refactors que cruzan capas |
| Contexto que sostiene | Corto a medio | Largo, con varios archivos en juego a la vez |
| Costo por tarea | Bajo | Alto |
| Dónde brilla | Repetir algo que ya existe | Diseñar algo que todavía no existe |
| Dónde falla | Se traba en bucle cuando el problema es de diseño, no de tipeo | Sobre-diseña tareas triviales |

**El criterio de ruteo es la complejidad del APPLY, no la del propose.** Proponer una spec es barato en cualquiera de las dos: escribir texto estructurado lo hace bien cualquier modelo. Lo que cuesta es implementar el guard de carrera. Por eso un change puede proponerse en OpenCode y aplicarse en Claude Code sin contradicción.

**Regla del PDF:** Claude Code si complejidad **alta** o criticidad **sensible**. OpenCode si baja o media.

## 2. Ruteo por change

| Change | Alcance | Compl. | Critic. | Apply en | Audita |
|---|---|---|---|---|---|
| `00-walking-skeleton` | Webhook: firma + idempotencia + responder por Cloud API + INSERT mínimo | alta | sensible | **Claude Code** | `@security` |
| `01-cimientos-datos` | FastAPI + PG + SQLAlchemy sync + Alembic + repos base + MenuItem | media | normal | OpenCode | — |
| `02-pedidos-core` | Customer, Order, OrderItem, snapshot, máquina de estado + guard de carrera | alta | sensible | **Claude Code** | `@security` |
| `03-conversacion` | Conversation, máquina de estados, lock FOR UPDATE, comandos globales, timeouts | alta | sensible | **Claude Code** | `@security` |
| `04-flujo-pedido-wa` | Adapter WhatsApp (intención→PyWa), guión de pedido, `messages.yaml` | alta | normal | **Claude Code** | — |
| `05-reservas` | Intake + validación, máquina de reserva, escalada, template de confirmación | media | sensible | **Claude Code** | `@security` |
| `06-notificacion-staff` | StaffNotifier + eventos de dominio + adapter que persiste la notificación (sin canal externo) | media | normal | OpenCode | — |
| `07-bordes` | Handoff/des-handoff, fuera de horario, item agotado, zona fuera, carrito vacío | media | normal | OpenCode | — |
| `08-panel` | Login con hash, listar entrantes, cambiar estado, confirmar/rechazar, toggle, auditoría, y el aviso al staff (polling HTMX + sonido + notificación del navegador) | media | sensible | **Claude Code** | `@security` |
| `09-hardening` | Tests de integración, Docker, CI, logs estructurados, backups | media | normal | OpenCode | — |

**El orden no se altera** (`SDD-6`). El walking skeleton va primero a propósito: lo más incierto es la frontera con Meta, y se ataca en el change 00, no a la mitad del proyecto.

## 3. Protocolo de handoff

### Regla de escape

**2 o 3 `run-verify` fallidos sobre el mismo problema en OpenCode → handoff a Claude Code.** No es una derrota, es el diseño del sistema. Si OpenCode entra en bucle es porque el problema dejó de ser de tipeo y pasó a ser de diseño: eso es trabajo de la otra herramienta. Insistir una cuarta vez quema tiempo y ensucia el repo con intentos a medio revertir.

Antes del handoff: revertí los cambios a medias. Se pasa un estado limpio, no un desastre parcial.

### Plantilla

```
## Objetivo
<qué tiene que quedar funcionando, en una frase>

## Change y estado
Change: <slug>
Spec: openspec/changes/<slug>/ (aprobada el <fecha>)
Tareas completas: <N de M> — <cuáles>
Tarea trabada: <cuál, y qué falla exactamente>
Intentos previos: <qué se probó y por qué no funcionó>

## Archivos que podés tocar
<lista explícita>
NO toques: <lista explícita>

## Restricciones
.instructions.md §<códigos relevantes>
Escenarios de la spec que tienen que pasar: <cuáles>

## Comando de verificación
uv run pytest tests/<ruta> -x
run-verify completo antes de dar por cerrada la tarea
```

El handoff en la dirección inversa (Claude Code → OpenCode) usa la misma plantilla y sirve para lo mismo: terminar el trabajo mecánico que quedó después de que se resolvió el diseño.

## 4. Rutina por change — 9 pasos

Esto se repite idéntico para los 10 changes. Los prompts exactos están en el playbook.

| # | Paso | Herramienta | Corte |
|---|---|---|---|
| 1 | Elegir el change del plan, confirmar que el anterior está archivado, crear la rama `change/<slug>` | — | El anterior tiene que estar mergeado y archivado |
| 2 | `/opsx-propose` con el prompt largo del playbook | Cualquiera | — |
| 3 | **🛑 REVISAR LA SPEC** — `proposal.md`, `design.md`, `specs/`, `tasks.md` | **Humano** | **No se delega. Sin OK explícito no se avanza** |
| 4 | Ajustar la spec si hace falta → volver al paso 3 | Cualquiera | Hasta que la spec diga lo que tiene que decir |
| 5 | `/opsx-apply <change>` tarea por tarea, `run-verify` tras cada una | Según la matriz | Rojo ⇒ frenar. 2-3 rojos iguales en OpenCode ⇒ handoff |
| 6 | Verificación funcional escenario por escenario contra la app corriendo, con `@api-explorer` | Cualquiera | Tabla escenario → PASS/FAIL con evidencia. Los FAIL se corrigen |
| 7 | Auditoría `@security` — **solo changes 00, 02, 03, 05, 08** | Cualquiera | Riesgo medio/alto se corrige antes de archivar |
| 8 | Abrir el PR → `run-verify` y `security-audit` sobre el PR → revisión → merge a `main` | MCP `github` | Checks en verde. Nada se mergea directo a `main` |
| 9 | `/opsx-archive <change>` + `update-estado` + bitácora en el README | Cualquiera | Tasks completas, PR mergeado, verificación verde |

Los changes grandes (02, 03, 04) se parten en varios PRs por bloque coherente de `tasks.md`: los pasos 5 a 8 se repiten por bloque, y el paso 9 corre una sola vez al cerrar el change completo. Un PR de 40 archivos no lo revisa nadie.

El paso 3 es el único que no tiene herramienta asignada, y es a propósito. **Es tuyo.** Es el punto donde el proyecto se define, y el único lugar donde encontrás un malentendido de negocio antes de que cueste 800 líneas.

## 5. Checklist de cierre de change

Antes de archivar, todo esto tiene que ser cierto:

- [ ] Todas las tareas de `tasks.md` completas, ninguna marcada a mano sin ejecutar (`PRI-5`)
- [ ] `run-verify` completo en verde: ruff + format + mypy + pytest
- [ ] Cada escenario de la spec verificado contra la app corriendo, con evidencia (`PASS`, no "debería andar")
- [ ] Las reglas de concurrencia del change tienen test en paralelo, no secuencial (`VER-2`)
- [ ] Toda migración probada `upgrade` y `downgrade` (`VER-4`)
- [ ] Ningún texto de cara al cliente hardcodeado; todas las claves existen en `messages.yaml` (`TXT-1`, `TXT-3`)
- [ ] Ningún valor de negocio hardcodeado: timeouts, zonas, horarios, topes (`GEN-7`)
- [ ] Si el change es `@security`: auditoría hecha, hallazgos medio/alto corregidos
- [ ] Los non-goals se respetaron: no entró nada "de paso" (`SDD-3`)
- [ ] Todos los PRs del change mergeados a `main`, con los checks en verde
- [ ] `ESTADO.md` actualizado y bitácora escrita en el README

## 6. Checklist de cierre de sesión

Aunque el change quede a la mitad:

- [ ] `update-estado`: dónde quedó, qué sigue, qué está bloqueado
- [ ] Bitácora en el README: prompt usado, qué ajusté a mano, qué corrigió el loop de `run-verify` con ejemplo concreto, CU cubiertos
- [ ] Nada a medio revertir en el working tree
- [ ] Decisiones nuevas anotadas en `ESTADO.md`, no en la cabeza
