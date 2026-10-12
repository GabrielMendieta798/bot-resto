# BOT-RESTO

WhatsApp bot for restaurants built with FastAPI and PostgreSQL.

## Bitácora

### 02–03/10/2026 — `add-application-skeleton`

**Qué se hizo.** La aplicación pasó a existir: `backend/app/main.py` con lifespan, `GET /health` (200, o 503 con cuerpo si la base está caída), routers vacíos del webhook y del panel en prefijos disjuntos, configuración validada al arrancar (entorno + `config/restaurant.yaml`, `messages.yaml` y `http_errors.yaml`), formato de error uniforme, logging JSON con enmascarado de teléfonos y cliente HTTP saliente con timeouts. Toolchain: dependencias pineadas, ruff, mypy estricto, pytest con suites `unit` e `integration`. No cubre ningún caso de uso.

**Prompt usado.** `/opsx:propose` con alcance, 11 escenarios obligatorios, non-goals y restricciones de `.instructions.md`; después `/opsx:apply` por bloques (grupo 1; grupos 2 a 5; grupos 6 a 8), con `run-verify` después de cada tarea.

**Ajustes a mano sobre la spec.**
- Sin override de mypy para `app.models.*`: los modelos pasaban estricto igual.
- Textos de error HTTP en `http_errors.yaml`, separados del copy del cliente en `messages.yaml`, que tiene solo comentarios mientras no haya copy.
- Tres escenarios agregados durante el apply, cada uno aprobado antes de implementarse:
  - httpx no loguea URLs.
  - Los errores inesperados se loguean una vez y sin datos del cliente.
  - Los mensajes de excepción no llevan datos del cliente.

**Lo que corrigió el loop de `run-verify` y de la verificación.**
- **Tests que leían el `.env` real.** Un test que borraba `APP_ENV` del entorno igual levantaba la app, porque la clave volvía desde el `.env` del desarrollador. Se cortó esa lectura en la fixture de configuración.
- **Filtro de rutas vacío.** FastAPI 0.142 envuelve los routers incluidos en un objeto privado y el filtro por `APIRoute` devolvía una lista vacía. Los tests ahora recorren los routers propios y comparan contra el esquema OpenAPI.
- **Fuga de datos de clientes en el log del 500** (`@security`, reproducido con uvicorn real). Un `IntegrityError` con una dirección como parámetro dejaba dos records con la dirección: el de nuestro handler y el que uvicorn agregaba al re-levantarse la excepción. Ahora deja un solo record y sin la dirección:
  - un middleware propio reemplaza al handler de `Exception`;
  - el engine usa `hide_parameters=True`;
  - los errores de SQLAlchemy y de validación se loguean sin mensaje en cualquier eslabón de la cadena.

**Verificación.** `run-verify` en verde: 92 tests unitarios y 1 de integración contra PostgreSQL 16. Verificación funcional con `@api-explorer`: 8 PASS, 0 FAIL. `@security` en tres pasadas; en la última, 0 altos y 0 medios. Los bajos que quedaron están anotados como deuda para los changes que los disparan.

**Casos de uso cubiertos.** Ninguno, por diseño.

<<<<<<< HEAD
### 11/10/2026 — `migrate-identifiers-to-bigint`

**Qué se hizo.** Las seis PK internas, sus seis FK dependientes y las seis secuencias de PostgreSQL quedaron en `BIGINT`. Los modelos declaran `BigInteger` explícitamente y conservan `int` en Python. Las migraciones incluyen guards que rechazan un downgrade cuando una PK o secuencia ya supera el rango de `INTEGER`. No cambió ningún contrato HTTP ni regla de negocio.

**Prompt usado.** “Quiero que completemos los tasks de migrate identifiers en el código”. El trabajo continuó task por task contra el change aprobado `migrate-identifiers-to-bigint`, ejecutando `run-verify` antes de marcar cada bloque.

**Ajustes realizados durante el apply.**
- Se creó `bot_resto_test`, una base PostgreSQL dedicada a migraciones destructivas. La fixture confirma el sufijo `_test`, reinicia solamente su esquema y nunca altera `bot_resto`.
- La preparación local se hace una sola vez con `sudo -u postgres createdb --owner=bot_resto_user bot_resto_test`; no requiere otorgar `CREATEDB` al rol de la aplicación.
- Se comprobó el contrato completo de PK, FK, acciones `ON DELETE`, índices y unicidad antes y después del upgrade.
- Las secuencias se llevaron al límite de `INTEGER`; las seis tablas generaron automáticamente el ID `2.147.483.648`.
- Se retiró de `alter_column` el argumento `autoincrement=True`, que Alembic ignora y advierte que solo aplica a MySQL. La autogeneración real quedó demostrada por los tests de PostgreSQL.
- Los downgrades se verifican por revisión: columnas (`88d85f44fb7d`) y secuencias (`c3a7b9d2e641`). No se reordenó el historial de migraciones.

**Lo que corrigió el loop de `run-verify`.**
- El rol `bot_resto_user` no tenía `CREATEDB`, como corresponde por mínimo privilegio. Se reemplazó la creación dinámica de bases por una base de test fija y protegida.
- `psycopg` rechazó inicialmente la URL SQLAlchemy `postgresql+psycopg://`; la fixture la normaliza a `postgresql://` solamente para la conexión directa de limpieza.
- Pytest podía incluir la contraseña en el reporte de un test fallido porque el fixture devolvía el DSN como texto. Ahora entrega un objeto `URL` de SQLAlchemy, cuyo `repr` enmascara el secreto, y conserva la cadena completa solo dentro de la fixture.
- PostgreSQL expone `conversations_customer_id_key` como restricción única y como índice físico. El contrato del test ahora protege ambas representaciones.
- Ruff detectó a tiempo bloques de tests desplazados durante la edición; se reubicaron antes de ejecutar la suite funcional.

