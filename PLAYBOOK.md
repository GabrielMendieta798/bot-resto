# PLAYBOOK.md — Prompts del proyecto

Prompts listos para copiar y pegar, en orden. Uno por vez.

## Cómo se usa

- **Los prompts de `/opsx-propose` son largos a propósito.** Más contexto de negocio adentro = mejores escenarios en la spec = menos corregís a mano después. No los recortes.
- **Los de apply y verificación son cortos a propósito.** El trabajo pesado lo hacen las skills y la spec, no el prompt.
- Cada prompt viene con una nota **"Al revisar:"** debajo. Eso es tuyo, no del agente.
- Cada bloque de texto plano es lo que copiás. Lo de afuera es contexto para vos.
- **La revisión humana de la spec (paso 3 de la rutina) no se delega nunca.** Está marcada en cada change, no una sola vez.

## Qué va al repo y qué no

| Al repo (compartido con Gabriel)                     | Local, en `.gitignore`           |
| ---------------------------------------------------- | -------------------------------- |
| `.instructions.md` — las reglas se discuten en el PR | `AGENTS.md`, `CLAUDE.md`         |
| `openspec/` — ahí viven los changes y las specs      | `AI_README.md`, `AI_WORKFLOW.md` |
| Todo el código, tests, CI, config                    | `ESTADO.md`, `PLAYBOOK.md`       |
|                                                      | `.claude/`, `.opencode/`         |

## Estado del repo al arrancar

`GabrielMendieta798/bot-resto`. **Rama de integracion: `develop`.** `main` queda para lo desplegable.

| Ruta                           | Estado                                                                                                                                                                       |
| ------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `backend/app/models/`          | **Los seis modelos escritos**: `customer`, `menu_item`, `order`, `order_item`, `conversation`, `reservation`. Ninguno paso por spec: se absorben change por change (`SDD-7`) |
| `backend/app/core/config.py`   | Settings con una sola clave, `database_url`. No valida YAML (`VAL-4`)                                                                                                        |
| `backend/app/core/database.py` | engine, sessionmaker y `Base`. Con `echo=True` (`DAT-10`)                                                                                                                    |
| `backend/alembic/`             | Inicializado y **sin configurar**: `target_metadata = None` y la URL placeholder de fabrica. Autogenerate produce migraciones vacias sin avisar                              |
| `database.sql`                 | Esquema a mano. Insumo de referencia del change 01, no fuente del esquema (`DAT-6`)                                                                                          |
| `pyproject.toml`               | Deps sin pinear, sin ruff, sin mypy, con `pytest-asyncio` que no corresponde                                                                                                 |
| `.instructions.md`             | Commiteado. El resto del andamiaje, ignorado                                                                                                                                 |

Faltan: `main.py`, tests, docker-compose, CI, y todo lo de WhatsApp, notificacion al staff y panel.

**Bugs activos que los changes tienen que cerrar:** `Conversation.customer` y `Reservation.customer` usan `back_populates` hacia relaciones que `Customer` no tiene (`conversation` y `reservations`); `configure_mappers()` falla en la primera query. Van en los changes 03 y 05.

**La Fase 0 no reestructura nada.** El layout actual (`models/` plano, `core/database.py`) difiere del objetivo de `AGENTS.md` (`domain/<modulo>/`, `db/`). Esa reconciliacion es parte del **change 01**, con spec aprobada. La Fase 0 agrega al lado de lo que hay.

---

# Fase 0 — Setup del entorno (una sola vez)

## P0.1 — Saneamiento y constitución · ✅ YA HECHO A MANO

**Herramienta:** Claude Code, o a mano — son siete operaciones de git.

```
Vamos a sanear el repo e instalar las reglas del proyecto. No implementes ningún caso de uso, no crees modelos, no muevas archivos de lugar.

Tareas, en orden:

1. Sacar .env del tracking con `git rm --cached .env`. Confirmá que .gitignore ya incluye `.env` y que NO excluye `.env.example`. El archivo estaba vacío, así que NO reescribas el historial de git.
2. Renombrar ".env .example" (con espacio en el nombre) a ".env.example".
3. Copiar .instructions.md a la raíz del repo. Este archivo SÍ se commitea: es el contrato que se discute en los PRs.
4. Agregar al .gitignore un bloque para el andamiaje de IA, que NO se sube: AGENTS.md, CLAUDE.md, AI_README.md, AI_WORKFLOW.md, ESTADO.md, PLAYBOOK.md, .claude/ y .opencode/. Poné un comentario arriba del bloque que aclare que son archivos de herramientas de desarrollo, locales.
5. Copiar (sin commitear, quedan ignorados) AGENTS.md, CLAUDE.md, AI_README.md, AI_WORKFLOW.md, ESTADO.md y PLAYBOOK.md a la raíz, y .opencode/HIERARCHY.md.
6. Copiar las skills a .claude/skills/ y espejarlas con contenido IDÉNTICO en .opencode/skills/. Lo mismo con los agentes: .claude/agents/ y .opencode/agents/.
7. NO toques database.sql, ni backend/app/models/, ni backend/app/core/. Todo eso se absorbe en el change 01 (regla SDD-7).

Rama `chore/setup`, un commit por tarea que sea commiteable, y abrí el PR.
```

> **Al revisar:** confirmá que `.env` desapareció de `git ls-files` y que `git status` no lista los archivos de andamiaje. **El punto de control crítico es el 7**: si el agente vio `database.sql` o los modelos vacíos y "de paso" te completó `order.py`, eso es `SDD-1` roto en el primer prompt del proyecto. Revertilo sin negociar.

---

## P0.2 — Toolchain y esqueleto de la app

**Herramienta:** Claude Code. Es el prompt más largo de la Fase 0.

```
Completá el toolchain y el esqueleto de la app. Leé primero .instructions.md, AGENTS.md y .opencode/HIERARCHY.md.

IMPORTANTE, dos límites que no cruzás:
- NO implementes ningún caso de uso.
- NO muevas ni reescribas backend/app/models/ ni backend/app/core/. El layout actual difiere del objetivo de AGENTS.md §4 y esa reconciliación es del change 01. Vos agregás al lado de lo que hay.

Toolchain (pyproject.toml):
1. Migrar a uv. Todas las dependencias con versión pineada (SEC-5) y lockfile commiteado.
2. Sacar pytest-asyncio: el stack es SQLAlchemy sync por DAT-3 y no hay nada async que testear.
3. Agregar ruff (check y format) y mypy en modo estricto.
4. Config de pytest con los markers unit e integration, y testpaths apuntando a las carpetas que vas a crear.

Esqueleto:
5. backend/app/main.py: app FastAPI con lifespan, con el router del webhook y el del panel montados en prefijos separados (API-4), aunque estén vacíos.
6. Health check en GET /health con estado de la app y conectividad con la DB. Sin exponer la cadena de conexión ni versiones internas.
7. Extender backend/app/core/config.py: además de database_url, cargar y validar config/restaurant.yaml y config/messages.yaml. La app NO levanta si falta una clave (VAL-4). Creá los dos YAML con los defaults documentados y un comentario arriba aclarando que los valores finales salen de las 5 preguntas al dueño del local, no de una decisión técnica.
8. En backend/app/core/database.py, pasar el `echo` del engine a config y dejarlo apagado por default (DAT-10).
9. backend/app/core/: jerarquía de excepciones de dominio, y logging estructurado con el enmascarado de número de teléfono de SEC-3.
10. Exception handler global que mapee las excepciones de dominio a los códigos de API-3, con el formato de error uniforme de API-2. Cero stacktrace hacia afuera.
11. Cliente HTTP centralizado en backend/app/integrations/ sobre httpx, con timeouts explícitos, reutilizable después por el adapter de WhatsApp. Sin lógica de WhatsApp todavía.
12. Alembic YA está inicializado en backend/alembic/ pero quedó con los defaults de fábrica y así no sirve. Arreglalo:
    - backend/alembic/env.py tiene target_metadata = None. Apuntalo a Base.metadata importando app.models, para que el autogenerate vea las tablas. Como está hoy, genera migraciones VACIAS y no avisa nada.
    - backend/alembic.ini tiene sqlalchemy.url = driver://user:pass@localhost/dbname, el placeholder de fábrica. Sacá la URL del .ini y que env.py la lea desde las settings, para no commitear nunca la cadena de conexión (GEN-3).
    - NO generes ninguna migración: la primera la crea el change 00, con la tabla de idempotencia.
13. docker-compose.yml con PostgreSQL para desarrollo local.
14. tests/unit/ y tests/integration/ con sus conftest y un test de humo del health check.
15. .env.example completo, con todas las claves que las settings esperan y ningún valor real.

Al terminar corré la skill run-verify y mostrame el resultado. Después abrí el PR.
```

> **Al revisar:** tres cosas concretas. **(a)** Que `backend/app/models/` esté intacto y que no haya ninguna migración de Alembic generada — si hay una, se adelantó al change 01. **(b)** Probalo a mano: borrá una clave del `.env` y levantá la app. Si arranca igual, `VAL-4` no se cumplió y vas a arrastrar config rota en silencio durante diez changes. **(c)** Que mypy esté estricto de verdad y no con `ignore_errors` o media docena de módulos excluidos para que pase; con dos modelos y un `main.py` no hay excusa para excluir nada.

---

## P0.3 — Instalar OpenSpec

**Herramienta:** terminal

```
openspec init
```

Elegí **OpenCode** y **Claude Code**. Al terminar, verificá que `/opsx-propose`, `/opsx-apply` y `/opsx-archive` estén disponibles en las dos.

