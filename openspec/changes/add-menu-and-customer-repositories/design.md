# Design: Add menu and customer repositories

## Context

La motivación está en proposal.md (Why). Lo que condiciona el diseño:

- `Customer` y `MenuItem` existen en `backend/app/models/` y en la base
  (`alembic_version = c3a7b9d2e641`). `customers.phone` tiene el índice único
  `ix_customers_phone`. `menu_items` tiene `CHECK price >= 0` y
  `CHECK estimated_time_min IS NULL OR estimated_time_min >= 0`.
- `configure_mappers()` corre sin error sobre `app.models` (verificado el
  10/10). La parte de la deuda D-9 que decía "falta confirmar" queda
  confirmada; este change la ejercita en cada test de integración.
- `build_engine` ya usa `hide_parameters=True`: un error de SQLAlchemy no lleva
  los parámetros de la sentencia (SEC-3).
- `InvalidInputError` y `NotFoundError` ya existen y ya mapean a 400 y 404.
  `AppError` acepta un `detail` para el log y un `field` opcional.
- La base de desarrollo corre `read committed` (default de PostgreSQL) y
  collation `en_US.utf8`.
- Probado el 10/10 con la versión pineada de Pydantic: el texto de un
  `ValidationError` incluye el valor recibido (`input_value=...`). Si uno se
  escapa con un teléfono adentro, el teléfono termina en el log.

## Goals / Non-Goals

**Goals:**

- Una frontera de datos que los próximos módulos (`orders`, `conversations`,
  `reservations`) copien tal cual: repositorio con `Session`, servicio sin
  ella, transacción en manos de quien llama.
- Que las garantías del negocio (no borrar, no duplicar, no tocar históricos)
  dependan de la base o de una sola función, no de la disciplina de quien
  llama.

**Non-Goals (de diseño, además de los del proposal):**

- Ninguna fábrica ni contenedor de dependencias: los tests construyen
  `MenuService(repo)` a mano. Cómo se arma en un request lo decide el change
  del webhook.
- Ningún lock (`FOR UPDATE`) en el menú: la disponibilidad se re-verifica al
  agregar al carrito (ORD-10) y al confirmar (ORD-15), dentro de la
  transacción del pedido. Bloquear acá no protege nada que esas reglas no
  cubran.
- No se cachea el menú.

## Decisions

### D1. Dónde vive cada archivo

```
backend/app/domain/                         nada acá importa sqlalchemy, app.models ni app.db
├── __init__.py                             vacío
├── menu/
│   ├── __init__.py                         vacío
│   ├── schemas.py                          MenuItemRead, MenuItemUpdate (Pydantic)
│   └── service.py                          MenuRepository (Protocol) + MenuService
└── customers/
    ├── __init__.py                         vacío
    ├── schemas.py                          CustomerRead (Pydantic)
    └── service.py                          CustomerRepository (Protocol) + CustomerService

backend/app/db/                             destino que nombra D-5
├── __init__.py                             vacío
└── repositories/
    ├── __init__.py                         vacío
    ├── menu.py                             SqlMenuRepository (importa Session y MenuItem)
    └── customers.py                        SqlCustomerRepository (importa Session y Customer)

tests/unit/
├── domain_fakes.py                         InMemoryMenuRepository, InMemoryCustomerRepository
├── test_menu_service.py
├── test_menu_schemas.py                    errores de forma de MenuItemUpdate
├── test_customer_service.py
└── test_domain_boundaries.py               AST sobre todo app.domain + import en intérprete limpio
tests/integration/
├── conftest.py                             + fixture de sesión con transacción externa
├── test_menu_repository.py
├── test_customer_repository.py
└── test_customer_concurrency.py
```

**Lectura estricta de GEN-1 (decidido por Lautaro el 10/10).** GEN-1 dice que
el dominio no importa la `Session`. Por eso los repositorios viven fuera de
`backend/app/domain/`, en `backend/app/db/repositories/`, y **ningún** módulo
bajo `domain/` importa `sqlalchemy`, `app.models`, `app.core.database` ni
`app.db`. La regla no tiene excepciones por archivo: el test de AST recorre
todo el paquete `domain`, incluidos los módulos que sumen los changes futuros
y los imports dentro de funciones. Así, un `orders/service.py` que importe la
`Session` dentro de una función también falla.