**Verificación.** `run-verify` en verde: Ruff check y format, mypy estricto sobre 24 archivos, 92 tests unitarios y 8 de integración. Siete escenarios de integración prueban upgrade, datos relacionados, constraints, generación de IDs más allá de `INTEGER`, enforcement de FK, downgrade válido y rechazo atómico por overflow.

**Casos de uso cubiertos.** Ninguno de negocio. Se cubre la capacidad técnica de almacenamiento y generación de identificadores internos en PostgreSQL.
=======
### 10/10/2026 — `add-menu-and-customer-repositories`

**Qué se hizo.** La capa de datos y servicios de UC-03 (ver el menú por categorías), UC-17 (marcar un item agotado o disponible) y UC-18 (editar nombre, descripción, precio y tiempo estimado), más obtener o crear un customer por teléfono. Servicios y schemas en `backend/app/domain/menu/` y `backend/app/domain/customers/`; repositorios en `backend/app/db/repositories/`. Los repositorios no commitean (la transacción es de quien llama), los servicios no ven la `Session`, y un mismo número nunca produce dos customers aunque lleguen dos mensajes a la vez (índice único + `INSERT ... ON CONFLICT DO NOTHING`). Sin endpoints, pantallas ni migraciones. Hecho en Claude Code (extensión de VS Code); los comandos `/opsx:*` no estaban instalados en la sesión, así que se siguió el mismo flujo con el CLI de OpenSpec 1.7.0. Los commits los hizo Lautaro, tarea por tarea.

**Prompt usado.** `/opsx:propose` con alcance, 16 escenarios obligatorios (dos propios: creación concurrente y repositorio que nunca commitea), non-goals y restricciones de `.instructions.md`: [COMPLETAR: prompt original de propose]. Después, dos rondas de decisiones sobre la propuesta y `/opsx:apply` por grupo, con `run-verify` después de cada tarea y el commit a cargo de Lautaro.

**Ajustes a mano sobre la spec.**
- **Lectura estricta de `GEN-1`:** los repositorios pasaron de `domain/<modulo>/repository.py` a `backend/app/db/repositories/`, y el test de AST recorre todo el paquete `domain`.
- **`MenuItemUpdate` tipado en lugar de `Mapping`**, con el criterio forma (Pydantic: tipo, largo, nulidad, campos desconocidos) contra reglas (servicio: límites de valor y de negocio). Un `null` explícito en el tiempo estimado pasó a ser error de forma.
- **Precio como texto decimal exacto (`SDD-2`, durante el apply de 2.1):** FastAPI valida el payload en modo Python después de `json.loads`, y con `strict` puro ningún request podía traer un precio. Ahora precio y tiempo aceptan texto exacto (`"9200.00"`, `"25"`) y siguen rechazando `float` y `bool` (`DAT-8`). Escenario aprobado antes de implementarlo.
- **Regrupado de tareas** (grupos 2 a 5) para que cada tarea entregue el comportamiento junto con sus tests, y cada repositorio con sus tests de integración.
- **`set_available` explícito** como interpretación de `DAT-5` ("togglea"), y el `NOT NULL` de `estimated_time_min` registrado como prerrequisito del change de pedidos.

**Lo que corrigió el loop de `run-verify` y de la verificación.**
- **Ningún request podía traer un precio.** `test_valid_payload_reaches_the_handler` (`tests/unit/test_menu_schemas.py`) devolvió 400 con `{"price": "9200.00"}`: `strict=True` rechazaba el `str` que entrega `json.loads`. Se frenó la tarea, se aprobó el escenario nuevo y `backend/app/domain/menu/schemas.py` sumó validadores `mode="before"` con un patrón ASCII explícito (el parser de Pydantic aceptaba `"١٢٣"` y `"1_000"`).
- **mypy contra "opcional pero no nulo".** El plugin de Pydantic rechazó `name: str = Field(default=None)` en `domain/menu/schemas.py`; quedó `X | None = None` más un validador que rechaza el `null` explícito.
- **`Row[Any]` en SQLAlchemy 2.1.** mypy rechazó el helper de `db/repositories/menu.py` porque `Row` es variádico; pasó a recibir `RowMapping`.
- **Orden con Ñ.** El test de collation esperaba "Nuez, Ñoquis" y PostgreSQL con `en_US.utf8` devolvió "Ñoquis, Nuez" (la Ñ como N acentuada). Se corrigió la expectativa y el design D7; la collation española quedó como deuda (D-33).
- **Ruff:** S603 en `tests/unit/test_domain_boundaries.py` (`subprocess` con script constante, `noqa` justificado), RUF003 por un dígito árabe en un comentario de `domain/customers/service.py`, un `noqa` sin uso y un import sin usar.

**Verificación.** `run-verify` en verde: ruff, format, mypy estricto (35 archivos), 242 tests unitarios y 34 de integración contra PostgreSQL 16. La suite de integración se corrió dos veces seguidas (la segunda con los archivos en orden inverso) y dejó 0 filas. Los tests de concurrencia pasaron 10 de 10 corridas. Pruebas de mutación: con `SELECT` antes del `INSERT` fallan los tests de carrera; con un `commit()` en el repositorio fallan los de rollback y el chequeo de fronteras. Auditoría: `/security-review` y un subagente independiente de solo lectura (en lugar de `@security`, no disponible en la sesión); 0 altos, 0 medios, 6 bajos anotados como deuda (D-24 a D-29).

**Casos de uso cubiertos.** La capa de dominio de UC-03, UC-17 y UC-18, sin pantallas ni guion de WhatsApp, y la identificación del customer por teléfono que usan todos los flujos.
>>>>>>> origin/develop
