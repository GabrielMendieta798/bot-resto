# .instructions.md — WhatsApp bot de pedidos y reservas

Reglas normativas del proyecto. **Fuente de verdad.** Cada regla es imperativa y verificable: un revisor la marca cumplida o no cumplida. No es documentación explicativa. Ante conflicto con cualquier otro documento, prompt, skill o subagente, este archivo prevalece (ver §PRI).

Proyecto: bot de WhatsApp para restaurante de pastas y parrilla (pedidos + reservas intake). Stack cerrado: monolito modular en Python — FastAPI + PostgreSQL + SQLAlchemy sync + Alembic + PyWa (WhatsApp Cloud API) + APScheduler + pytest + Docker + Jinja2/HTMX para el panel.

**Alcance:** este archivo y el resto del andamiaje de desarrollo asistido viven fuera del repositorio compartido. Gobiernan todo el trabajo dirigido con agentes; no son un contrato con terceros.

Convención de códigos:
`GEN` transversal · `DAT` datos · `CONV` conversación · `WA` WhatsApp · `TXT` textos/guión · `NOT` notificación · `ORD` pedidos · `RES` reservas · `PAN` panel · `VAL` validación · `API` contrato HTTP · `SEC` seguridad · `VER` verificación y tests · `SDD` spec-driven development · `IA` módulo de IA · `PRI` prioridad.

---

## Vocabulario de estados

Identificadores canónicos. El código, la DB y las specs usan **exactamente** estos valores.

**`OrderStatus`** — `RECEIVED` · `PREPARING` · `READY` · `ON_THE_WAY` · `DELIVERED` · `CANCELLED_BY_CUSTOMER` · `CANCELLED_BY_STAFF`

**`ReservationStatus`** — `REQUESTED` · `CONFIRMED` · `REJECTED` · `CANCELLED`

**`DeliveryType`** — `DELIVERY` · `PICKUP`

**`ConversationState`** — `MAIN_MENU` · `HANDOFF` · `POST_ORDER` · `POST_RESERVATION` · los estados de flujo que cada change agregue

**Eventos de dominio** — `OrderReceived` · `ReservationRequested`

---

## GEN — Principio rector (transversal)

- **GEN-1** — El dominio (módulos `customers`, `menu`, `orders`, `reservations`, `conversations`) no importa PyWa, ni la `Session` de SQLAlchemy, ni ningún cliente de notificación. Toda dependencia externa entra por una interfaz/adapter.
- **GEN-2** — El sistema tiene tres fronteras obligatorias: repositorio por módulo (datos), intención de respuesta abstracta → adapter de canal (WhatsApp), y evento de dominio → `StaffNotifier` (notificación). Ningún módulo de dominio cruza una frontera sin pasar por su interfaz.
- **GEN-3** — Todos los secretos (tokens de Meta, cadena de conexión de la DB, claves del panel, y las credenciales de cualquier canal de notificación que se sume) viven en variables de entorno / `.env` fuera del repo. Ningún secreto hardcodeado ni commiteado a Git.
- **GEN-4** — Toda transición de estado (pedido, reserva, conversación) registra su timestamp al aplicarse.
- **GEN-5** — El despliegue es una instancia por restaurante (single-tenant clonable). No hay multi-tenant en el MVP.
- **GEN-6** — Todo timestamp persistido es `TIMESTAMPTZ` almacenado en UTC. La zona horaria del local vive en config (`America/Argentina/Buenos_Aires` por default) y se aplica solo al presentar y al validar horarios de negocio (RES-2, RES-8, UC-13). Prohibido `datetime.now()` sin zona.
- **GEN-7** — Ningún valor de negocio configurable se hardcodea: timeouts de carrito e inactividad, límite de reintentos, zonas de delivery y sus costos, ventana y tope de personas de reservas, tiempo de escalada de reserva, horarios del local. Todos entran por YAML o env. Mientras las preguntas de negocio sigan abiertas, los valores son **defaults documentados en el YAML**, no constantes en código.
- **GEN-8** — Los jobs del scheduler (expiración de carrito, escalada de reservas) corren en un único proceso. Si el deploy levanta más de un worker, cada job toma un lock en DB antes de ejecutar. Ningún timeout puede dispararse dos veces por el mismo evento.
- **GEN-9** — **Todo identificador de código va en inglés**: módulos, clases, funciones, tablas, columnas, valores de estado, eventos de dominio y claves de `messages.yaml`. El único castellano del sistema es el texto de cara al cliente, que vive como **valor** en `messages.yaml`, y las palabras que el cliente escribe para los comandos globales (`menú`, `cancelar`, `atrás`, `hablar con una persona`), que son dato de entrada, no identificadores.