> **Al revisar:** `openspec init` **escribe en `AGENTS.md` y en `CLAUDE.md`**. Los dos están gitignoreados, así que no vas a ver el cambio en un PR: mirá el diff local antes de seguir. Si te agregó instrucciones que diluyen o contradicen lo que ya tenías, revertí esa parte — `PRI-2` dice que ninguna herramienta relaja una regla. Lo que sí conviene dejar es la referencia a dónde viven los changes. Y confirmá que `openspec/` **no** quedó en el `.gitignore`: esa carpeta se commitea.

---

## P0.4 — CI sobre el Pull Request

**Herramienta:** OpenCode. Es config, no diseño.

```
Creá el workflow de GitHub Actions que corre sobre cada Pull Request a develop y a main. La rama de integración del proyecto es develop.

Los pasos del job van en el mismo orden que la skill run-verify: ruff check, ruff format --check, mypy, pytest unit, pytest integration. Los tests de integración corren contra un service container de PostgreSQL.

Requisitos:
- Python 3.12 y uv, con cache de dependencias.
- El job corta al primer paso rojo; no sigue ejecutando los siguientes.
- Sin secretos reales: la base del CI usa credenciales de test inyectadas como env del job.
- Nada de deploy, nada de publicar imágenes, nada que escriba en develop ni en main.

No toques el código de la app. Solo .github/workflows/.
```

> **Al revisar:** que no haya ni un secreto real en el YAML, y que el job de integración **levante PostgreSQL de verdad** en vez de saltear esos tests si la DB no responde — un CI que skipea integración en silencio es peor que no tener CI. Después, a mano en GitHub: branch protection en `develop` y en `main`, exigiendo el check en verde y una revisión aprobada. Eso no lo puede hacer el agente, y sin eso el CI es decorativo.

---

## P0.5 — Sanity check de governance

**Herramienta:** las dos. Mismo prompt en OpenCode y en Claude Code, y comparás.

```
Sin escribir ni modificar código, respondeme:

1. Listá las skills disponibles y qué hace cada una en una línea.
2. Listá los subagentes y qué herramientas tiene cada uno.
3. Listá los MCP conectados. Confirmá que podés usar postgres y github: probá postgres listando las tablas de la base local, y github listando los PRs abiertos de este repo.
4. Resumime en 5 líneas la jerarquía de autoridad de .opencode/HIERARCHY.md.
5. ¿Qué hacés si te pido implementar algo que rompe una regla de .instructions.md?
6. ¿Qué hacés si run-verify falla dos veces seguidas por la misma causa?
7. ¿Podés empezar a escribir código de un change sin que yo apruebe la spec?
8. ¿Cuáles son los estados válidos de un Order y cuáles son terminales?
```

> **Al revisar:** esto es un test del andamiaje, no una consulta. **La 5 tiene que decir que frena, cita la regla por código y te propone dos caminos** — si contesta algo tipo "lo haría igual, con cuidado", el `.instructions.md` no está entrando en contexto y todo lo que construyas después es humo. **La 6 tiene que decir handoff a Claude Code. La 7 tiene que ser un no rotundo.** La 8 verifica que leyó la tabla de vocabulario: tiene que nombrar los siete estados y marcar `DELIVERED`, `CANCELLED_BY_CUSTOMER` y `CANCELLED_BY_STAFF` como terminales. Si te dice `CANCELLED` a secas, está citando `database.sql` en vez de la constitución. Si una herramienta no ve las skills, el problema es de ubicación de carpetas: revisá el espejado de P0.1.

---

## Cierre de la Fase 0

- [ ] `.env` fuera del tracking, `.env.example` completo
- [ ] `.instructions.md` commiteado; el resto del andamiaje ignorado y `git status` limpio
- [ ] `run-verify` en verde
- [ ] `/health` responde y la DB conecta
- [ ] Las settings revientan con una clave faltante (probado a mano)
- [ ] `backend/app/models/` intacto y sin migraciones generadas
- [ ] OpenSpec instalado en las dos herramientas, con `AGENTS.md` y `CLAUDE.md` revisados post-init
- [ ] CI en verde sobre un PR con base `develop`, y branch protection activa en `develop` y `main`
- [ ] Sanity check pasado en las dos herramientas, incluida la pregunta 8
- [ ] `update-estado` + primera entrada de bitácora en el README

---

# Fase C.1 — Un change por vez

## Change 00 — `walking-skeleton`

**Complejidad:** alta · **Criticidad:** sensible · **Apply en:** Claude Code · **Audita:** `@security`

Va primero a propósito. Lo más incierto de todo el proyecto es la frontera con Meta: firma, idempotencia y el viaje de ida y vuelta por la Cloud API. Eso se ataca ahora, no a la mitad del proyecto con cinco changes encima.

### Prompt de propuesta

```
/opsx-propose Quiero el change "00-walking-skeleton". No cubre un caso de uso completo: es la rebanada vertical más fina que atraviesa todas las capas, desde que Meta golpea el webhook hasta que el cliente recibe una respuesta por WhatsApp, pasando por la base de datos. Lo que se prueba acá no es negocio, es que la frontera con Meta funciona y es segura.

Contexto de negocio: el restaurante recibe pedidos por WhatsApp. Meta reenvía eventos cuando no recibe un 200 a tiempo, y reenvía bastante. Si un reenvío se procesa dos veces, más adelante eso significa dos pedidos idénticos para la misma persona, que la cocina prepara dos veces y que alguien tiene que cancelar a mano. Por eso la idempotencia del webhook no es hardening opcional, es red de seguridad desde el primer día. Y como el endpoint es público, cualquiera que descubra la URL puede inyectar mensajes falsos si la firma no se valida bien.

Alcance backend:
- GET del webhook: endpoint de verificación de Meta. Compara el verify token y devuelve hub.challenge solo si coincide.
- POST del webhook: valida la firma X-Hub-Signature-256 (HMAC-SHA256 con el app secret) ANTES de procesar nada. La firma se calcula sobre el cuerpo crudo de la request tal como llegó, no sobre el JSON re-serializado.
- Tabla de eventos procesados con message_id como clave. Es la primera migración de Alembic del proyecto y la única tabla de este change.
- INSERT ... ON CONFLICT DO NOTHING por message_id antes de cualquier efecto. Si ya existía, responde 200 y corta sin re-procesar.
- Respuesta al cliente por la Cloud API con un texto fijo, para probar la pata de salida. El envío vive solo en integrations/whatsapp/ y sale DESPUÉS del commit. Decidí en el design si conviene PyWa o el cliente httpx centralizado, y justificá la elección.
- Parseo del payload de Meta con un modelo Pydantic en el borde, tolerante a los eventos que no son mensajes entrantes (status updates, delivery receipts): esos se descartan sin efecto.

Alcance frontend: ninguno. Este change no toca el panel.

Escenarios que las specs deben cubrir como mínimo, con código de estado explícito:
1. GET de verificación con verify token correcto -> 200 y el hub.challenge en el cuerpo, como texto plano.
2. GET de verificación con verify token incorrecto -> 403, sin devolver el challenge.
3. POST con firma válida y message_id nuevo -> 200, queda una fila en la tabla de eventos procesados, y sale exactamente un mensaje al cliente.
4. POST con firma inválida -> 403. Ninguna fila, ningún envío, ningún log del contenido del mensaje.
5. POST sin el header de firma -> 403.
6. La firma se valida contra el cuerpo crudo: un test que firme el cuerpo original y lo compare contra el resultado de re-serializar el JSON tiene que demostrar que el segundo NO valida. Este escenario existe porque re-serializar antes de firmar es el error más común de esta integración y no se nota hasta producción.
7. POST con message_id ya procesado, en secuencia -> 200, sigue habiendo una sola fila, y NO se reenvía el mensaje al cliente.
8. ESCENARIO CRÍTICO, va como escenario propio: dos POST concurrentes con el MISMO message_id. Exactamente una fila en la tabla, exactamente un envío al cliente, y las dos requests responden 200. El test tiene que disparar las dos en paralelo con conexiones separadas, no en secuencia.
9. El procesamiento falla después del INSERT de idempotencia -> la transacción revierte entera, la marca de idempotencia desaparece con ella, NO sale ningún mensaje, y el webhook responde 5xx para que Meta reintente. Un reintento posterior con el mismo message_id se procesa normalmente.
10. POST con un payload que no es un mensaje entrante (status update o delivery receipt) -> 200 y corte, sin fila y sin envío.
11. El envío por la Cloud API falla con error de red o 5xx -> la transacción ya commiteó, así que el fallo se loguea y no revierte nada. El webhook igual responde 200.

Non-goals, no entra nada de esto:
- Máquina de estados de conversación, comandos globales, fallback ni reintentos.
- Ningún modelo ni tabla de dominio: Customer, MenuItem, Order, OrderItem, Conversation, Reservation. Los modelos que ya existen en backend/app/models/ NO se tocan en este change.
- messages.yaml, guión de conversación ni ningún texto configurable: el texto de respuesta es fijo y queda documentado como deuda del change 04.
- Botones, listas ni intenciones de respuesta abstractas.
- StaffNotifier, eventos de dominio y notificación al staff.
- Panel, login y cualquier endpoint de staff.
- Scheduler y timeouts.

Restricciones: .instructions.md §WA-3, §WA-4, §WA-9, §CONV-9, §CONV-10, §GEN-3, §GEN-6, §DAT-1, §DAT-3, §DAT-6, §VAL-1, §API-1, §API-3, §SEC-1, §SEC-2, §SEC-3, §SEC-4, §VER-1, §VER-2, §VER-3, §VER-4.
```

### 🛑 Al revisar la spec — ANTES de implementar