- **La dependencia apunta hacia el dominio.** `db/repositories/menu.py`
  importa los schemas de `domain/menu/schemas.py`, porque devuelve
  `MenuItemRead`. El dominio no importa nada de `db/`. Es el sentido correcto:
  la persistencia depende del dominio y no al revés.
- **El `Protocol` vive en `service.py`.** La interfaz es de quien la consume:
  el servicio declara qué necesita, y el repositorio la cumple
  estructuralmente, sin heredar ni importar nada del servicio. En los tests de
  integración, una asignación tipada
  (`repo: MenuRepository = SqlMenuRepository(session)`) hace que mypy estricto
  verifique que la implementación cumple el contrato.
- **Los `__init__.py` quedan vacíos.** Si un `__init__.py` de `db/`
  re-exportara algo y se importara desde el dominio, arrastraría SQLAlchemy.
  El test de "intérprete limpio" (spec `domain-data-boundary`) cubre ese hueco
  transitivo, que el AST no ve.
- **Los modelos se quedan en `backend/app/models/`, y `core/database.py` en
  `core/`.** Solo `db/repositories/` los importa. Cuando se reconcilie el
  layout (D-5), se mueven sin tocar el dominio.
- **Nombres de los métodos** (en inglés, GEN-9):
  - `MenuService`: `list_categories()`, `list_available_items(category)`,
    `list_all_items()`, `get_item(item_id)`,
    `set_available(item_id, available)` y
    `update_item(item_id, changes: MenuItemUpdate)`.
  - `CustomerService`: `get_or_create_by_phone(phone: str)`.

**Alternativas descartadas:**

- *`repository.py` dentro de cada `domain/<modulo>/`* (la primera versión de
  este design). Exigía leer GEN-1 como "todo menos el repositorio", y el test
  de AST tenía que listar excepciones por archivo.
- *Un `ports.py` aparte para los `Protocol`.* Suma un archivo por módulo sin
  aportar nada mientras cada interfaz tenga un solo consumidor.

### D2. Quién es dueño de la transacción

**Quien abre la transacción la cierra.** En producción va a ser el borde: el
handler del webhook o el endpoint del panel. En los tests, el propio test. El
repositorio recibe una `Session` ya abierta y solo ejecuta sentencias. Puede
hacer `flush`, pero no hace `commit`, `rollback`, `begin`, `close` ni
`begin_nested`. El servicio no tiene con qué hacerlo, porque no ve la
`Session` (D3).

Por qué:

- **CONV-10.** El `INSERT` de idempotencia de WA-4 y todo el efecto del
  mensaje (crear el customer, armar el pedido, mover la conversación) van en
  una única transacción. Si `get_or_create_by_phone` commiteara, un fallo
  posterior revertiría la marca de idempotencia pero dejaría el customer
  creado. Ese caso puntual es inofensivo, pero el patrón no lo es: el día que
  `orders` copie un repositorio que commitea, un pedido queda persistido con
  el mensaje marcado como no procesado, y el reintento de Meta lo duplica.
- **Los envíos salientes van después del commit** (CONV-10). Solo quien
  commitea sabe cuándo pasó.
- **Composición.** Un caso de uso que toca dos repositorios (customer +
  conversation + order) necesita que ninguno de los dos decida por los demás.

**Alternativas descartadas:**

- *Commit en el repositorio.* Rompe CONV-10 por lo de arriba.
- *Commit en el servicio.* Exige que el servicio vea la `Session` o una
  abstracción de transacción. Lo primero rompe D3. Lo segundo es un unit of
  work, y ese patrón es non-goal: lo define el change del webhook. Este change
  solo fija que, sea cual sea ese patrón, los repositorios no commitean.