## DAT — Capa de datos

- **DAT-1** — Las path operations de FastAPI que tocan datos se declaran `def` (no `async def`); FastAPI las corre en su threadpool.
- **DAT-2** — El acceso a datos de cada módulo va detrás de una capa de repositorio propia. El dominio nunca usa la `Session` de SQLAlchemy directamente.
- **DAT-3** — SQLAlchemy opera en modo sync. No se introduce async SQLAlchemy ni asyncpg.
- **DAT-4** — Al confirmar un pedido se persiste `unit_price_snapshot` en cada `OrderItem`. Editar el precio de un `MenuItem` no altera Orders existentes.
- **DAT-5** — Marcar un item agotado togglea `MenuItem.available`; el `MenuItem` nunca se borra.
- **DAT-6** — Los cambios de esquema van versionados con Alembic. No se modifica el esquema fuera de una migración. No existe ningún `.sql` suelto como fuente del esquema.
- **DAT-7** — `Order` separa `subtotal`, `delivery_fee` y `total` en campos distintos.
- **DAT-8** — Todo importe monetario se modela como `Numeric(12,2)` en DB y `Decimal` en Python. Prohibido `float` para dinero, en modelo, en cálculo y en serialización.
- **DAT-9** — La invariante ORD-6 se garantiza en la DB con un índice único parcial sobre `orders(customer_id)` filtrado por los estados no-terminales, además del chequeo en dominio. No alcanza con validar en código.
- **DAT-10** — El logging de SQL (`create_engine(echo=...)`) se controla por config y está apagado por default. Nunca encendido en producción: el SQL crudo expone teléfonos y direcciones (§SEC-3).

## CONV — Conversación

- **CONV-1** — El router de conversación se implementa como máquina de estados explícita (tabla/dict de transiciones o librería equivalente), no como `if/elif` anidado.
- **CONV-2** — El procesamiento de cada mensaje entrante corre bajo `SELECT ... FOR UPDATE` de la fila `Conversation` del cliente. Serializa los mensajes del mismo número; no bloquea números distintos.
- **CONV-3** — Tres comandos globales están disponibles desde cualquier estado de flujo: "menú"/"cancelar" (→ `MAIN_MENU`, descarta el flujo en curso), "atrás" (→ paso anterior del flujo), "hablar con una persona" (→ `HANDOFF`).
- **CONV-4** — Un input no reconocido en un estado responde el fallback ("no te entendí, elegí una opción") y suma un reintento. Superado el límite de reintentos configurado, deriva a `HANDOFF`.
- **CONV-5** — Al cerrar `POST_ORDER` o `POST_RESERVATION` se limpian `current_order_id` y `current_reservation_id` de la Conversation.
- **CONV-6** — El aviso por inactividad y el reset de sesión usan los timeouts definidos en config; no se hardcodean valores. Al resetear se descarta el carrito (es estado conversacional, no un Order).
- **CONV-7** — El carrito vive en estado conversacional hasta la confirmación. No se persiste como Order antes de UC-07.
- **CONV-8** — El carrito se almacena en una columna `JSONB` de la fila `Conversation`, para que quede cubierto por el lock de CONV-2 y por el reset de CONV-6. No vive en memoria de proceso ni en una tabla aparte.
- **CONV-9** — El orden de adquisición de locks es fijo en todo el sistema: primero el `INSERT` de idempotencia (WA-4), después el `FOR UPDATE` de `Conversation`, después cualquier otro `FOR UPDATE` (Order, Reservation). Nunca en otro orden.
- **CONV-10** — El `INSERT ... ON CONFLICT` de WA-4 y todo el efecto de dominio del mensaje comparten una **única transacción**: si el procesamiento falla, la marca de idempotencia se revierte con él. Los envíos salientes (WhatsApp, notificación al staff) se disparan **después del commit**, nunca dentro de la transacción.

## WA — WhatsApp