Esto no se delega. Cinco cosas que tenés que ver escritas en `design.md` y en `specs/`, y si falta alguna la spec vuelve:

1. **Que la firma se valide contra el cuerpo crudo.** Si el design dice "se valida la firma del payload" sin aclarar que es sobre los bytes tal como llegaron, exigilo explícito. Este es el bug que más caro sale en esta integración: anda en todos los tests que vos escribas y falla contra Meta en producción, porque el orden de las claves y los espacios cambian al re-serializar.
2. **Que use `hmac.compare_digest` y no `==`.** Comparar strings de firma con `==` filtra información por tiempo de ejecución. `WA-3` lo pide y el `@security` lo va a marcar como alto.
3. **Que el `INSERT` de idempotencia y el procesamiento estén en la MISMA transacción, y el envío DESPUÉS del commit.** Si el design los separa en dos transacciones, la marca de idempotencia sobrevive a un procesamiento fallido y el reintento de Meta queda bloqueado para siempre: ese mensaje se pierde y nadie se entera. Es `CONV-10` y es el punto más sutil de todo el change.
4. **Que el escenario 8 tenga un test en paralelo de verdad**, con dos conexiones y dos threads. Si `tasks.md` lo resuelve con dos llamadas seguidas en el mismo test, no está probando la carrera: está probando el escenario 7 otra vez.
5. **Que no haya aparecido ni un modelo de dominio.** La tentación es enorme, porque `Customer` y `MenuItem` ya están escritos en el repo y "total ya están". Si la spec los toca, o genera una migración que los incluya, volvé al propose: son del change 01 y este change no los necesita para nada.

### Ruteo y regla de escape

**Apply en Claude Code.** Complejidad alta y criticidad sensible: acá hay HMAC, transacciones, `ON CONFLICT` y una carrera real. El propose es barato en cualquiera de las dos, pero el apply no.

Si igual lo arrancás en OpenCode y `run-verify` falla 2 o 3 veces por la misma causa, **handoff a Claude Code** con la plantilla de `AI_WORKFLOW.md` §3, revirtiendo antes lo que quedó a medias.

### Después de esto

No te tiro el prompt de `/opsx-apply` todavía. Primero revisás la spec con los cinco puntos de arriba. El apply viene después, y es corto: el trabajo pesado ya está en la spec.

---

## Change 01 — `cimientos-datos`

**CU-03 / 17 / 18** · Complejidad media · Criticidad normal · **Apply en OpenCode** · sin auditoría

Es el change que absorbe lo que ya está escrito en el repo (`SDD-7`) y lo alinea con la estructura objetivo.

```
/opsx-propose Quiero el change "01-cimientos-datos" que cubre UC-03 (ver menú por categorías), UC-17 (marcar item agotado o disponible) y UC-18 (editar menú, precios y tiempos) en su capa de datos y de servicios. Las pantallas de staff para UC-17 y UC-18 son del change 08: acá va el dominio que esas pantallas van a usar.

Contexto de negocio: el menú de un restaurante de pastas y parrilla cambia todos los días. Se acaba la bondiola a las nueve de la noche y hay que sacarla de la carta en diez segundos, no borrarla: mañana vuelve. Los precios se actualizan seguido por inflación, y un pedido que se confirmó ayer a un precio no puede cambiar de monto porque hoy se actualizó la lista. Cada item tiene un tiempo estimado de preparación distinto, y de ahí sale después el ETA que se le promete al cliente.

Situación del repo: ya existen, escritos a mano y sin pasar por ninguna spec, los modelos customer.py, menu_item.py, order.py y order_item.py, sin repositorios, sin servicios y sin migración; conversation.py y reservation.py están vacíos; backend/app/core/database.py tiene el engine y la Base; y hay un database.sql en la raíz con el esquema pensado a mano. Este change absorbe SOLO customers y menu, y los evalúa contra las reglas como si fueran código nuevo, según SDD-7. Order y OrderItem quedan donde están, sin tocar, hasta el change 02.

Hay dos bugs conocidos en ese código que este change tiene que arreglar en la parte que le toca: backend/app/models/__init__.py declara Order y OrderItem en __all__ sin importarlos, y Order.customer usa back_populates hacia una relación "orders" que no existe en Customer, lo que hace fallar configure_mappers en la primera query. Arreglá el __init__ solo para lo que este change absorbe; el de Order y OrderItem es del change 02.

Alcance backend:
- Reconciliar la estructura hacia el layout de AGENTS.md §4: módulos de dominio con models, repository, service y schemas. Los modelos existentes se mueven, no se reescriben desde cero si ya cumplen las reglas.
- Módulos de dominio customers y menu completos, cada uno con su capa de repositorio. El servicio nunca recibe una Session.
- Primera migración de Alembic del dominio, con customers y menu_items Y NADA MÁS. Si el autogenerate trae orders u order_items porque quedaron registrados en Base.metadata, se recortan a mano de la migración: esas tablas son del change 02 y no pasaron por spec. Cuando la migración esté verde, database.sql se borra del repo: el esquema pasa a vivir solo en las migraciones.
- Servicios de menú: listar categorías, listar items disponibles de una categoría, togglear disponibilidad, editar nombre, descripción, precio y tiempo estimado.
- Servicio de customers: obtener o crear por número de teléfono.

Alcance frontend: ninguno. Este change no toca el panel ni el flujo de WhatsApp.

Escenarios que las specs deben cubrir como mínimo, con código de estado explícito donde haya endpoint:
1. Listar categorías devuelve solo las categorías que tienen al menos un item disponible.
2. Listar items de una categoría devuelve nombre, precio y tiempo estimado, y NO incluye los items con available en false.
3. Togglear un item a no disponible: el item sigue existiendo en la base, solo cambia el booleano. Un borrado físico es un fallo del escenario.
4. Togglear de vuelta a disponible lo devuelve al listado.
5. Editar el precio de un item persiste el precio nuevo y no altera ningún dato histórico.
6. Un precio negativo se rechaza. Un tiempo estimado negativo se rechaza.
7. Obtener o crear customer por teléfono: la primera vez crea, la segunda devuelve el mismo registro. Dos llamadas concurrentes con el mismo teléfono no crean dos customers: se prueba con el índice único y test en paralelo.
8. Todo importe leído desde la base vuelve como Decimal, nunca como float.
9. Todo timestamp vuelve con zona horaria. Un datetime naive es un fallo del escenario.
10. La migración corre upgrade y downgrade limpio, en ese orden y de vuelta.
11. ESCENARIO PROPIO: la migración inicial crea exactamente dos tablas, customers y menu_items. Un test inspecciona el esquema después del upgrade y falla si aparece orders u order_items.

Non-goals:
- Endpoints de staff y cualquier pantalla del panel: son del change 08.
- El guión de WhatsApp que muestra el menú al cliente: es del change 04.
- Order, OrderItem, Conversation y Reservation, y sus tablas: son de los changes 02, 03 y 05. Los archivos order.py y order_item.py ya existen en el repo y NO se tocan en este change.
- Cualquier cambio en el webhook del change 00.

Restricciones: .instructions.md §GEN-1, §GEN-2, §GEN-6, §GEN-9, §DAT-1, §DAT-2, §DAT-3, §DAT-5, §DAT-6, §DAT-8, §DAT-10, §VAL-1, §VAL-3, §VAL-4, §API-5, §SEC-4, §VER-1, §VER-3, §VER-4, §SDD-7.
```

### 🛑 Al revisar la spec

- **Que el `service` no reciba nunca una `Session`.** Es el desvío más frecuente y el más cómodo: el agente necesita una consulta que el repositorio no expone y en vez de agregar el método, le pasa la sesión. `DAT-2` muerto en el primer módulo, y todos los módulos que siguen copian el patrón.
- **Que `database.sql` se borre en este change**, no "más adelante". Dos fuentes del esquema conviviendo es la garantía de que en dos semanas divergen y nadie sabe cuál manda.
- **Que la migración inicial incorpore lo que a `database.sql` le falta.** Lo tenés listado en `ESTADO.md` D-3: para este change aplican `subtotal`/`delivery_fee` y el resto quedan para sus changes. Si la migración es una traducción literal del `.sql`, arrastraste los ocho huecos.
- **Que el escenario 7 tenga índice único en la DB**, no un `if not exists` en el servicio.

---

## Change 02 — `pedidos-core`

**CU-04 / 07 / 09 / 19** · Complejidad alta · Criticidad sensible · **Apply en Claude Code** · audita `@security`