**Cómo se verifica:** escenarios de rollback de la spec
`domain-data-boundary`, más un test de AST que falla si algún módulo de
`backend/app/db/repositories/` llama a `commit`, `rollback`, `begin`,
`begin_nested` o `close`.

### D3. Por qué ningún servicio ve una `Session`

1. **GEN-1 y DAT-2 lo exigen.** En la lectura estricta, ningún módulo del
   dominio importa la `Session`, y el acceso a datos va detrás de un
   repositorio que vive fuera del dominio (D1).
2. **No puede commitear lo que no ve.** D2 depende de esto. Si el servicio
   tuviera la `Session`, la regla "no commitear" sería una convención que se
   cumple por disciplina. Sin ella, es imposible romperla sin cambiar un
   import, y ese cambio lo agarra el test de AST.
3. **Tests de dominio sin base (VER-3).** Las reglas (validación de precio,
   teléfono canónico, edición parcial, idempotencia de `set_available`) se
   prueban con un fake en memoria, en milisegundos y sin contenedor. La base
   real se reserva para lo que solo la base puede probar: el índice único, la
   concurrencia, el rollback y los tipos que devuelve psycopg.
4. **Nada ORM se escapa.** El servicio recibe y devuelve schemas Pydantic. Un
   objeto ORM que sale del repositorio puede disparar un lazy load fuera de la
   transacción, o un cambio de atributo que se flushea sin querer.

**`Protocol` y no clase abstracta**, porque el repositorio no tiene que
importar nada del servicio. El acoplamiento es en una sola dirección:
`db/repositories/` conoce los schemas del dominio, y el dominio no conoce
`db/`.

**Costo:** una capa más de tipos (los `Protocol` y los schemas de salida), y
mantener el fake en memoria en sintonía con el repositorio real. Lo mitiga
que los dos implementan el mismo `Protocol` bajo mypy estricto, y que los
escenarios de comportamiento observable (orden, filtro de disponibles) se
prueban también contra la base real.

### D4. Obtener o crear: el índice único hace el trabajo

El repositorio ejecuta dos sentencias:

```sql
INSERT INTO customers (phone) VALUES (:phone)
ON CONFLICT (phone) DO NOTHING
RETURNING id, phone, name, created_at;
-- si no devolvió fila:
SELECT id, phone, name, created_at FROM customers WHERE phone = :phone;
```

Ambas usan el ORM o sentencias parametrizadas (SEC-4). Qué pasa con dos
transacciones simultáneas para el mismo número, en `read committed`:

- A inserta y no commitea. B intenta el mismo `INSERT` y **espera** sobre la
  entrada del índice único.
- Si A commitea, el `ON CONFLICT DO NOTHING` de B no devuelve fila. El
  `SELECT` siguiente toma un snapshot nuevo, ve la fila de A y devuelve el
  mismo `id`.
- Si A hace rollback, el `INSERT` de B procede y crea la fila.

**Alternativas descartadas:**

- *`SELECT` y después `INSERT` si no existe.* Las dos transacciones ven "no
  existe" y una falla con `IntegrityError`. Es la carrera que el escenario 12
  pide evitar.
- *`INSERT` y capturar `IntegrityError`.* En PostgreSQL un error aborta la
  transacción entera: la del caller, con la marca de idempotencia adentro.
  Habría que envolverlo en un savepoint, y eso es más maquinaria para el
  mismo resultado.
- *`ON CONFLICT DO UPDATE SET phone = EXCLUDED.phone RETURNING`.* Devuelve la
  fila en una sola sentencia, pero toma un lock de fila sobre `customers`
  hasta el final de la transacción y escribe una versión nueva de la fila en
  cada mensaje. Ese lock no figura en el orden de CONV-9 (idempotencia →
  `Conversation` → otros), y sumarlo por comodidad abre la puerta a un
  deadlock que hoy no existe.

**Supuesto:** el caller corre en `read committed`. En `repeatable read`,
PostgreSQL rechaza el `ON CONFLICT` contra una fila commiteada fuera del
snapshot, con un error de serialización. Ver Risks.

**Cómo se prueba la concurrencia (VER-2):** se usan dos engines, o sea dos
conexiones reales y dos sesiones.

