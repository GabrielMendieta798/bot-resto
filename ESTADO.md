# ESTADO.md

Snapshot del proyecto entre sesiones. Se actualiza con la skill `update-estado` al cerrar cada change y cada sesión (`SDD-5`).

**Última actualización:** 03/10/2026 — cierre de `add-application-skeleton` (apply completo y archivado)

> **Hueco conocido:** entre el 19/09 y el 02/10 hubo sesiones que no actualizaron este archivo (inicialización de OpenSpec, tres changes propuestos, cuatro migraciones, PRs #15 a #19). Lo de ese período que no se pudo verificar en el repo figura como `ESTADO DESCONOCIDO`.

---

## Snapshot

Fase actual: **esqueleto de la aplicación cerrado y archivado.** La app levanta y se puede verificar; todavía ningún caso de uso.

- Repo: `GabrielMendieta798/bot-resto`. Flujo por PR vía `develop` (PRs #15 a #23 mergeados; `develop` y `main` en `4bc1c24`). Ramas `change/<slug>`.
- OpenSpec inicializado. Changes activos: **3** (`add-whatsapp-message-idempotency`, `allow-order-additions`, `migrate-identifiers-to-bigint`). Archivados: **1** (`add-application-skeleton`). Main specs en `openspec/specs/`: 6 capabilities. Los nombres no siguen la numeración 00–09 del plan de `AI_WORKFLOW.md`; la correspondencia es `ESTADO DESCONOCIDO`.
- **`add-application-skeleton`:** archivado el 03/10 (40/40 tareas). Último `run-verify` en verde el 03/10: ruff, format, mypy estricto, 92 tests unitarios y 1 de integración. `@security`: tercera pasada sin medios ni altos. Llegó a `main` en los PRs #20 a #23.
- Base local de desarrollo: contenedor `bot-resto-db` (`postgres:16`). Los tests de integración corren contra ella.
- La app ya levanta: `uv run uvicorn app.main:app` desde `backend/`. Exige `APP_ENV` en el `.env`.

## Hecho

- [x] Documento de arquitectura y casos de uso (CP-1 cerrado)
- [x] `.instructions.md` — 17 secciones, aprobado el 18/09/2026
- [x] `AGENTS.md`, `CLAUDE.md`, `AI_README.md`, `AI_WORKFLOW.md`, `.opencode/HIERARCHY.md`
- [x] 7 skills: `run-verify`, `write-tests`, `security-audit`, `add-domain-module`, `add-conv-state`, `migrate-safe`, `update-estado`
- [x] 3 subagentes read-only: `@security`, `@test-writer`, `@api-explorer`
- [ ] Playbook de prompts (Fase C) — `PLAYBOOK.md` existe; si la Fase C se dio por cerrada es `ESTADO DESCONOCIDO`
- [x] `add-application-skeleton` — archivado el 03/10/2026 (PRs #20 a #23)

## Próximo paso

1. **Elegir cuál de los tres changes activos sigue** (`add-whatsapp-message-idempotency`, `allow-order-additions`, `migrate-identifiers-to-bigint`). El orden respecto del plan 00–09 (`SDD-6`) es `ESTADO DESCONOCIDO`: confirmarlo antes de arrancar.
2. Al retomarlo, revisar su `tasks.md`: sus tareas de verificación ahora tienen dónde correr (`tests/unit`, `tests/integration`, `run-verify`). `add-whatsapp-message-idempotency` tiene pendientes 1.3–1.6, 3.1–3.7, 4.1–4.7 y 5.1–5.2; las de migración necesitan la base `bot-resto-db`.
3. El primer change que exponga el webhook arrastra las deudas D-12 a D-14 (D-14 es Media y va **antes** de exponerlo).

## Bloqueantes

| # | Qué | Bloquea | Estado |
|---|---|---|---|
| B-2 | **CP-2 — 5 preguntas al dueño del local**: zonas de delivery y costos, ventana y tope de reservas, timeouts de carrito, tiempo de escalada de reserva, horarios (incluido el partido). | Valores finales del YAML. **No bloquea código** gracias a `GEN-7`: los defaults documentados ya viven en `config/restaurant.yaml` (02/10), con encabezado que remite a estas 5 preguntas. | 🟡 Mitigado |
| B-3 | **CP-3 — política vigente de ventana de 24 h y templates de Meta.** Define si se puede avisar estado de pedido y confirmar reservas sin template aprobado. Dependencia que rota; hay que verificarla al construir. | Changes `04`, `05`, `08` | 🔴 Abierto |
| B-4 | **CP-6 — dos claves faltantes en `messages.yaml`**: `pedido_cancelado_staff_push` y `pedido_estado.cancelado`. | Changes `04` y `08` | 🔴 Abierto |
| ~~B-1~~ | ~~Stack del panel sin definir~~ | — | ✅ Resuelto 19/09 — ver Decisiones |

## Deuda técnica

| # | Qué | Severidad |
|---|---|---|
| ~~D-1~~ | ✅ Parcial, verificado 03/10: `.env` ya no está trackeado (`git ls-files .env` vacío) y está en `.gitignore`, que desde el 03/10 cubre también `.env.*`. La limpieza del historial es `ESTADO DESCONOCIDO`. Original: `.env` trackeado en un repo público. **Verificado vacío**, sin credenciales reales. Sacarlo del tracking, agregarlo a `.gitignore` y limpiar el historial (`SEC-1`). | Media |
| ~~D-2~~ | ✅ Resuelto, verificado 03/10: `.env.example` bien nombrado y completo (`add-application-skeleton`, con test que lo compara contra las settings). Original: `.env.example` mal nombrado: `.env .example`, con un espacio. Renombrar y completar con todas las claves requeridas (`SEC-1`). | Baja |
| ~~D-3~~ | ✅ Verificado 03/10: `database.sql` ya no está en el repo y hay 4 migraciones de Alembic. Si las migraciones cubren las 8 faltas listadas es `ESTADO DESCONOCIDO`. Original: `database.sql` en la raíz como fuente del esquema. Choca con `DAT-6`. Es insumo de referencia del change 01 y se borra cuando exista la migración inicial. **Le faltan 8 cosas que exige `.instructions.md`**: tabla de idempotencia por `message_id` (`WA-4`), `subtotal`/`delivery_fee` (`DAT-7`), `CANCELLED_BY_STAFF` y `cancel_reason` (`ORD-3`, `ORD-11`), timestamps por transición (`GEN-4`), índice único parcial (`DAT-9`), `current_reservation_id` + carrito JSONB + contador de reintentos (`CONV-5/8/4`), marca de escalada de reserva (`RES-5`), y todo lo de panel y auditoría (`PAN-1/3/4`). | Media |
| D-4 | Sigue abierta, verificado 03/10: `diff -rq .claude/skills .opencode/skills` encuentra diferencias (al menos en las skills de OpenSpec). Original: Las skills están en `.claude/skills/`. Falta espejarlas en `.opencode/skills/` con contenido idéntico, y lo mismo con los agentes. **Sin sincronización automática: se hace a mano en cada edición.** | Media |
| D-5 | El layout del repo (`models/` plano, `core/database.py`) difiere del objetivo de `AGENTS.md` (`domain/<modulo>/`, `db/`). Se reconcilia en el change 01, no antes. | Media |
| ~~D-6~~ | ✅ Resuelto 02/10 en `add-application-skeleton` (PR #20): versiones con `==`, `uv.lock` regenerado, ruff, mypy estricto sin overrides, sin `pytest-asyncio`, markers `unit`/`integration`. Original: `pyproject.toml`: dependencias sin pinear (`SEC-5`), sin ruff, sin mypy, con `pytest-asyncio` que no corresponde al stack sync (`DAT-3`), y `testpaths` apuntando a una carpeta inexistente. Se arregla en P0.2. | Baja |
| ~~D-7~~ | ✅ Resuelto 02/10 en `add-application-skeleton`: `DATABASE_ECHO` apagado por default y prohibido con `APP_ENV=production`; además `hide_parameters=True`. Original: `create_engine(echo=True)` loguea todo el SQL, o sea teléfonos y direcciones apenas haya datos reales (`SEC-3`, `DAT-10`). Se arregla en P0.2. | Media |
| ~~D-8~~ | ✅ Verificado 03/10: `models/__init__.py` ya importa `Order` y `OrderItem`. En qué change se arregló es `ESTADO DESCONOCIDO`. Original: **Bug activo:** `models/__init__.py` declara `Order` y `OrderItem` en `__all__` sin importarlos. `Base.metadata` no registra esas tablas, así que el `autogenerate` de Alembic no las ve. Se arregla en el change 02. | Alta |
| D-9 | Verificado 03/10: `Customer` ya tiene la relación `orders`. **Falta confirmar** que `configure_mappers()` no falle (ningún test lo ejercita todavía). Original: **Bug activo:** `Order.customer` usa `back_populates="orders"` y `Customer` no tiene esa relación. `configure_mappers()` falla en la primera query. Todavía no explotó porque no hay tests ni endpoints que consulten. Se arregla en el change 02. | Alta |
| D-10 | A `Order` le faltan 7 cosas que exige la constitución: `subtotal`/`delivery_fee` (`DAT-7`), los dos estados de cancelación (`ORD-3`, `ORD-5`), `cancel_reason` (`ORD-11`), timestamps por transición (`GEN-4`), el índice único parcial (`DAT-9`), el constraint de `ON_THE_WAY` en retiro (`ORD-4`), y `StrEnum` en Python además del `CHECK`. Todo va en el change 02, listado en su prompt. | Media |
| D-11 | Riesgo de secuencia: con `Order` y `OrderItem` en `Base.metadata`, el `autogenerate` del change 01 los arrastraría a la migración inicial sin que hayan pasado por spec. Bloqueado explícitamente en el prompt del change 01 y cubierto por su escenario 11. | Media |
| D-12 | **Para el change que exponga el webhook (00).** El `field` del error 400 refleja la última parte de `loc`: con campos `dict` o modelos `extra="forbid"`, es una clave que mandó el cliente, devuelta sin límite de largo (`API-2`, `VAL-1`). Devolver `field` solo si es un campo declarado. | Baja |
| D-13 | **Para el change que agregue el adapter de WhatsApp (00).** `OutboundHttpClient` no traduce `httpx.InvalidURL`, `CookieConflict` ni `StreamError`. Y si un adapter llama `raise_for_status()`, la `HTTPStatusError` lleva la URL completa con su query (p. ej. `access_token`) y termina en el log del 500. Prohibir `raise_for_status()` en adapters y ofrecer un chequeo de status en el cliente que levante `OutboundHttpError` con método, host y status (`SEC-2`). | Baja |
| D-14 | **Para el change que exponga el webhook (00), antes de exponerlo.** El access log de uvicorn imprime la query string completa (verificado: `GET /health?token=abc` aparece entero). El `GET` de verificación de Meta trae `hub.verify_token` en la query (`SEC-2`). Apagar o filtrar el access log. | Media |
| D-15 | **Para el change que tome `backend/alembic/`.** `env.py` pasa `str(settings.database_url)` a `config.set_main_option`, que interpola con ConfigParser: una contraseña con `%` (así se codifican `@` o `/` en una URL) levanta `ValueError` con la URL completa, contraseña incluida, en el traceback de `alembic upgrade` (`SEC-2`). Pasar `.replace("%", "%%")`. | Baja |
| D-16 | Si falla el propio logging de un error inesperado, se re-imprime la excepción original entera: `_log_unexpected` corre dentro del `except` (una falla nueva queda encadenada y sale por uvicorn), y `logging.raiseExceptions=True` hace que `handleError` vuelque la cadena en stderr sin enmascarar (`SEC-3`, `API-2`). Sin disparador hoy. Loguear fuera del `except` con fallback de solo `error_type`, y `logging.raiseExceptions=False` o un `handleError` propio. Bajo de la 3.ª pasada de `@security`. | Baja |
| D-17 | `_exception_chain` (`api/errors.py`) no recorre `BaseExceptionGroup.exceptions`: un grupo con varias excepciones, una de ellas `IntegrityError`, se loguea con `exc_info` completo (`SEC-3`). Sin disparador hoy (no hay task groups). Resolver en el change que introduzca `TaskGroup` o `gather`. Bajo de la 3.ª pasada de `@security`. | Baja |
| D-18 | **Para el change del panel (08).** `add_middleware` inserta al principio: todo middleware agregado después de `UnhandledErrorMiddleware` (sesión, CSRF, CORS) queda por fuera, y sus errores vuelven a `ServerErrorMiddleware` + uvicorn, con log doble y texto completo (`API-2`, `SEC-3`). Un test fija que `UnhandledErrorMiddleware` sea el más interno. | Baja |
| D-19 | **Para el change del panel (08).** `/docs` y `/openapi.json` quedan públicos: no exponen datos, pero sí la superficie del panel. Decidir si se apagan en producción. | Baja |
| D-20 | El `TestClient` de Starlette sobre `httpx` está deprecado (warning en cada corrida de tests); recomienda `httpx2`. Resolver en la próxima actualización de dependencias, pineando la versión (`SEC-5`). | Baja |

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
| 02/10 | **`GET /health` con la base caída responde 503 con cuerpo**, no 200 | Un monitor u orquestador decide por el código de estado, no por el cuerpo. 503 con cuerpo cumple "no un 500 sin cuerpo" y la distinción app/base vive en el cuerpo. `API-3` no lista 503 pero tampoco lo prohíbe |
| 02/10 | **Textos de error HTTP en `config/http_errors.yaml`, separados de `messages.yaml`** | `messages.yaml` lo edita el dueño del local (`TXT-2`) y no tiene que toparse con strings internos. Una sección aparte dentro del mismo archivo no lo cumplía |
| 02/10 | `messages.yaml` con solo comentarios mientras no haya copy; el vacío se acepta **solo** en ese archivo | Más legible para el dueño que un `{}` literal. Archivo ausente o clave desconocida siguen sin dejar levantar la app |
| 02/10 | **Sin override de mypy para `app.models.*`** | Los modelos pasan estricto tal como están (verificado apagando el override). Una exención que no exime nada solo hace ruido; si un modelo rompe mypy, se decide ahí |
| 02/10 | `APP_ENV` obligatorio y sin default; `DATABASE_ECHO=true` con `production` no deja arrancar | Con default, un deploy que se olvida de setearlo caería en `development` y el guard de `DAT-10` no serviría |
| 02/10 | `DATABASE_URL` como `str` con `repr=False`, no `SecretStr` | `backend/alembic/env.py` (non-goal) hace `str(settings.database_url)`; con `SecretStr` devolvería `**********` |
| 02/10 | Loggers `httpx` y `httpcore` en WARNING | A nivel INFO, httpx loguea la URL completa de cada request saliente, query incluida: ahí puede viajar un token (`SEC-2`). Escenario agregado a la spec con test que falla sin el arreglo |
| 03/10 | **`UnhandledErrorMiddleware` en lugar del handler de `Exception`** | Con el handler, Starlette re-levanta la excepción y uvicorn la vuelve a loguear completa, con datos del cliente. Reproducido con uvicorn real y un `IntegrityError` con dirección: dos records con la dirección; después del arreglo, uno y sin la dirección |
| 03/10 | Errores de SQLAlchemy y de validación (en cualquier eslabón de la cadena) se loguean sin mensaje; el resto de las excepciones conserva su mensaje | Sin mensajes se depura a ciegas. Se descartó la alternativa estricta (ningún mensaje) y se agregó a la spec de `structured-logging` el requirement "Exception messages carry no customer data", para que los próximos changes se enteren y `@security` lo revise |
| 03/10 | Los tests de rutas recorren nuestros routers + el esquema OpenAPI, no `app.routes` | FastAPI 0.142 envuelve los routers incluidos en `_IncludedRouter`, privado; depender de él rompería con cualquier actualización |

## Changes archivados

| Fecha | Change | PRs | Notas |
|---|---|---|---|
| 03/10/2026 | `add-application-skeleton` | #20, #21, #22, #23 | En `openspec/changes/archive/2026-10-03-add-application-skeleton/`. Creó las 6 primeras main specs: `application-runtime`, `development-toolchain`, `error-contract`, `outbound-http-client`, `runtime-configuration`, `structured-logging` |