```
/opsx-propose Quiero el change "02-pedidos-core" que cubre UC-04 (armar pedido), UC-07 (confirmar pedido), UC-09 (cancelar pedido pre-preparación) y UC-19 (cancelar o marcar fallido desde el staff), en su capa de dominio.

Contexto de negocio: este es el corazón del sistema y donde está la plata. Un cliente arma su pedido, lo confirma, y en ese momento el restaurante se compromete. Hay una ventana corta donde el cliente todavía puede arrepentirse: mientras el pedido está recibido y nadie lo empezó a cocinar. En cuanto la cocina lo toma, esa ventana se cierra. Y ahí está la carrera real del negocio: el cliente aprieta cancelar en el mismo segundo en que el cocinero aprieta empezar. Si los dos ganan, la cocina prepara comida que nadie va a pagar, o peor, el cliente cree que canceló y le llega el delivery igual. Uno de los dos tiene que perder, siempre, y el que pierde tiene que enterarse.

El otro punto delicado es el precio. Los precios del menú cambian seguido por inflación. Un pedido confirmado ayer no puede cambiar de monto porque hoy se actualizó la lista: lo que se cobra es lo que el cliente vio cuando confirmó.

Situación del repo: backend/app/models/order.py y order_item.py ya existen, escritos a mano y sin spec. Lo que está bien se conserva y lo que falta se completa, según SDD-7. Lo que ya cumple: unit_price_snapshot en OrderItem, Numeric(12,2) en los montos, DateTime con zona, CheckConstraints reales en la base, y el cascade entre Order y OrderItem. Lo que le falta, y este change tiene que resolver:
- Order tiene solo total: faltan subtotal y delivery_fee como campos separados.
- El CheckConstraint de status tiene un CANCELLED único: faltan CANCELLED_BY_CUSTOMER y CANCELLED_BY_STAFF como estados distintos.
- No existe cancel_reason.
- Solo hay created_at: ninguna transición registra su propio timestamp.
- Falta el índice único parcial que impide más de un pedido no terminal por cliente.
- No hay constraint que impida ON_THE_WAY en un pedido de retiro.
- status y delivery_type son String pelados: en Python nada impide asignar un valor inválido. Quiero StrEnum en Python ADEMÁS del CheckConstraint en la base, no en lugar de.
- backend/app/models/__init__.py declara Order y OrderItem en __all__ pero no los importa, así que Base.metadata no los registra y el autogenerate de Alembic no los ve.
- Order.customer usa back_populates hacia una relación "orders" que Customer no tiene: configure_mappers falla en la primera query.

Alcance backend:
- Módulo de dominio orders con models, repository, service y schemas, siguiendo la estructura del change 01.
- Order y OrderItem completos, con el precio unitario congelado en cada línea al confirmar y con todo lo que falta de la lista de arriba.
- Order separa subtotal, costo de envío y total en campos distintos.
- Máquina de estados del pedido con sus siete estados y sus transiciones válidas declaradas de forma explícita, no como condicionales sueltos.
- Guard de concurrencia para la cancelación del cliente.
- Cancelación por staff desde estados avanzados, con motivo obligatorio.
- Carrito en memoria de dominio: agregar línea, restar cantidad, quitar línea. Restar hasta cero elimina la línea. El carrito NO se persiste como Order hasta la confirmación.
- Cálculo de ETA a partir del tiempo estimado del item más lento.
- Migración de Alembic con orders, order_items, sus constraints, sus índices y el índice único parcial que impide más de un pedido no terminal por cliente.

Alcance frontend: ninguno.

Escenarios que las specs deben cubrir como mínimo, con código de estado explícito:
1. Confirmar un pedido crea el Order y sus líneas en una sola transacción, con el precio unitario congelado en cada línea -> 201.
2. Editar el precio de un item del menú DESPUÉS de confirmar no altera el total del pedido ya confirmado. El test compara el total antes y después de tocar el menú.
3. Restar cantidad hasta cero elimina la línea del carrito. Restar cantidad en un pedido ya confirmado -> 409.
4. ESCENARIO CRÍTICO, va como escenario propio: el cliente cancela y el staff pasa a preparación al mismo tiempo. Exactamente uno gana. Si gana el staff, la cancelación devuelve 409 y el pedido queda en preparación. Si gana el cliente, el pedido queda cancelado y el cambio del staff devuelve 409. El test dispara las dos operaciones en paralelo, con conexiones separadas.
5. ESCENARIO CRÍTICO, va como escenario propio: dos confirmaciones concurrentes del mismo cliente. Se crea exactamente un Order; la segunda falla contra el índice único parcial. Test en paralelo.
6. Cancelar un pedido que ya está en preparación -> 409 con un mensaje que le explica al cliente por qué no se pudo.
7. El staff cancela sin indicar motivo -> 400. Con motivo -> 200, y el motivo queda persistido y disponible para el aviso al cliente.
8. Marcar en camino un pedido de retiro -> 409. Un retiro va de listo a entregado directo.
9. Cualquier transición saliente desde un estado terminal -> 409.
10. Una transición que no existe en la máquina de estados -> 409, y queda registrada. Nunca se aplica en silencio.
11. Cada transición aplicada deja su timestamp. Un estado sin timestamp de transición es un fallo del escenario.
12. El ETA de un carrito con tres items devuelve el tiempo del más lento, no la suma.
13. Confirmar un pedido que incluye un item que dejó de estar disponible entre el armado y la confirmación -> 409, con el item identificado, y el pedido no se crea.
14. El subtotal, el costo de envío y el total son campos separados y consistentes entre sí.
15. ESCENARIO PROPIO: asignar un estado que no está en el vocabulario falla, tanto desde Python (StrEnum) como desde la base (CheckConstraint). Un test lo prueba por los dos caminos.
16. Importar app.models expone Customer, MenuItem, Order y OrderItem, y Base.metadata registra las cuatro tablas. Un test lo verifica.
17. Una query que cargue un Order con su Customer y sus items no falla en configure_mappers. Es el bug de back_populates que hay hoy.

Non-goals:
- Cualquier cosa de WhatsApp: adapter, botones, intenciones, textos. Son del change 04.
- La máquina de estados de conversación y el lock de Conversation: son del change 03.
- Validación de horario del local y de zona de delivery: son del change 07. Acá se deja el punto de extensión, no la regla.
- StaffNotifier y avisos: son del change 06.
- Panel y endpoints de staff: son del change 08.

Restricciones: .instructions.md §Vocabulario de estados, §GEN-1, §GEN-2, §GEN-4, §GEN-6, §DAT-2, §DAT-4, §DAT-7, §DAT-8, §DAT-9, §CONV-7, §CONV-9, §ORD-1 a §ORD-13, §VAL-3, §API-3, §VER-1, §VER-2, §VER-3, §VER-4.
```

### 🛑 Al revisar la spec

- **Exigí update condicional atómico, no `SELECT` y después `UPDATE`.** Este es EL punto de control de este change. Si el `design.md` describe "se lee el estado, se verifica que sea `RECEIVED`, y se actualiza", la carrera sigue abierta entre las dos operaciones y el escenario 4 va a pasar por casualidad en los tests y a fallar en producción un viernes a las nueve de la noche. Tiene que ser un `UPDATE ... WHERE status = 'RECEIVED'` que devuelve filas afectadas, o un `SELECT ... FOR UPDATE` que mantiene el lock hasta el commit. Las dos sirven; leer y después escribir sin lock, no.
- **Que el índice único parcial esté en la migración**, escrito a mano. Alembic no lo autogenera.
- **Que el escenario 2 compare totales**, no que "el snapshot existe". La regla es que el total no se mueve; probalo moviendo el precio.
- **Que los escenarios 4 y 5 estén en `tasks.md` como tests en paralelo con conexiones separadas.** Si aparecen como dos llamadas seguidas, no prueban nada.

---

## Change 03 — `conversacion`

**CU-01 / 12** · Complejidad alta · Criticidad sensible · **Apply en Claude Code** · audita `@security`

```
/opsx-propose Quiero el change "03-conversacion" que cubre UC-01 (iniciar conversación y menú principal) y UC-12 (expirar carrito y resetear sesión).

Contexto de negocio: la gente escribe por WhatsApp como habla. Manda tres mensajes seguidos en vez de uno, aprieta un botón dos veces porque no vio que ya había respondido, abandona el pedido a la mitad y vuelve cuarenta minutos después esperando encontrarlo, o se pierde y escribe "menú" para volver a empezar. El bot tiene que sobrevivir a todo eso sin perder el hilo ni mezclar estados. Y sobre todo: los tres mensajes seguidos de la misma persona se tienen que procesar en orden, uno atrás del otro, porque si se procesan a la vez el carrito queda inconsistente. Pero eso no puede frenar a los demás: si hay quince personas pidiendo al mismo tiempo un viernes, cada una va por su lado.

El carrito abandonado es el otro caso real: alguien arma medio pedido, se distrae, y vuelve dos horas después. Ese carrito ya no vale. Se avisa, se descarta y se vuelve al menú principal.

Alcance backend:
- Módulo de dominio conversations con models, repository, service y schemas.
- Conversation con su estado, el flujo activo, las referencias al pedido y a la reserva en curso, el contador de reintentos, la marca de última interacción y el carrito.
- Router implementado como tabla de transiciones explícita. Un if/elif anidado es un rechazo del change.
- Serialización por número: cada mensaje entrante se procesa bajo lock pesimista de la fila de la conversación de ese cliente.
- Los tres comandos globales, disponibles desde cualquier estado de flujo.
- Fallback con contador de reintentos y derivación a handoff al superar el límite de config.
- Jobs de scheduler para el aviso de inactividad y el reset de sesión, con los timeouts de config.
- Enganche con el webhook del change 00: el mensaje entrante ya deduplicado entra al router.
- Migración de Alembic con conversations.

Alcance frontend: ninguno.

Escenarios que las specs deben cubrir como mínimo:
1. Primer mensaje de un número desconocido crea la conversación y devuelve el menú principal.
2. Mensaje de un número conocido recupera la conversación en el estado donde había quedado.
3. ESCENARIO CRÍTICO, va como escenario propio: tres mensajes del MISMO número llegan a la vez. Se procesan uno después del otro, en orden, y el estado final es el que corresponde a la secuencia. El test los dispara en paralelo con conexiones separadas.
4. ESCENARIO CRÍTICO: mensajes de DOS números distintos llegan a la vez y no se bloquean entre sí. El test tiene que demostrar que el segundo no espera al primero.
5. Los tres comandos globales funcionan desde cualquier estado de flujo, no solo desde el menú. Un test por comando y por estado no trivial.
6. "menú" o "cancelar" en medio de un pedido a medio armar descarta el flujo y el carrito, y vuelve al menú principal.
7. "atrás" desde el segundo paso de un flujo vuelve al primero. "atrás" desde el primer paso vuelve al menú principal.
8. Un input no reconocido responde el fallback y suma un reintento, sin cambiar de estado.
9. Superado el límite de reintentos configurado, la conversación pasa a handoff. El límite sale de config: el test lo cambia y el comportamiento cambia con él.
10. El carrito vive en la fila de la conversación, no en memoria del proceso. Reiniciar la app y volver a mandar un mensaje encuentra el carrito intacto.
11. Pasado el timeout de inactividad, el job avisa una sola vez. Correr el job dos veces no manda dos avisos.
12. Pasado el timeout de reset, el carrito se descarta y la conversación vuelve al menú principal.
13. El orden de adquisición de locks respeta el del documento: idempotencia primero, conversación después, resto al final. Un test de dos flujos cruzados no debe producir deadlock.
14. Al cerrar el post-pedido o el post-reserva, las referencias al pedido y a la reserva en curso quedan en null.

Non-goals:
- El guión concreto del pedido y de la reserva: son de los changes 04 y 05.
- Botones, listas, intenciones abstractas y traducción a PyWa: es del change 04.
- messages.yaml completo: acá solo las claves que el menú principal y el fallback necesitan.
- Handoff y des-handoff completos: la transición a handoff sí entra, la operatoria del staff es del change 07.
- Reservas y notificación al staff.

Restricciones: .instructions.md §Vocabulario de estados, §GEN-1, §GEN-4, §GEN-6, §GEN-7, §GEN-8, §DAT-1, §DAT-2, §DAT-3, §CONV-1 a §CONV-10, §TXT-1, §TXT-3, §VAL-2, §VER-1, §VER-2, §VER-3.
```