- **WA-1** — Solo `integrations/whatsapp/` importa PyWa. `conversations/` y el resto del dominio no importan PyWa.
- **WA-2** — El dominio devuelve una intención de respuesta abstracta (`ShowMenu`, `AskQuantity`, `AskConfirmation`). El adapter de WhatsApp la traduce a botones/listas de PyWa. La traducción vive solo en el adapter.
- **WA-3** — Todo webhook verifica origen/firma antes de procesar: el `GET` de verificación devuelve `hub.challenge` solo si el verify token coincide; el `POST` valida `X-Hub-Signature-256` (HMAC-SHA256 con el app secret) con comparación en tiempo constante. Firma inválida ⇒ 403 y no se procesa.
- **WA-4** — Todo webhook hace `INSERT ... ON CONFLICT DO NOTHING` sobre la tabla de eventos procesados por `message_id` antes de procesar. Si el registro ya existe, responde 200 y corta sin re-procesar.
- **WA-5** — Los mensajes iniciados por el negocio fuera de la ventana de 24 h usan un template pre-aprobado de Meta. Dentro de la ventana, se responde con texto libre.
- **WA-6** — La navegación del menú es por botones/listas estructuradas; el bot no interpreta lenguaje libre para inferir intención (eso es fase 2). Los inputs de texto que el flujo pide explícitamente y valida como dato estructurado (cantidad numérica, dirección de entrega, nombre) sí se aceptan.
- **WA-7** — Las respuestas con más de 3 opciones se envían como lista (hasta 10 filas). Los botones se usan solo hasta 3 opciones (límite de la Cloud API).
- **WA-8** — Los nombres/ids de los templates de Meta y el mapeo de sus parámetros viven en config, no en `messages.yaml` (que guarda solo copy de texto libre dentro de la ventana). Cambiar de template aprobado no toca código.
- **WA-9** — Un fallo de procesamiento revierte la transacción (incluida la marca de idempotencia, CONV-10) y el webhook responde 5xx para habilitar el reintento de Meta, logueando el `message_id`. Duplicado ⇒ 200 y corte (WA-4). Firma inválida ⇒ 403 (WA-3).

## TXT — Textos / guión de conversación

- **TXT-1** — Todo texto de cara al cliente vive en `messages.yaml`, referenciado por clave **en inglés** (p. ej. `order.confirmed`). El código usa la clave, nunca el literal. El valor está en castellano rioplatense.
- **TXT-2** — `messages.yaml` es config por instancia: cada cliente clonado tiene el suyo. Cambiar redacción o emojis se hace editando el YAML, sin tocar código ni redeployar.
- **TXT-3** — Toda clave referenciada desde código existe en `messages.yaml`. La ausencia de una clave falla en el arranque de la app, no en runtime frente al cliente.

## NOT — Notificación al staff

- **NOT-1** — El dominio emite eventos de dominio (`OrderReceived`, `ReservationRequested`) contra la interfaz `StaffNotifier`. No llama a ningún canal externo directamente.
- **NOT-2** — **El canal del MVP es el propio panel.** El adapter registrado de `StaffNotifier` persiste el evento como notificación pendiente; el panel la levanta y avisa. No hay canal externo (WhatsApp, Telegram, email, SMS) en el MVP. Sumar uno es un adapter nuevo, sin tocar el dominio.
- **NOT-3** — `StaffNotifier` admite varios adapters activos en simultáneo.
- **NOT-4** — El panel es el único punto de acción del staff. Ningún adapter de notificación, presente o futuro, opera pedidos ni reservas: solo alerta.
- **NOT-5** — El fallo de un adapter de notificación no revierte ni bloquea la operación de dominio ya commiteada: se loguea y se reintenta según la política de config. Persistir el pedido y avisar al staff son dos pasos, no uno.
- **NOT-6** — El evento de dominio y su recorrido por `StaffNotifier` son obligatorios y testeables desde el change 06, antes de que exista el panel que los muestra. No se saltea el paso "porque todavía no lo lee nadie".
- **NOT-7** — Cada notificación registra si fue vista. Una notificación ya vista no vuelve a sonar ni a reaparecer, aunque el panel se recargue, se abra en dos dispositivos, o el polling la traiga de nuevo.
- **NOT-8** — El cuerpo de la notificación del navegador lleva solo el mínimo: tipo de operación, identificador y total. Nunca dirección de entrega, teléfono ni nombre del cliente (`SEC-3`); esos datos se ven dentro del panel, con sesión autenticada.

## ORD — Pedidos

