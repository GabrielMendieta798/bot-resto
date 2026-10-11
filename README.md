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
