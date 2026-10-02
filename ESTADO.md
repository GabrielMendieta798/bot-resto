# ESTADO.md

Snapshot del proyecto entre sesiones. Se actualiza con la skill `update-estado` al cerrar cada change y cada sesión (`SDD-5`).

**Última actualización:** 19/09/2026 — sesión de armado del andamiaje (Fases A y B)

---

## Snapshot

Fase actual: **montaje del ecosistema de desarrollo asistido.** Sin código de producto todavía.

- Diseño cerrado: documento de arquitectura y casos de uso completo (25 CU, 7 ADRs, plan de 10 changes).
- Governance (Fase A) completa y aprobada.
- Skills y subagentes (Fase B) generados: 7 skills, 3 subagentes.
- Repo: `GabrielMendieta798/bot-resto`, commits directos a `main` sin PR. Ya hay código: `core/config.py`, `core/database.py`, y los modelos `Customer`, `MenuItem`, `Order` y `OrderItem`; `conversation.py` y `reservation.py` siguen vacíos. Gabriel trabajó fuera del SDD; `customers` y `menu` se absorben en el change 01 y `orders` en el 02 (`SDD-7`).
- OpenSpec: **sin inicializar**.
- Changes: **0 de 10** propuestos.

## Hecho

- [x] Documento de arquitectura y casos de uso (CP-1 cerrado)
- [x] `.instructions.md` — 17 secciones, aprobado el 18/09/2026
- [x] `AGENTS.md`, `CLAUDE.md`, `AI_README.md`, `AI_WORKFLOW.md`, `.opencode/HIERARCHY.md`
- [x] 7 skills: `run-verify`, `write-tests`, `security-audit`, `add-domain-module`, `add-conv-state`, `migrate-safe`, `update-estado`
- [x] 3 subagentes read-only: `@security`, `@test-writer`, `@api-explorer`
- [ ] Playbook de prompts (Fase C)

## Próximo paso

1. Cerrar la Fase C del andamiaje (playbook de prompts).
2. Fase 0 del playbook: bootstrap del repo + `openspec init` + sanity check de governance + verificar acceso a los MCPs.
3. Change `00-walking-skeleton` — propose, **revisión humana de la spec**, apply en Claude Code, auditoría `@security`, PR, merge, archive.

## Bloqueantes

| # | Qué | Bloquea | Estado |
|---|---|---|---|
| B-2 | **CP-2 — 5 preguntas al dueño del local**: zonas de delivery y costos, ventana y tope de reservas, timeouts de carrito, tiempo de escalada de reserva, horarios (incluido el partido). | Valores finales del YAML. **No bloquea código** gracias a `GEN-7`: se arranca con defaults documentados. | 🟡 Mitigado |
| B-3 | **CP-3 — política vigente de ventana de 24 h y templates de Meta.** Define si se puede avisar estado de pedido y confirmar reservas sin template aprobado. Dependencia que rota; hay que verificarla al construir. | Changes `04`, `05`, `08` | 🔴 Abierto |
| B-4 | **CP-6 — dos claves faltantes en `messages.yaml`**: `pedido_cancelado_staff_push` y `pedido_estado.cancelado`. | Changes `04` y `08` | 🔴 Abierto |
| ~~B-1~~ | ~~Stack del panel sin definir~~ | — | ✅ Resuelto 19/09 — ver Decisiones |

## Deuda técnica