### 🛑 Al revisar la spec

- **Que el router sea una tabla de transiciones de verdad.** Si el `design.md` dice "máquina de estados" pero `tasks.md` describe un método `handle_message` con ramas por estado, es lo mismo que prohíbe `CONV-1` con otro nombre. Pedí ver la estructura de datos: un dict, una tabla, un registro de transiciones. Algo que se pueda listar y testear sin ejecutar el flujo.
- **Que el lock sea sobre la fila, no sobre la tabla.** El escenario 4 existe para eso. Si el agente resuelve la serialización con un lock de tabla o un mutex de aplicación, un viernes con quince pedidos simultáneos el bot se convierte en una fila de un solo carril.
- **Que el escenario 11 esté cubierto de verdad** (`GEN-8` y `RES-10` comparten esta idea). Un job que avisa dos veces no es un bug menor: es el cliente recibiendo dos WhatsApp idénticos y perdiendo confianza en el bot.
- **Que el carrito sea `JSONB` en la fila de la conversación.** Si queda en una tabla aparte, el lock de `CONV-2` deja de cubrirlo y abriste una carrera nueva sin querer.

---

## Change 04 — `flujo-pedido-wa`

**CU-04 a CU-08** · Complejidad alta · Criticidad normal · **Apply en Claude Code** · sin auditoría

```
/opsx-propose Quiero el change "04-flujo-pedido-wa" que cubre UC-04 (armar pedido), UC-05 (modificar), UC-06 (datos de entrega), UC-07 (confirmar) y UC-08 (consultar estado) del lado de la conversación por WhatsApp.

Contexto de negocio: acá es donde el cliente realmente vive el bot. Todo lo que construimos en los changes anteriores es invisible para él; esto es lo único que ve. Y lo que ve tiene que ser rápido de usar con una mano, parado en la calle, con mala señal: botones, no párrafos. Elegir categoría, elegir plato, decir cuántos, aclarar si va sin sal, agregar otro o ir al total.

La redacción de cada mensaje es del dueño del local, no nuestra. Él va a querer cambiar un emoji, poner "che" en vez de "hola", ajustar cómo se pide la dirección. Eso tiene que ser editar un archivo de texto y listo, sin tocar código ni volver a desplegar.

Alcance backend:
- Adapter de WhatsApp en integrations/whatsapp/: recibe la intención de respuesta abstracta que devuelve el dominio y la traduce a botones o listas de la Cloud API. Es el ÚNICO lugar del sistema que conoce PyWa.
- Catálogo de intenciones de respuesta abstractas en el dominio de conversación.
- Estados nuevos de la máquina de conversación para el flujo completo de pedido, con sus transiciones.
- messages.yaml completo para el flujo de pedido, con claves en inglés y textos en castellano rioplatense.
- Consulta de estado del pedido en curso.

Alcance frontend: ninguno.

Escenarios que las specs deben cubrir como mínimo:
1. El dominio devuelve una intención abstracta y nunca un objeto de PyWa. Un test verifica que el módulo de conversación no importa PyWa ni nada de integrations.
2. Una respuesta con 3 opciones o menos se envía como botones.
3. Una respuesta con 4 opciones se envía como lista.
4. Una respuesta con más de 10 opciones se pagina según lo que defina el design: la Cloud API no acepta más de 10 filas. Este escenario existe porque el menú de un restaurante de pastas y parrilla tranquilamente supera las 10 opciones en una categoría.
5. El flujo completo del pedido de punta a punta: categoría, item, cantidad, observaciones, agregar otro, ver carrito, datos de entrega, resumen con total, confirmación.
6. La cantidad se pide como texto y se valida: un número fuera de rango o algo que no es número responde el fallback y suma reintento, sin romper el flujo.
7. Modificar el carrito: sumar una línea, restar cantidad, quitar una línea, y restar hasta cero que elimina la línea.
8. El resumen previo a confirmar muestra subtotal, costo de envío y total como tres líneas distintas, con los valores que se van a persistir.
9. Consultar el estado del pedido devuelve el estado actual traducido a un mensaje del YAML, no el identificador técnico.
10. Ningún texto de cara al cliente está hardcodeado. Un test recorre el código del flujo y falla si encuentra un literal en castellano.
11. Una clave referenciada desde el código que no existe en messages.yaml hace fallar el arranque de la app, no el mensaje al cliente.
12. Las claves pedido_cancelado_staff_push y pedido_estado.cancelado, que faltaban en el guión, existen con su redacción. En nomenclatura inglesa según GEN-9.

Non-goals:
- Reservas: son del change 05.
- Validación de horario del local, zona de delivery e item agotado: son del change 07. Acá se llama al punto de extensión que el change 02 dejó.
- Notificación al staff: es del change 06.
- Panel.
- Interpretación de texto libre para inferir intención: es fase 2 y está prohibida por WA-6.

Restricciones: .instructions.md §GEN-1, §GEN-9, §CONV-1, §CONV-3, §CONV-4, §CONV-7, §CONV-8, §WA-1, §WA-2, §WA-5, §WA-6, §WA-7, §WA-8, §TXT-1, §TXT-2, §TXT-3, §VAL-2, §DAT-7, §DAT-8, §VER-1, §VER-3.
```

### 🛑 Al revisar la spec

- **Que ninguna traducción a PyWa se filtre fuera del adapter.** El escenario 1 tiene que estar como test automático, no como buena intención. Es la regla que protege todo lo demás: el día que entre otro canal o el texto libre de la fase 2, si esto se respetó el núcleo no se toca.
- **Que el escenario 4 tenga una decisión concreta de paginación.** Diez filas es un límite duro de la Cloud API y una categoría de pastas lo pasa fácil. Si la spec dice "se manejará la paginación" sin decir cómo, volvé al propose: eso se descubre en producción con el menú real cargado.
- **Que el escenario 10 sea un test, no un checklist.** "Revisar que no haya literales" no escala; un test que grepea el módulo sí.
- **Que confirmes vos la redacción del YAML.** Los textos son del dueño del local. Lo que escriba el agente es un borrador para que él lo corrija, y conviene que lo sepa desde el día uno.

---

## Change 05 — `reservas`

**CU-R1 a CU-R5** · Complejidad media · Criticidad sensible · **Apply en Claude Code** · audita `@security`