- *Test determinista.* A crea y no commitea. B arranca en un thread. El test
  verifica que B sigue bloqueado, consultando `pg_stat_activity` con
  `wait_event_type = 'Lock'` desde una tercera conexión. Después A commitea y
  B devuelve el mismo `id`. Una variante hace rollback en A.
- *Test de carrera.* Varios threads con una `threading.Barrier`, todos para el
  mismo número, todos commitean. Al final hay un solo registro y un solo
  `id`.

Los números de prueba son únicos por corrida, y el teardown borra sus filas,
porque este es el único test que commitea.

### D5. Validación: la forma en `MenuItemUpdate`, las reglas en el servicio

La frontera sigue VAL-3 tal como la fijó Lautaro el 10/10. Pydantic valida
**forma** (tipos, largos, campos requeridos, campos desconocidos). El
servicio valida **reglas** y levanta `InvalidInputError`.

**Criterio (precedente para `orders` y `reservations`, aprobado el 10/10):**
**forma (Pydantic) = tipo, largo, nulidad y campos desconocidos; reglas
(servicio) = límites de valor y de negocio.**

Aplicado a este change:

- **Forma:** un nombre vacío o en blanco es forma, porque es un largo.
- **Reglas:** un precio negativo, la escala del precio, el rango de
  `Numeric(12,2)`, y un tiempo negativo o fuera del rango de `Integer` son
  reglas, porque son límites de valor.

**`MenuItemUpdate` (forma)** usa `strict=True`, `extra="forbid"` y
`str_strip_whitespace=True`. Todos sus campos son opcionales: un campo que no
vino queda fuera de `model_fields_set`, y uno que vino vacío queda adentro
con su valor.

| Campo | Tipo cuando viene | Forma que valida |
|---|---|---|
| `name` | `str`, no nulo | trim, de 1 a 150 caracteres (`String(150)`) |
| `description` | `str \| None` | trim; si queda vacío o viene `None`, se guarda sin descripción |
| `price` | `Decimal`, no nulo | `allow_inf_nan=False`; `strict` rechaza `float`, `str` e `int` |
| `estimated_time_min` | `int`, no nulo | `strict` rechaza `bool`, `float` y `str`; un `null` explícito falla acá (nulidad = forma), así el tiempo nunca vuelve a desconocido |

Probado el 10/10 con la versión pineada:

- `name=None` da `string_type` y `name="   "` da `string_too_short`.
- `price=None` y `price=1.5` dan `is_instance_of`, y `price=NaN` da
  `finite_number`.
- `category="x"` da `extra_forbidden` y `estimated_time_min=True` da
  `int_type`.
- `model_fields_set` distingue `{}` de `{"description"}` cuando el valor es
  `None`.
- Con el mismo patrón que `name` y `price` (default `None`, tipo no nulo),
  `estimated_time_min=None` explícito da error de tipo.

Cómo declarar "opcional pero no nulo" sin pelearse con mypy (un default
`None` sobre `str`, o un validador `mode="before"`) se resuelve en el apply.
El comportamiento está fijado por la spec.

**Camino de los errores de forma.** Un `ValidationError` al construir
`MenuItemUpdate` no es un error del dominio: sigue el camino de validación
del contrato de errores.

- Cuando `MenuItemUpdate` es el payload de un endpoint, FastAPI lo convierte
  en `RequestValidationError`, y el handler existente responde `400`
  `invalid_input` con el campo, sin repetir el input (VAL-1).
- **Requisito para el change del panel:** el endpoint **tiene** que recibir
  `MenuItemUpdate` (o un formulario que lo construya) como payload validado
  por FastAPI. Si lo construye a mano dentro del handler, un
  `ValidationError` suelto termina en `500`, porque el contrato solo traduce
  `RequestValidationError`.
- El texto de un `ValidationError` incluye el valor rechazado. Para los campos
  del menú no es dato personal, y además `api/errors.py` ya trata
  `ValidationError` como opaco al loguear.