| # | Qué | Severidad |
|---|---|---|
| D-1 | `.env` trackeado en un repo público. **Verificado vacío**, sin credenciales reales. Sacarlo del tracking, agregarlo a `.gitignore` y limpiar el historial (`SEC-1`). | Media |
| D-2 | `.env.example` mal nombrado: `.env .example`, con un espacio. Renombrar y completar con todas las claves requeridas (`SEC-1`). | Baja |
| D-3 | `database.sql` en la raíz como fuente del esquema. Choca con `DAT-6`. Es insumo de referencia del change 01 y se borra cuando exista la migración inicial. **Le faltan 8 cosas que exige `.instructions.md`**: tabla de idempotencia por `message_id` (`WA-4`), `subtotal`/`delivery_fee` (`DAT-7`), `CANCELLED_BY_STAFF` y `cancel_reason` (`ORD-3`, `ORD-11`), timestamps por transición (`GEN-4`), índice único parcial (`DAT-9`), `current_reservation_id` + carrito JSONB + contador de reintentos (`CONV-5/8/4`), marca de escalada de reserva (`RES-5`), y todo lo de panel y auditoría (`PAN-1/3/4`). | Media |
| D-4 | Las skills están en `.claude/skills/`. Falta espejarlas en `.opencode/skills/` con contenido idéntico, y lo mismo con los agentes. **Sin sincronización automática: se hace a mano en cada edición.** | Media |
| D-5 | El layout del repo (`models/` plano, `core/database.py`) difiere del objetivo de `AGENTS.md` (`domain/<modulo>/`, `db/`). Se reconcilia en el change 01, no antes. | Media |
| D-6 | `pyproject.toml`: dependencias sin pinear (`SEC-5`), sin ruff, sin mypy, con `pytest-asyncio` que no corresponde al stack sync (`DAT-3`), y `testpaths` apuntando a una carpeta inexistente. Se arregla en P0.2. | Baja |
| D-7 | `create_engine(echo=True)` loguea todo el SQL, o sea teléfonos y direcciones apenas haya datos reales (`SEC-3`, `DAT-10`). Se arregla en P0.2. | Media |
| D-8 | **Bug activo:** `models/__init__.py` declara `Order` y `OrderItem` en `__all__` sin importarlos. `Base.metadata` no registra esas tablas, así que el `autogenerate` de Alembic no las ve. Se arregla en el change 02. | Alta |
| D-9 | **Bug activo:** `Order.customer` usa `back_populates="orders"` y `Customer` no tiene esa relación. `configure_mappers()` falla en la primera query. Todavía no explotó porque no hay tests ni endpoints que consulten. Se arregla en el change 02. | Alta |
| D-10 | A `Order` le faltan 7 cosas que exige la constitución: `subtotal`/`delivery_fee` (`DAT-7`), los dos estados de cancelación (`ORD-3`, `ORD-5`), `cancel_reason` (`ORD-11`), timestamps por transición (`GEN-4`), el índice único parcial (`DAT-9`), el constraint de `ON_THE_WAY` en retiro (`ORD-4`), y `StrEnum` en Python además del `CHECK`. Todo va en el change 02, listado en su prompt. | Media |
| D-11 | Riesgo de secuencia: con `Order` y `OrderItem` en `Base.metadata`, el `autogenerate` del change 01 los arrastraría a la migración inicial sin que hayan pasado por spec. Bloqueado explícitamente en el prompt del change 01 y cubierto por su escenario 11. | Media |

## Decisiones