```
/opsx-propose Quiero el change "05-reservas" que cubre UC-R1 (solicitar reserva), UC-R2 (consultar estado), UC-R3 (cancelar), UC-R4 (confirmar o rechazar del lado del staff, en su capa de dominio) y UC-R5 (escalar una reserva sin responder).

Contexto de negocio: el restaurante no tiene un sistema de mesas y no lo va a tener en el MVP. Quién entra y quién no lo decide una persona mirando el salón, no un algoritmo. Entonces el bot toma el pedido de reserva, lo valida contra lo que se puede validar sin conocer el salón (que la fecha sea futura, que el local esté abierto ese día y a esa hora, que no pidan mesa para veinte, que no reserven para dentro de seis meses) y lo deja como solicitado. El staff confirma o rechaza. El sistema NUNCA confirma solo: si lo hiciera, el sábado a la noche aparecerían ocho personas con una reserva que nadie aceptó.

El problema real que trae esto es el silencio. Alguien pide mesa para el viernes, el staff está a full y no lo mira, y el cliente queda esperando sin saber nada. Por eso a las horas configuradas se le avisa que seguimos procesando, y la solicitud se marca como escalada para que el staff la vea arriba de la lista. Escalar no es confirmar ni rechazar: la reserva sigue exactamente en el mismo estado.

Alcance backend:
- Módulo de dominio reservations con models, repository, service y schemas.
- Máquina de estados de la reserva con sus cuatro estados y transiciones válidas.
- Validación de intake completa, antes de crear la solicitud.
- Estados nuevos de la máquina de conversación para el flujo de reserva, con las listas de fecha y hora derivadas de las franjas del YAML.
- Job de escalada con el tiempo de config.
- Envío de la confirmación al cliente por template de utilidad pre-aprobado, con el nombre del template y el mapeo de parámetros en config.
- messages.yaml del flujo de reserva.
- Migración de Alembic con reservations, incluida la marca de escalada.

Alcance frontend: ninguno. Las pantallas de confirmar y rechazar son del change 08.

Escenarios que las specs deben cubrir como mínimo, con código de estado explícito:
1. Solicitud válida crea la reserva en estado solicitado -> 201. El sistema no la confirma ni la rechaza.
2. Fecha en el pasado -> rechazo en el intake, la reserva NO se crea.
3. Fecha y hora fuera del horario del local -> rechazo en el intake. El test incluye el caso de horario partido: una hora que cae en el hueco del mediodía a la tarde se rechaza, y las dos franjas se aceptan.
4. Cantidad de personas por encima del tope configurado -> rechazo en el intake.
5. Fecha más allá de la ventana configurada -> rechazo en el intake.
6. Las opciones de fecha y hora se ofrecen como listas derivadas del YAML. Texto libre para fecha u hora no se acepta: responde el fallback.
7. El cliente cancela una reserva solicitada -> 200, queda cancelada.
8. El cliente cancela una reserva confirmada -> 200, queda cancelada.
9. El cliente intenta cancelar una reserva ya cancelada o rechazada -> 409.
10. El cliente tiene dos reservas no terminales y consulta estado: el bot le ofrece la lista para elegir. Nunca asume la última.
11. ESCENARIO PROPIO: pasado el tiempo configurado, el job de escalada avisa al cliente UNA sola vez y marca la reserva como escalada. El estado NO cambia: sigue solicitada. Correr el job de nuevo no vuelve a avisar ni vuelve a marcar.
12. El staff confirma una reserva -> 200, y el aviso al cliente sale por template de utilidad, no como texto libre.
13. El staff rechaza una reserva -> 200, y el cliente recibe el aviso.
14. El nombre del template y el mapeo de parámetros salen de config. Un test los cambia y el envío cambia con ellos, sin tocar código.
15. Cada transición deja su timestamp.

Non-goals:
- Pantallas del panel para confirmar y rechazar: son del change 08.
- Gestión de mesas, disponibilidad automática y cupos: fuera del MVP por ADR-07.
- Estado de no-show: no existe en el MVP.
- Urgencia diferenciada por cercanía de la reserva: fuera del MVP.
- Notificación al staff: es del change 06.

Restricciones: .instructions.md §Vocabulario de estados, §GEN-4, §GEN-6, §GEN-7, §GEN-8, §DAT-2, §DAT-6, §CONV-1, §CONV-5, §WA-5, §WA-7, §WA-8, §TXT-1, §TXT-3, §RES-1 a §RES-10, §VAL-2, §VAL-3, §API-3, §VER-1, §VER-2, §VER-4.
```

### 🛑 Al revisar la spec

- **Que no exista ningún camino por el que el sistema confirme una reserva solo.** Leé la máquina de estados y buscá cualquier transición automática hacia confirmado: un default, un job, un "si pasa X entonces". `RES-1` es la regla de oro del dominio y la única forma de verificarla es leyendo la tabla de transiciones completa.
- **Que escalar no cambie el estado.** Es la confusión más natural del mundo: "escalada" suena a estado. Es una marca sobre una reserva que sigue solicitada. Si aparece como estado en el enum, volvé al propose.
- **Que el horario partido esté en el escenario 3.** Un restaurante de pastas y parrilla cierra a la tarde. Si el validador solo mira "entre apertura y cierre", acepta reservas para las cinco de la tarde con el local cerrado.
- **Que el template esté en config y no en `messages.yaml`.** Es `WA-8`, y es el punto donde se mezclan las dos cosas más seguido. Además, verificá vos el CP-3: la política de templates de Meta cambia el 1 de octubre y conviene que confirmes la vigente antes de aprobar esta spec.

---

## Change 06 — `notificacion-staff`

**CU-11** · Complejidad media · Criticidad normal · **Apply en OpenCode** · sin auditoría

```
/opsx-propose Quiero el change "06-notificacion-staff" que cubre UC-11 (persistir la operación y avisar al staff).

Contexto de negocio: cuando entra un pedido, alguien en la cocina se tiene que enterar en el momento. Hoy el único canal es el propio panel, que va a estar abierto en una tablet o una compu en la cocina. Nada de WhatsApp, Telegram, mail ni SMS: no queremos acoplar la operación interna del restaurante a la política de precios de Meta ni sumar un costo por mensaje. Pero el día que eso cambie, sumar un canal tiene que ser escribir una clase, no reabrir el dominio.

De eso se trata este change: el dominio emite un evento y se olvida. Un adapter lo recoge. Hoy ese adapter deja la notificación en la base para que el panel la levante. Mañana puede haber dos adapters activos a la vez y el dominio ni se entera.

Y hay una cosa que importa más de lo que parece: una notificación que ya vio el staff no puede volver a sonar. Si la tablet de la cocina suena cada diez segundos por el mismo pedido, a la media hora le bajan el volumen y el sistema deja de servir.

Alcance backend:
- Interfaz StaffNotifier en el módulo de notificaciones, con su registro de adapters.
- Eventos de dominio para pedido recibido y reserva solicitada, emitidos desde los servicios de los changes 02 y 05 contra la interfaz.
- Adapter que persiste la notificación como fila pendiente, con su marca de vista.
- Migración de Alembic con la tabla de notificaciones.
- Enganche: los servicios de pedido y de reserva emiten el evento DESPUÉS del commit de la operación.

Alcance frontend: ninguno. El endpoint de polling y el aviso en el navegador son del change 08.

Escenarios que las specs deben cubrir como mínimo:
1. Confirmar un pedido emite el evento correspondiente contra StaffNotifier, y queda una notificación pendiente.
2. Crear una solicitud de reserva emite su evento y deja su notificación pendiente.
3. Un test verifica que los módulos de dominio NO importan ningún adapter concreto: solo la interfaz.
4. ESCENARIO PROPIO: el adapter falla al persistir. El pedido ya commiteado NO se revierte. El fallo se loguea y la operación del cliente termina bien. Un pedido que se pierde porque falló un aviso es peor que un aviso perdido.
5. Con dos adapters registrados a la vez, los dos reciben el evento. Si uno falla, el otro igual recibe.
6. Una notificación marcada como vista no vuelve a aparecer como pendiente, aunque se consulte de nuevo.
7. Marcar como vista dos veces es idempotente: no rompe ni duplica.
8. El cuerpo de la notificación lleva solo tipo de operación, identificador y total. Un test verifica que NO contiene dirección de entrega, teléfono ni nombre del cliente.
9. El evento sale después del commit de la operación de dominio, nunca dentro de la transacción. Un test fuerza el rollback de la operación y verifica que no quedó ninguna notificación.

Non-goals:
- Endpoint de polling, sonido y notificación del navegador: son del change 08.
- Cualquier canal externo: WhatsApp, Telegram, mail, SMS, push web. Fuera del MVP.
- Pantalla de notificaciones en el panel.

Restricciones: .instructions.md §GEN-1, §GEN-2, §GEN-4, §DAT-2, §DAT-6, §CONV-10, §NOT-1 a §NOT-8, §SEC-3, §VER-1, §VER-3.
```

### 🛑 Al revisar la spec

- **Que el escenario 4 esté y sea explícito.** Es el que define la jerarquía correcta: el pedido vale más que el aviso. Si el `design.md` mete el envío del evento dentro de la transacción del pedido, un fallo del notificador tira abajo un pedido real de un cliente real. Es exactamente al revés de lo que querés.
- **Que el escenario 3 sea un test de imports**, no una afirmación en prosa. Es la única verificación automática de que la frontera de `NOT-1` existe de verdad.
- **Que la marca de vista esté en el modelo desde el principio.** Agregarla después significa otra migración y, mientras tanto, la tablet sonando en loop.

---

## Change 07 — `bordes`

**CU-10 / 13 / 14 / 20** · Complejidad media · Criticidad normal · **Apply en OpenCode** · sin auditoría