- **ORD-1** — La transición `RECEIVED → PREPARING` la dispara el staff. Es el candado que cierra la ventana de cancelación del cliente.
- **ORD-2** — La cancelación por cliente (`RECEIVED → CANCELLED_BY_CUSTOMER`) commitea solo si `status` sigue en `RECEIVED` bajo `SELECT ... FOR UPDATE`. Si ya pasó a `PREPARING`, se rechaza y se informa al cliente.
- **ORD-3** — El staff puede cancelar/marcar fallido (`→ CANCELLED_BY_STAFF`) desde `RECEIVED`, `PREPARING`, `READY` y `ON_THE_WAY`.
- **ORD-4** — `ON_THE_WAY` aplica solo a `DELIVERY`. En `PICKUP`, el camino válido es `READY → DELIVERED` directo; no se permite `ON_THE_WAY` en un retiro.
- **ORD-5** — Estados terminales del pedido: `DELIVERED`, `CANCELLED_BY_CUSTOMER`, `CANCELLED_BY_STAFF`. Un estado terminal no tiene transición saliente.
- **ORD-6** — Un cliente no puede tener más de un Order en estado no-terminal a la vez. Hasta cerrar el actual, no puede iniciar otro. (Garantizado en DB por DAT-9.)
- **ORD-7** — UC-05 (modificar pedido) permite sumar líneas, restar cantidad y quitar líneas, solo mientras el pedido no está confirmado. Restar hasta cero elimina la línea.
- **ORD-8** — El Order se crea transaccionalmente en UC-07, tras confirmación explícita del cliente. Un doble-tap del botón confirmar (mismo `message_id`) no crea dos Orders (queda cubierto por WA-4).
- **ORD-9** — Confirmar pedido exige local abierto (UC-13) y, si es `DELIVERY`, zona válida (UC-14).
- **ORD-10** — Al seleccionar o confirmar un item se re-verifica `MenuItem.available`. Si dejó de estar disponible entre el listado y la acción, se informa al cliente y el item no se agrega ni se confirma.
- **ORD-11** — La transición a `CANCELLED_BY_STAFF` exige un motivo registrado en `cancel_reason`. El aviso al cliente incluye ese motivo.
- **ORD-12** — El ETA de preparación de un pedido se calcula como el `estimated_time_min` del item más lento del carrito. Si es `DELIVERY`, se le suma el tiempo de entrega de la zona definido en config.
- **ORD-13** — Una transición de estado inválida (no contemplada en la máquina de estados) se rechaza explícitamente y se registra. Nunca se aplica "por las dudas" ni se ignora en silencio.

## RES — Reservas

- **RES-1** — Reservas en modo intake: el staff confirma (`CONFIRMED`) o rechaza (`REJECTED`). El sistema nunca auto-confirma ni auto-rechaza una reserva.
- **RES-2** — UC-R1 valida en el intake, antes de crear la `REQUESTED`: fecha futura, dentro del horario del local (YAML), y dentro de la ventana y el tope de personas configurados.
- **RES-3** — Las opciones de fecha y hora se ofrecen como listas derivadas de las franjas del YAML. No se acepta texto libre para fecha ni hora.
- **RES-4** — El cliente puede cancelar en `REQUESTED` (→ `CANCELLED`) y en `CONFIRMED` (→ `CANCELLED`).
- **RES-5** — Una `REQUESTED` sin resolver pasado el tiempo configurado avisa al cliente "seguimos procesando" y la marca como escalada, sin cambiar de estado. No hay urgencia diferenciada por cercanía de la reserva (fuera del MVP).
- **RES-6** — La confirmación de reserva al cliente se envía mediante template de utilidad pre-aprobado (cae típicamente fuera de la ventana de 24 h; ver WA-5 y WA-8).
- **RES-7** — No existe estado de no-show. No se implementa en el MVP.
- **RES-8** — Los horarios del local viven en config YAML por instancia, con soporte de horario partido. No en tabla de DB.
- **RES-9** — Si el cliente tiene más de una reserva en estado no-terminal, UC-R2 y UC-R3 ofrecen la lista para que elija (aplica WA-7). Nunca se asume "la última".
- **RES-10** — El aviso de escalada (RES-5) se emite una sola vez por reserva. Re-ejecutar el job no vuelve a avisarle al cliente.

## PAN — Panel administrativo