| Fecha | Decisión | Por qué |
|---|---|---|
| 18/09 | Monolito modular, no microservicios | ADR-01: un restaurante por instancia no justifica el costo operativo |
| 18/09 | SQLAlchemy sync + path operations `def` | ADR-02: single-tenant ⇒ concurrencia baja garantizada; async resuelve un problema que no existe |
| 18/09 | Lock pesimista `FOR UPDATE` sobre `Conversation` | ADR-03: serializa el mismo número sin infra extra; blinda la carrera cancelar/preparar |
| 18/09 | Idempotencia por tabla `message_id` | ADR-04: Meta reenvía eventos; sin esto un reintento duplica pedidos |
| 18/09 | `StaffNotifier` como interfaz de notificación | ADR-05: el dominio emite eventos, un adapter alerta, y el panel es donde se actúa |
| 18/09 | Intención abstracta → adapter de canal | ADR-06: capa anti-corrupción; el día que entre otro canal el núcleo no se toca |
| 18/09 | Reservas intake con confirmación humana | ADR-07: el MVP no gestiona mesas ni slots |
| 18/09 | Sin IA en el MVP | No hay caso de RAG ni de búsqueda semántica que la justifique hoy (`IA-1`) |
| 18/09 | Webhook devuelve 5xx ante fallo de procesamiento, para que Meta reintente | `WA-9` + `CONV-10`: la marca de idempotencia revierte con la transacción, así el reintento sirve |
| 18/09 | Carrito en columna `JSONB` de `Conversation` | `CONV-8`: única forma de que el lock de `CONV-2` y el reset de `CONV-6` lo cubran de verdad |
| 19/09 | Gestor de dependencias: `uv` | Todos los comandos de `AGENTS.md` asumen `uv run ...`. A confirmar con Gabriel |
| 19/09 | **Panel: Jinja2 + HTMX dentro de la misma app FastAPI.** Sin SPA, sin segundo deploy | ADR-01 ya eligió monolito. Sesión por cookie server-side + CSRF (`PAN-1/5/6`) es gratis así y un dolor con un SPA separado. El auto-refresh de la lista de entrantes (UC-15) lo resuelve HTMX sin build step |
| 19/09 | 7 skills, congeladas. No se suma una skill nueva "por las dudas" | Solo si el patrón se repite de verdad y tiene reglas propias que sin escribir se rompen |
| 19/09 | **Flujo por Pull Requests.** Nada se mergea a `main` directo; `run-verify` y `security-audit` corren sobre el PR | Dos personas sobre el mismo repo. Un PR = un incremento acotado y revisable; los changes grandes se parten en varios PRs |
| 19/09 | Se suma el MCP `github` | Consecuencia del flujo de PRs, no del proyecto. Los MCPs siguen siendo `postgres`, `sequential-thinking` y `github`; nada de tablero ni grafo |
| 19/09 | **Todo identificador en inglés** (`GEN-9`). Prefijo de reglas `PED` → `ORD`. Estados de cancelación separados: `CANCELLED_BY_CUSTOMER` y `CANCELLED_BY_STAFF` | El código ya estaba en inglés. Los dos cancelados son transiciones distintas con reglas distintas (`ORD-2` vs `ORD-3`+`ORD-11`); un `CANCELLED` único las confunde en el `CHECK` y en los tests |
| 19/09 | **`.instructions.md` y `openspec/` van al repo; el resto del andamiaje al `.gitignore`** | Las reglas y las specs se discuten en el PR. `AGENTS.md`, `CLAUDE.md`, `AI_README.md`, `AI_WORKFLOW.md`, `ESTADO.md`, `PLAYBOOK.md`, `.claude/` y `.opencode/` son herramientas de Lautaro, no contrato compartido |
| 19/09 | La reconciliación del layout entra en el change 01, no en la Fase 0 | Mover archivos sin spec es exactamente lo que `SDD-1` prohíbe. La Fase 0 agrega al lado de lo que hay |
| 19/09 | **El aviso al staff es el propio panel**: el adapter de `StaffNotifier` persiste la notificación, el panel la levanta por polling HTMX y avisa con sonido + notificación del navegador (`NOT-2`, `PAN-9`, `PAN-10`) | Instantáneo, gratis, sin ventana de 24 h ni templates de Meta, sin números extra, y sin acoplar la operación interna del restaurante a la política de precios de Meta, que además encarece utility templates y service messages desde el 1/10/2026. La tablet ya va a estar abierta en la cocina |
| 19/09 | **Se saca Telegram.** El MVP no tiene canal de notificación externo; `StaffNotifier` queda con un adapter de logging como única implementación (`NOT-2`, `NOT-6`) | Revierte la parte de ADR-05 que elegía canal. La interfaz y el evento de dominio se mantienen: por eso existía el `StaffNotifier`. **Consecuencia abierta: hasta el change 08 el staff no tiene forma de enterarse de un pedido nuevo salvo mirando el panel** |

## Changes archivados

*(ninguno todavía)*