**Reglas en `MenuService.update_item`.** Cada una levanta
`InvalidInputError(detail, field=...)`, con un `detail` fijo que no incluye el
valor.

| Regla | Campo |
|---|---|
| Sin ningún campo en `model_fields_set` | — (`field=None`) |
| `price < 0` | `price` |
| `price` con más de dos decimales significativos (`price != price.quantize(Decimal("0.01"))`): `1500.500` pasa y `1500.505` no | `price` |
| `price` fuera de `Numeric(12,2)` (`abs(price) >= 10**10`) | `price` |
| `estimated_time_min < 0` o `> 2_147_483_647` (`Integer`) | `estimated_time_min` |

- **Precio y tiempo no negativos son reglas de negocio.** Pydantic podría
  validarlos con `ge=0`, pero un precio negativo no es un error de tipo: es un
  importe que el negocio no admite. Lo mismo vale para la escala y el rango.
  Tener las reglas del importe en el dominio deja que `orders` reuse la misma
  función cuando valide líneas.
- **El precio no se redondea.** El servicio nunca redondea. El repositorio
  cuantiza a `0.01` antes de escribir, y con un valor ya validado eso no
  cambia el valor (`1500.500` → `1500.50`). La lectura vuelve siempre con
  exponente `-2`.
- **Orden de los chequeos:** primero las reglas, después el id ("Business
  rules are checked before the item is looked up"). Un id fuera de
  `1..2**63-1` se responde con `NotFoundError` sin ir a la base. El `detail`
  es `f"menu item {item_id} not found"`.

**Teléfono (customers).** `get_or_create_by_phone(phone: str)` valida en el
servicio con `re.fullmatch(r"[0-9]{8,15}", phone)` y levanta
`InvalidInputError("phone is not canonical", field="phone")`. Es `[0-9]` y no
`\d`, porque `\d` acepta dígitos Unicode como `٥`.

- No pasa por Pydantic porque el teléfono no llega en un payload HTTP: lo
  entrega el adapter de WhatsApp ya normalizado (non-goal acá), y la spec pide
  `InvalidInputError`.
- Al no haber Pydantic de por medio, no existe ningún `ValidationError` cuyo
  texto pueda arrastrar el número (SEC-3).
- `CustomerRead` solo valida la forma de salida (fecha con zona).

### D6. Edición parcial y disponibilidad

- **Edición parcial.** Después de aplicar las reglas, el servicio arma el
  diccionario de cambios con
  `changes.model_dump(include=changes.model_fields_set)`. El repositorio emite
  `UPDATE menu_items SET <solo esas columnas> WHERE id = :id RETURNING ...`.
  - Las columnas que no vinieron no aparecen en el `SET`. Si dos personas del
    staff editan a la vez el nombre y el precio del mismo plato, ninguna pisa
    el cambio de la otra. Con leer, modificar y escribir el objeto entero, la
    segunda escritura sí pisaría a la primera.
  - Sin fila devuelta, `NotFoundError`.
- **`set_available(item_id, available)`** es un
  `UPDATE ... SET available = :available WHERE id = :id RETURNING ...`.
  Fijar el mismo valor dos veces deja la misma fila, sin error.
- **Ninguna operación emite `DELETE`.** El test del escenario de agotado
  verifica que la fila sigue en la base, consultándola desde la propia sesión
  sin pasar por el repositorio.

**Interpretación de DAT-5 (aprobada por Lautaro el 10/10).** DAT-5 dice
"Marcar un item agotado **togglea** `MenuItem.available`; el `MenuItem` nunca
se borra". Este change lo implementa como **seteo explícito**
(`set_available(id, True|False)`), no como toggle (`available = NOT
available`). Las razones:

- **Lo que DAT-5 protege es la segunda mitad:** el item no se borra.
  "Togglea" describe el efecto visible en el panel (un interruptor), no la
  operación que se persiste.
- **Un toggle no es idempotente.** Dos clics en "agotado" (doble tap, dos
  tablets, un reintento del navegador después de un timeout) dejan el plato
  **disponible**: el cliente lo pide y la cocina ya no lo tiene. Con el seteo
  explícito, el estado final es el que el staff vio y eligió, por más veces
  que llegue el pedido.
- **El panel puede seguir mostrando un interruptor.** Manda el valor destino
  (`available=false`), no "invertí lo que haya".
- **Si se quiere que la letra de la regla acompañe**, el cambio sugerido para
  `.instructions.md` es "fija `MenuItem.available` al valor elegido". Editar
  ese archivo requiere aprobación aparte (PRI-2); este change no lo toca.

### D7. Lecturas, orden y tipos

- **`list_categories`:** `SELECT DISTINCT category ... WHERE available
  ORDER BY category`.
- **Listas de items:** `ORDER BY name, id`. Las dos usan la collation de la
  base, que para un menú en castellano es la correcta (`Ñoquis` entre `N` y
  `O`, no después de la `Z` como con `C`). Ver Risks.
- **`MenuItemRead`** es un solo schema de salida, con `available`, para las
  dos listas. En la lista del cliente siempre vale `true`, y un segundo schema
  no aporta nada.
- **Precios con dos decimales.** `MenuItemRead.price` es `Decimal`, y un
  validador de salida verifica que el exponente sea `-2`.
- **Fechas en UTC.** `created_at` es `AwareDatetime`, que rechaza los naive.
  Un validador lo pasa a UTC con `astimezone(UTC)`, porque psycopg devuelve
  la fecha en la zona de la sesión de la base.
- **`CustomerRead.phone`** lleva `Field(repr=False)`, así un `repr()` o un
  log del objeto no muestran el número.
- **Los schemas de salida son inmutables** (`frozen=True`). Modificar un
  atributo levanta un error y no se puede confundir con un cambio
  persistido.

### D8. Aislamiento de los tests de integración

- **Fixture `db_session`:**
  - Abre una conexión y una transacción externa.
  - Crea una `Session` con `join_transaction_mode="create_savepoint"`. Así,
    el `session.rollback()` que hace el test, en el papel de caller, revierte
    solo lo que hizo el código bajo prueba.
  - El teardown revierte la transacción externa. No queda nada en la base y
    no hay que borrar nada.
- **Datos propios.** La base de desarrollo puede tener filas propias. Los
  tests crean sus items con una categoría única por test (sufijo aleatorio).
  Las aserciones sobre listas filtran por esa categoría, o verifican
  presencia y ausencia, nunca igualdad contra la lista completa.
- **La fixture del escenario de `DAT-4`** inserta un `Order` (`PICKUP`,
  `RECEIVED`) y un `OrderItem` con `unit_price_snapshot` mediante `insert()`
  de Core sobre las tablas. No modifica los modelos.
- **Excepción:** el test de concurrencia (D4) es el único que commitea y
  limpia sus propias filas.

### Evaluación de los modelos existentes (SDD-7)

| Hallazgo | Regla | Veredicto |
|---|---|---|
| `price` `Numeric(12,2)` con `CHECK >= 0` | DAT-8 | Cumple. |
| `created_at` `TIMESTAMPTZ`, `server_default=now()` | GEN-6 | Cumple. |
| `customers.phone` con índice único | Escenario 12 | Cumple; es la base de D4. |
| `phone` `String(30)` sin `CHECK` de forma canónica | — | No viola ninguna regla. La forma canónica la garantiza el servicio. Un `CHECK` en la base sería más fuerte, pero requiere migrar: queda propuesto como deuda, no se hace acá. |
| `available` con default solo en Python, sin `server_default` | DAT-5 | No afecta a este change, que no da altas. Lo toma el change de carga del menú. |
| `name` sin `CHECK` de no vacío | — | La forma la valida `MenuItemUpdate` (D5). No es violación. |
| **`estimated_time_min` admite `NULL`** | ORD-12 | **Tensión, no violación literal.** ORD-12 calcula el ETA con "el mayor `estimated_time_min` del carrito", y un `NULL` lo deja indefinido. Arreglarlo es un `NOT NULL`, o sea una migración, que acá es non-goal. Por SDD-2 no se migra. El escenario quedó aprobado por Lautaro el 10/10 (requirement "Estimated time may be unknown on existing items"): el tiempo se lee como ausente, y una edición no puede volver a dejarlo en `NULL` porque `MenuItemUpdate` rechaza el `null` explícito como error de forma (D5). **El `NOT NULL` de `menu_items.estimated_time_min` es prerrequisito del change de pedidos por ORD-12**: ese change no puede calcular `estimated_kitchen_ready_at` sin él. Se registra como deuda en `ESTADO.md` (tarea 6.4). |
| `MenuItem` sin `updated_at` | PAN-4 | La auditoría es del panel; non-goal. |
| `Order.customer` declarada dos veces; `chk_order_status` con `CANCELLED` | ORD-3, D-10 | Fuera de alcance (`Order` es non-goal). `configure_mappers()` pasa igual. |

Ningún hallazgo obliga a tocar un modelo para cumplir los escenarios pedidos.

## Risks / Trade-offs

- **[Riesgo] Un caller en `repeatable read` o `serializable` rompe D4** con un
  error de serialización en la carrera. → El docstring del repositorio lo
  dice. El change del webhook fija el nivel de aislamiento cuando defina la
  transacción. Hoy el default de PostgreSQL es `read committed`, y nada del
  repo lo cambia.
- **[Riesgo] El orden depende de la collation de la base.** Una instancia
  creada con `C` ordenaría distinto. → Los tests usan nombres cuyo orden es
  igual en `C` y en `en_US`, salvo un caso con `Ñ` que fija la collation
  esperada y documenta qué asume. El `docker-compose` de otro change debería
  fijar la collation.
- **[Riesgo] Un `MenuItemUpdate` construido a mano en un handler** convierte
  un error de forma en un `500`, porque el contrato solo traduce
  `RequestValidationError`. → Queda escrito en D5 como requisito del change
  del panel. Si ese change necesita construirlo a mano, la solución es sumar
  `ValidationError` al contrato de errores en ese change, con su spec.
- **[Trade-off] Dos capas de validación del mismo campo** (por ejemplo, el
  tipo del precio en Pydantic y el signo en el servicio). Hay que saber dónde
  vive cada chequeo. → Las dos tablas de D5 lo listan campo por campo, y los
  tests de forma y de reglas están en archivos separados.
- **[Trade-off] El fake en memoria puede divergir del repositorio real.** →
  Los dos cumplen el mismo `Protocol` bajo mypy, y el orden y los filtros se
  prueban también contra PostgreSQL.
- **[Riesgo] Datos de desarrollo con teléfonos no canónicos.** Un número
  guardado como `+54 9 ...` no se encuentra nunca con el formato canónico, y
  generaría un customer paralelo. → No hay datos reales todavía. Si los
  hubiera, normalizarlos es una migración de datos de otro change.
- **[Trade-off] `set_available` explícito en lugar de toggle** se aparta de
  la letra de DAT-5. → Es una interpretación aprobada y justificada en D6.
  El ajuste de redacción de la regla queda sugerido, sin aplicar.

## Migration Plan

No hay migración ni cambio de esquema. El deploy es solo código. Para
revertir, se borran `backend/app/domain/`, `backend/app/db/` y los tests
nuevos. Nada más depende de ellos todavía.

## Decisiones resueltas antes de aprobar

Las tres interpretaciones que la primera versión dejaba abiertas las resolvió
Lautaro el 10/10. No queda ninguna pregunta abierta.

1. **GEN-1:** lectura estricta. Los repositorios van a
   `backend/app/db/repositories/` y el test de AST cubre todo `app.domain`
   (D1).
2. **`estimated_time_min` nullable:** se acepta el escenario, sin migrar. El
   `NOT NULL` es prerrequisito del change de pedidos (ORD-12) y es deuda en
   `ESTADO.md` (tabla SDD-7).
3. **`set_available` explícito:** es una interpretación de DAT-5,
   justificada en D6.
4. **`update_item` recibe `MenuItemUpdate`, no un `Mapping`:** la forma
   la valida Pydantic y las reglas el servicio (D5).