- **PAN-1** — El panel exige login usuario/clave por instancia. Toda acción de staff (cambiar estado, confirmar/rechazar reserva, editar menú, togglear disponibilidad, reactivar el bot) requiere sesión autenticada.
- **PAN-2** — El panel es el punto de acción del staff: donde cambia estados y opera. La alerta, cuando exista un canal, solo lo trae al panel.
- **PAN-3** — Las claves del panel se almacenan hasheadas (bcrypt o argon2). Nunca en texto plano ni de forma reversible.
- **PAN-4** — Toda acción de staff que cambia estado o datos deja un registro auditable con quién, qué y cuándo. Alcance MVP: traza append-only, sin pantalla de auditoría dedicada.
- **PAN-5** — La sesión del panel se transporta en cookie `HttpOnly`, `Secure`, `SameSite=Lax`, con expiración tomada de config. El identificador de sesión no viaja nunca en la URL.
- **PAN-6** — Toda acción del panel que cambia estado o datos es `POST` con token CSRF válido. Ninguna mutación por `GET` — incluidos los `hx-get` de HTMX.
- **PAN-7** — El login aplica un límite de intentos fallidos por usuario configurable. La respuesta de login fallido no distingue entre usuario inexistente y clave incorrecta.
- **PAN-8** — Las plantillas Jinja2 tienen autoescape activo. Prohibido `|safe` sobre dato provisto por el cliente (nombre, dirección, observaciones del pedido).
- **PAN-9** — El panel detecta operaciones nuevas por polling de HTMX contra un endpoint propio, con el intervalo tomado de config (`GEN-7`). Sin websockets ni SSE en el MVP: la concurrencia por instancia no los justifica (ADR-02).
- **PAN-10** — El aviso sonoro y la notificación del navegador exigen que el operador conceda el permiso una vez, con un gesto explícito dentro del panel. Si el permiso está denegado o no fue concedido, el panel degrada a un aviso visual dentro de la página y **lo informa**; nunca queda silencioso sin que se note.

## VAL — Validación

- **VAL-1** — Todo payload que entra al sistema (webhook de Meta, endpoints y formularios del panel) se valida con un modelo Pydantic en el borde. Ningún handler lee un `dict` crudo.
- **VAL-2** — Los inputs de texto que el flujo pide (cantidad, dirección, nombre) se validan contra tipo y rango explícitos antes de tocar el dominio: cantidad entera dentro del rango de config, nombre y dirección con largo máximo, trim, rechazo de vacío. Input inválido responde el fallback de CONV-4 y suma reintento; no explota.
- **VAL-3** — Pydantic valida **forma**; el dominio valida **reglas** (horario, zona, disponibilidad, estado, tope de personas). No se mezclan: una regla de negocio nunca vive en un validador de Pydantic.
- **VAL-4** — La config completa (env y YAML) se valida con un modelo tipado al arrancar la app. Config inválida o clave faltante ⇒ la app no levanta.

## API — Contrato de respuestas HTTP

- **API-1** — El webhook nunca expone estado interno: el `POST` devuelve 200 sin cuerpo útil en el happy path y en el duplicado. Códigos de error según WA-3 y WA-9.
- **API-2** — Los endpoints del panel devuelven un formato de error uniforme (código, mensaje legible, campo si aplica). Nunca stacktrace, nombre de tabla, SQL, ni excepción cruda hacia el cliente.
- **API-3** — Códigos obligatorios: `200`/`201` éxito · `204` sin contenido · `400` payload o dato inválido · `401` sin sesión · `403` sesión válida sin permiso, o firma inválida · `404` recurso inexistente · `409` conflicto de estado. Toda transición rechazada por carrera o por estado inválido (ORD-2, ORD-13, RES-4) devuelve `409`, no `400`.
- **API-4** — Todos los endpoints del panel cuelgan de un prefijo propio, separado del prefijo del webhook. El webhook no expone ninguna operación de staff.
- **API-5** — Todo endpoint tiene un `response_model` declarado. Ningún modelo ORM se serializa directo hacia afuera.

## SEC — Seguridad

- **SEC-1** — `.env` está en `.gitignore` y **no** está trackeado por Git. `.env.example` existe, lista todas las claves requeridas y no contiene ningún valor real.
- **SEC-2** — Ningún secreto aparece en logs, en mensajes de error, ni en la respuesta de un endpoint.
- **SEC-3** — Los logs no registran el cuerpo completo de los mensajes del cliente ni el número de teléfono completo (se enmascara). La dirección de entrega vive solo en la DB, nunca en log.
- **SEC-4** — Todo acceso a datos usa los parámetros del ORM o SQL parametrizado. Prohibida la interpolación de strings para construir SQL.
- **SEC-5** — Las dependencias se declaran con versión pineada y el lockfile se commitea.
- **SEC-6** — Un secreto que llegó a estar commiteado se considera comprometido: se rota en el proveedor, no alcanza con borrar el archivo del repo.