```
/opsx-propose Quiero el change "07-bordes" que cubre UC-10 (hablar con una persona), UC-13 (local cerrado), UC-14 (validar zona de delivery) y UC-20 (reactivar el bot tras el handoff).

Contexto de negocio: son los casos que no aparecen en la demo y que son la mitad de la operación real. Alguien escribe a las cuatro de la mañana. Alguien pide delivery a treinta cuadras del local. Alguien quiere hablar con una persona porque tiene una pregunta que el bot no contempla. Alguien confirma un pedido con un plato que se acabó hace dos minutos.

El handoff es el más delicado de los cuatro. Cuando un cliente pide hablar con una persona, el bot se tiene que callar de verdad: si el dueño está escribiéndole por WhatsApp y el bot le sigue mandando el menú por arriba, es peor que no tener bot. Y el bot no se puede reactivar solo cuando el cliente escribe de nuevo, porque le pisaría la conversación al humano. Se reactiva cuando el staff lo decide, o por un timeout de seguridad, para que un handoff olvidado no deje al cliente sin bot para siempre.

El horario del local es partido: abre al mediodía, cierra a la tarde, vuelve a abrir a la noche. Eso no es un caso raro, es cómo funciona un restaurante de pastas y parrilla.

Alcance backend:
- Validación de horario de apertura contra el YAML, con soporte de horario partido y de días cerrados.
- Validación de zona de delivery contra las zonas configuradas, ofrecidas por botones o lista.
- Estado de handoff en la conversación: al entrar, el bot deja de responder a ese número.
- Reactivación del bot por acción del staff y por timeout de seguridad configurable.
- Re-verificación de disponibilidad del item al seleccionar y al confirmar, enganchada en el punto de extensión del change 02.
- Manejo del carrito vacío.
- messages.yaml de todos estos casos.

Alcance frontend: ninguno. El botón de reactivar del staff es del change 08; acá va el servicio que ese botón llama.

Escenarios que las specs deben cubrir como mínimo:
1. Mensaje recibido fuera del horario de apertura: el bot informa y NO deja armar un pedido.
2. ESCENARIO PROPIO: horario partido. Con el local abierto de 12 a 15 y de 20 a 24, un mensaje a las 13 se atiende, uno a las 17 se rechaza, y uno a las 21 se atiende. Los bordes exactos (15:00 y 20:00) están definidos en la spec y testeados.
3. Un día marcado como cerrado en el YAML rechaza todo el día.
4. Confirmar un pedido con el local cerrado -> 409, aunque el carrito estuviera armado desde antes.
5. Zona de delivery válida: se acepta y se aplica el costo de envío de esa zona.
6. Zona fuera de cobertura: se le ofrece al cliente pasar a retiro o hablar con una persona. El pedido no se confirma como delivery.
7. El cliente pide hablar con una persona: la conversación pasa a handoff y el bot deja de responder a ese número. Un test manda tres mensajes más y verifica que no sale ninguna respuesta automática.
8. El staff reactiva el bot: la conversación vuelve al menú principal y el bot responde de nuevo.
9. ESCENARIO PROPIO: handoff olvidado. Pasado el timeout de seguridad configurado, el bot se reactiva solo. El test cambia el timeout por config y el comportamiento cambia con él.
10. Item que deja de estar disponible entre el listado y la selección: se informa al cliente y no se agrega al carrito.
11. Item que deja de estar disponible entre la selección y la confirmación -> 409, con el item identificado, y el pedido no se crea.
12. Confirmar con el carrito vacío: se responde el mensaje correspondiente y no se crea ningún pedido.

Non-goals:
- Pantallas del panel: son del change 08.
- Cálculo de rutas, distancias o geolocalización. Las zonas son una lista cerrada de botones.
- Notificar al staff que hay un handoff pendiente: el evento ya existe desde el change 06.

Restricciones: .instructions.md §GEN-6, §GEN-7, §GEN-8, §CONV-1, §CONV-3, §WA-7, §TXT-1, §TXT-3, §ORD-9, §ORD-10, §RES-8, §API-3, §VER-1, §VER-3.
```

### 🛑 Al revisar la spec

- **Que el escenario 7 verifique el silencio.** "Pasa a handoff" es fácil de implementar y fácil de creer. Lo que importa es que después de eso el bot no conteste nada, y eso solo se prueba mandando más mensajes y verificando que no sale ninguna respuesta.
- **Que los bordes del horario partido estén definidos en la spec.** ¿Las 15:00 en punto está abierto o cerrado? Si la spec no lo dice, el agente elige, vos no te enterás, y la respuesta correcta la tiene el dueño del local. Es una de las cinco preguntas del CP-2.
- **Que el timeout de handoff exista.** Es la red de seguridad de todo el caso: sin él, un handoff que nadie cierra deja a ese cliente sin bot para siempre y nadie se entera nunca.

---

## Change 08 — `panel`

**CU-15 / 16 / R4** · Complejidad media · Criticidad sensible · **Apply en Claude Code** · audita `@security`

```
/opsx-propose Quiero el change "08-panel" que cubre UC-15 (ver pedidos y reservas entrantes), UC-16 (cambiar estado del pedido y notificar al cliente) y UC-R4 (confirmar o rechazar reserva), más las pantallas de UC-17, UC-18 y UC-20, y el aviso al staff en el navegador.

Contexto de negocio: el panel es donde trabaja el restaurante. Se abre en una tablet o una compu en la cocina y queda abierto todo el servicio. Ahí se ve lo que entra, se cambia el estado de los pedidos a medida que avanzan, se confirman o rechazan reservas, se marca lo que se acabó y se reactiva el bot cuando alguien terminó de atender a un cliente a mano.

Dos cosas lo hacen delicado. La primera es que es la única superficie autenticada del sistema y está expuesta a internet: si una ruta se queda sin protección, cualquiera cambia el estado de los pedidos de un restaurante. La segunda es el aviso: cuando entra un pedido, la cocina se tiene que enterar sin estar mirando la pantalla. Suena y aparece una notificación del navegador. Si el navegador tiene el permiso denegado, el panel lo tiene que decir en pantalla, porque una cocina que cree que le van a avisar y no le avisan nadie es peor que una cocina que sabe que tiene que mirar.

Alcance backend y frontend:
- Login usuario y clave con la clave hasheada, sesión por cookie.
- Listado de pedidos y reservas entrantes por estado.
- Cambio de estado del pedido con notificación al cliente por WhatsApp.
- Confirmar y rechazar reservas.
- Togglear disponibilidad de items y editar menú, precios y tiempos.
- Reactivar el bot tras un handoff.
- Traza de auditoría append-only de toda acción de staff.
- Endpoint de polling para notificaciones pendientes, consumido con HTMX.
- Aviso en el navegador: sonido más notificación, con el permiso pedido una vez mediante un gesto explícito.
- Plantillas Jinja2 con parciales para HTMX.

Escenarios que las specs deben cubrir como mínimo, con código de estado explícito:
1. ESCENARIO PROPIO, y quiero la lista completa: para CADA ruta del panel, una petición sin sesión -> 401 o 403 según corresponda. La spec enumera todas las rutas una por una; no vale "las rutas del panel exigen sesión".
2. Login con clave correcta -> 200 y cookie de sesión con HttpOnly, Secure y SameSite. Un test inspecciona los flags de la cookie.
3. Login con usuario inexistente y login con clave incorrecta devuelven exactamente la misma respuesta y el mismo tiempo de espera aproximado. Nada distingue un caso del otro.
4. Superado el límite configurado de intentos fallidos, el login se bloquea.
5. La clave nunca se almacena ni se loguea en texto plano. Un test verifica que el hash no es reversible y que no es un SHA suelto.
6. ESCENARIO PROPIO: toda mutación exige token CSRF. Una petición sin token -> 403. Una petición de mutación por GET -> 405 o 403, nunca se ejecuta. Esto incluye los hx-get de HTMX: ninguno cambia estado.
7. Cambiar el estado de un pedido aplica la transición y notifica al cliente. Una transición inválida -> 409.
8. Confirmar una reserva -> 200 y sale el template al cliente. Rechazarla -> 200 y sale el aviso.
9. Cada acción de staff deja una fila de auditoría con quién, qué y cuándo. La traza es append-only: un test verifica que no hay forma de editar ni borrar una fila desde la aplicación.
10. XSS: un pedido cuyo cliente escribió etiquetas HTML en las observaciones, o una dirección con comillas y script, se renderiza escapado. Un test lo verifica en la página.
11. El polling devuelve solo las notificaciones no vistas. Marcarlas como vistas hace que la siguiente vuelta no las traiga.
12. ESCENARIO PROPIO: el mismo pedido no suena dos veces. Recargar el panel, abrirlo en dos dispositivos o esperar dos vueltas de polling no vuelve a disparar el aviso de una notificación ya vista.
13. Con el permiso de notificaciones denegado, el panel muestra un aviso visual dentro de la página y lo informa. Nunca queda silencioso sin señal.
14. El intervalo de polling sale de config. Un test lo cambia y el comportamiento cambia con él.

Non-goals:
- Pantalla de auditoría dedicada: el MVP guarda la traza, no la muestra.
- Roles y permisos diferenciados dentro del staff: un solo rol por instancia.
- Gestión de usuarios desde el panel: se crean por script o por migración.
- Websockets y SSE: el aviso es por polling.
- Canales externos de notificación.
- Reportes, métricas y estadísticas.

Restricciones: .instructions.md §GEN-3, §GEN-4, §GEN-7, §DAT-1, §PAN-1 a §PAN-10, §NOT-7, §NOT-8, §VAL-1, §API-2, §API-3, §API-4, §SEC-1 a §SEC-4, §ORD-13, §RES-1, §VER-1, §VER-3.
```

### 🛑 Al revisar la spec

- **Verificá el 401 y el 403 explícito, ruta por ruta.** Este es EL punto de control de este change. Pedí que `specs/` enumere cada ruta del panel con su escenario de acceso sin sesión. "Las rutas del panel exigen sesión" es una frase, no una verificación: la ruta que se olvidaron de proteger es exactamente la que no aparece en esa lista, y es la que va a encontrar alguien más.
- **Que los `hx-get` de HTMX no muten nada.** Es el error clásico de HTMX y rompe `PAN-6` de la forma más silenciosa posible: un enlace que parece navegación y cambia el estado de un pedido, sin CSRF, ejecutable desde cualquier página que consiga que el navegador del staff lo cargue.
- **Que el escenario 12 esté.** Sin él, el aviso funciona perfecto el primer día y para el tercero alguien silenció la tablet.
- **Que el escenario 13 esté.** El modo de fallar más peligroso de todo el sistema no es que suene de más: es que no suene y nadie lo sepa.

---

## Change 09 — `hardening`

**Complejidad media** · Criticidad normal · **Apply en OpenCode** · sin auditoría