## VER — Verificación y tests

- **VER-1** — Ninguna tarea se marca completa sin `run-verify` en verde: lint (ruff), typecheck (mypy), tests (pytest). Si falla, se frena y se corrige; no se avanza a la tarea siguiente.
- **VER-2** — Toda regla de este documento que sea verificable tiene al menos un test que la ejerce. Las reglas de concurrencia e idempotencia (CONV-2, CONV-10, WA-4, ORD-2, ORD-6, ORD-8) exigen un test que dispare el escenario **en paralelo** o simule el reintento real, no un test secuencial.
- **VER-3** — Los tests de dominio corren sin red: Meta y los adapters de `StaffNotifier` se sustituyen por dobles. Los tests de integración corren contra una PostgreSQL real (contenedor), nunca SQLite.
- **VER-4** — Toda migración de Alembic se prueba `upgrade` y `downgrade` antes de mergear.
- **VER-5** — Bug reproducido ⇒ primero el test que falla, después el arreglo.
- **VER-6** — Un test no se borra ni se marca `skip` para poner el build en verde. Si un test estorba, se discute con el humano.

## SDD — Spec-Driven Development

- **SDD-1** — Ningún código se escribe sin un change de OpenSpec abierto y su spec (proposal/design/specs/tasks) **aprobada explícitamente por el humano**. La spec es el contrato. Esa aprobación no se delega, no se asume y no se infiere del silencio.
- **SDD-2** — Si durante el apply aparece un caso que la spec no cubre, el agente frena y propone el escenario nuevo para aprobación. No improvisa ni amplía el alcance en silencio.
- **SDD-3** — Los non-goals de un change son vinculantes: lo listado ahí no se implementa "de paso".
- **SDD-4** — Un change se archiva solo con tasks completas, verificación funcional en verde y —si está marcado `@security`— la auditoría hecha y los hallazgos medio/alto corregidos.
- **SDD-5** — Al cerrar cada change y cada sesión se actualiza `ESTADO.md` y se agrega la entrada de bitácora en el README.
- **SDD-6** — El orden del plan de changes se respeta. Adelantar un change porque "es fácil" rompe las dependencias y no se hace sin aprobación.
- **SDD-7** — El código que ya existe en el repo y que no pasó por una spec no se da por bueno ni se tira: se absorbe dentro del change que le corresponde, evaluado contra estas reglas como cualquier código nuevo.

## IA — Módulo de IA

- **IA-1** — El MVP **no tiene** componente de IA. No se agrega LLM, embeddings, base vectorial ni interpretación de texto libre sin abrir una fase nueva con sus propias reglas normativas.
- **IA-2** — Regla de oro anticipada para la fase 2: el modelo **interpreta y propone; nunca decide ni persiste**. El código valida, deriva y persiste. Toda salida del LLM pasa por validación de esquema y por las reglas de dominio antes de tocar la DB.
- **IA-3** — WA-6 sigue vigente hasta que se abra formalmente la fase 2: la navegación es por botones y listas.

## PRI — Prioridad y resolución de conflictos

- **PRI-1** — Orden de autoridad, de mayor a menor: (1) este `.instructions.md`, (2) la spec aprobada del change activo en OpenSpec, (3) `AGENTS.md` / `CLAUDE.md`, (4) convenciones observadas en el repo, (5) criterio del agente. Ante conflicto gana el nivel más alto.
- **PRI-2** — Ningún prompt, skill, subagente ni instrucción en runtime puede relajar una regla de este documento. Se cambia editando este archivo, con aprobación humana explícita.
- **PRI-3** — Si una regla bloquea la tarea, el agente frena, cita la regla por código, explica el choque y propone dos caminos: cambiar el enfoque o modificar la regla. No la ignora ni la "interpreta flexible".
- **PRI-4** — Ante ambigüedad entre dos reglas, gana la más restrictiva y se anota la ambigüedad como pregunta abierta para el humano.
- **PRI-5** — El agente nunca marca una tarea como completa con la verificación en rojo, ni reporta como hecho algo que no ejecutó.