```
/opsx-propose Quiero el change "09-hardening" que cierra el MVP para que pueda correr en la casa de un cliente real sin que nosotros estemos mirando.

Contexto de negocio: hasta acá el sistema funciona en nuestra máquina. Este change lo prepara para vivir solo en un servidor, atendiendo a un restaurante de verdad, con nosotros enterándonos si algo se rompe en vez de descubriéndolo porque el dueño nos escribe un sábado a la noche.

Alcance:
- Tests de integración que cubran los flujos completos de punta a punta: pedido de delivery, pedido de retiro, reserva confirmada, reserva rechazada, handoff y reactivación.
- Dockerfile de la aplicación y docker-compose de producción.
- Logs estructurados en JSON, con el enmascarado de datos personales verificado.
- Health check listo para el monitoreo externo.
- Backups automáticos de PostgreSQL, con la restauración probada de verdad, no solo configurada.
- Revisión final de .env.example: toda clave que la app necesita, ningún valor real.
- Documentación de despliegue: de cero a instancia andando.

Escenarios que las specs deben cubrir como mínimo:
1. El flujo completo de un pedido de delivery, desde el primer mensaje hasta la entrega, contra la app levantada con PostgreSQL real.
2. Lo mismo para un pedido de retiro, verificando que no pasa por en camino.
3. Reserva solicitada, escalada, confirmada por el staff y avisada al cliente.
4. Reserva rechazada por el staff.
5. Handoff, silencio del bot y reactivación por el staff.
6. Un backup se toma, se restaura en una base limpia, y un test verifica que los datos están completos. Un backup que nunca se restauró no es un backup.
7. Los logs en producción no contienen teléfonos completos, direcciones, cuerpos de mensaje ni secretos. Un test recorre la salida de un flujo completo y falla si encuentra alguno.
8. El health check distingue app arriba con DB caída de app arriba y sana.
9. El contenedor levanta desde cero con solo el .env y el docker-compose.

Non-goals:
- Multi-tenant: una instancia por restaurante, por GEN-5.
- Alta disponibilidad, réplicas y balanceo.
- Métricas, dashboards y alertas sofisticadas.
- Funcionalidad nueva de cualquier tipo.

Restricciones: .instructions.md §GEN-3, §GEN-5, §GEN-8, §SEC-1 a §SEC-6, §DAT-10, §VER-1, §VER-3, §VER-4, §SDD-3.
```

### 🛑 Al revisar la spec

- **Que el escenario 6 restaure de verdad.** Un backup configurado y nunca restaurado es un backup imaginario, y te vas a enterar el día que lo necesites.
- **Que el escenario 7 sea un test automático.** Es la única verificación real de `SEC-3` sobre el sistema completo en funcionamiento, no sobre módulos sueltos.
- **Que no entre funcionalidad nueva.** Es el último change y la tentación de "ya que estamos" es máxima. `SDD-3`: los non-goals son vinculantes.

---

# Fase C.2 — Prompts genéricos del ciclo

Estos se repiten igual en cada change. Son cortos a propósito: el trabajo pesado ya está en la spec y en las skills.

## Implementar

```
/opsx-apply <change>

Ejecutá las tareas en el orden de tasks.md. Después de CADA tarea, corré la skill run-verify y mostrame el resultado antes de pasar a la siguiente.

Si aparece un caso que la spec no cubre, frená y proponeme el escenario nuevo. No lo resuelvas por tu cuenta ni amplíes el alcance.

Al terminar, abrí el PR.
```

> **Al revisar:** mirá que el `run-verify` haya corrido de verdad entre tarea y tarea, no todo junto al final. Si el agente tildó cinco tareas y después corrió la verificación una sola vez, perdiste el punto de corte: el error de la tarea 2 ya se enterró bajo tres tareas más.

## Verificación funcional

```
Recorré la spec del change <change> escenario por escenario contra la app corriendo. Usá @api-explorer para armar y ejecutar los curls.

Devolveme una tabla: escenario -> PASS o FAIL, con la evidencia (código HTTP y cuerpo recortado).

Los FAIL se corrigen antes de seguir. Un escenario que no se puede ejercer por curl se marca NO VERIFICABLE POR CURL y decís qué test de integración lo cubre; no lo marques PASS.
```

## Auditoría — solo changes 00, 02, 03, 05 y 08

```
@security corré la skill security-audit sobre los archivos del change <change>.

Devolveme la tabla de riesgo · archivo:línea · regla · hallazgo · recomendación, ordenada por riesgo.
```

> **Al revisar:** los hallazgos de riesgo medio y alto se corrigen **antes** de archivar, no después (`SDD-4`). Y si el reporte viene vacío en un change sensible, mirá la lista de ítems `NO VERIFICADO`: a veces "limpio" significa "no pude revisar nada".

## Archivar

```
/opsx-archive <change>

Antes de archivar confirmá: todas las tareas de tasks.md completas, verificación funcional en verde, y —si el change es sensible— auditoría hecha con los hallazgos medio y alto corregidos.

Mostrame el diff de openspec/specs/ para que vea qué quedó consolidado.
```

## Cierre de sesión

```
Corré la skill update-estado.

Después agregá la entrada de bitácora en el README de esta sesión:
- Qué change se trabajó y en qué herramienta.
- El prompt que usé, tal cual.
- Qué tuve que ajustar a mano sobre lo que salió del agente.
- Qué corrigió el loop de run-verify, con un ejemplo concreto: qué falló, en qué archivo, qué cambió.
- Qué casos de uso quedaron cubiertos.

Escribí lo que pasó, no lo que estaba planeado.
```

> **Al revisar:** la bitácora es lo que después alimenta el README final y la justificación de todo el andamiaje. Si la escribís genérica ("el loop corrigió varios errores"), en tres meses no vale nada. El ejemplo concreto es lo que la hace útil.

## Handoff entre herramientas

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

> **Cuándo:** 2 o 3 `run-verify` fallidos por la misma causa en OpenCode. Revertí lo que quedó a medias antes de pasar el contexto: se entrega un estado limpio, no un desastre parcial.

---

# Fase C.3 — Cierre del proyecto

## Auditoría final

```
@security corré la skill security-audit sobre TODO el repositorio, no solo sobre un change.

Además verificá:
- Que .env no aparezca en git ls-files, ni en el historial con un valor real.
- Que .env.example liste todas las claves que la app necesita y ninguna con valor real.
- Que ninguna ruta del panel haya quedado sin exigir sesión. Enumerá las rutas y marcá una por una.

Devolveme la tabla de hallazgos ordenada por riesgo.
```

```
Corré run-verify sobre todo el repositorio y mostrame el resultado completo, paso por paso.
```

> **Al revisar:** de esos dos prompts sale la lista de pendientes por riesgo. Los altos se corrigen antes de que esto toque el WhatsApp real de un restaurante. Los medios, antes de dejarlo solo.

## README final

```
Escribí el README definitivo del proyecto. Usá la bitácora acumulada en el README actual: no inventes prompts ni resultados que no estén registrados ahí.

Secciones:

1. Qué es y qué resuelve. El problema real del restaurante, en dos párrafos.
2. Arquitectura: el monolito modular, sus módulos, y las tres fronteras (repositorio, intención abstracta -> adapter de canal, evento de dominio -> StaffNotifier). Con un diagrama Mermaid del flujo completo, desde el webhook de Meta hasta el aviso en el panel.
3. Los casos de uso, con su estado: cubierto, parcial o fuera del MVP.
4. Decisiones de arquitectura: los siete ADRs del documento original más las que se tomaron durante la construcción, cada una con su por qué. Incluí las que se revirtieron y por qué se revirtieron.
5. AI Engineering. Esta sección es la justificación completa del andamiaje:
   - La jerarquía de gobierno y por qué está separada en capas.
   - SDD con OpenSpec: el ciclo, y por qué la revisión humana de la spec no se delega.
   - Las skills, qué reglas hace cumplir cada una.
   - Los subagentes y por qué son read-only.
   - La matriz OpenCode vs Claude Code y el criterio de ruteo por complejidad del apply.
   - Los loops de run-verify: con ejemplos CONCRETOS sacados de la bitácora de qué corrigieron.
6. Los MCP configurados, con el rol de cada uno en el flujo.
7. Instalación desde cero: de repo clonado a instancia andando.
8. Qué NO hace este MVP y qué entra en fase 2.

Si algo de lo que te pido no está en la bitácora, decímelo en vez de completarlo. Prefiero un hueco marcado a un dato inventado.
```

> **Al revisar:** la última línea del prompt es la importante. La sección 5 es la que vale para mostrar el trabajo, y es también donde más fácil aparece un ejemplo inventado de "qué corrigió el loop". Si la bitácora está bien escrita, esa sección sale sola. Si no, se nota.

---

# Orden completo, de un vistazo

| Paso   | Qué                        | Herramienta | Audita      |
| ------ | -------------------------- | ----------- | ----------- |
| P0.1   | Saneamiento y constitución | Claude Code | —           |
| P0.2   | Toolchain y esqueleto      | Claude Code | —           |
| P0.3   | `openspec init`            | Terminal    | —           |
| P0.4   | CI sobre el PR             | OpenCode    | —           |
| P0.5   | Sanity check               | Ambas       | —           |
| 00     | `walking-skeleton`         | Claude Code | `@security` |
| 01     | `cimientos-datos`          | OpenCode    | —           |
| 02     | `pedidos-core`             | Claude Code | `@security` |
| 03     | `conversacion`             | Claude Code | `@security` |
| 04     | `flujo-pedido-wa`          | Claude Code | —           |
| 05     | `reservas`                 | Claude Code | `@security` |
| 06     | `notificacion-staff`       | OpenCode    | —           |
| 07     | `bordes`                   | OpenCode    | —           |
| 08     | `panel`                    | Claude Code | `@security` |
| 09     | `hardening`                | OpenCode    | —           |
| Cierre | Auditoría final + README   | Ambas       | `@security` |

**En cada change, el mismo ciclo:** propose → 🛑 **revisás la spec** → apply → verificación funcional → auditoría si es sensible → PR y merge → archive → `update-estado` y bitácora.
