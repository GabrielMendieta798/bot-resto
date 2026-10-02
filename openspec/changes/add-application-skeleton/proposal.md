# Change: Add application skeleton

## Why

El repositorio tiene modelos, migraciones y un repositorio de idempotencia, pero
no tiene una aplicación que se pueda levantar: no existe `backend/app/main.py`,
no hay tests, ni linter, ni typecheck. Sin eso nadie puede ejecutar ni verificar
nada (`VER-1`), y los tres changes ya propuestos
(`add-whatsapp-message-idempotency`, `allow-order-additions`,
`migrate-identifiers-to-bigint`) no pueden cerrar porque sus tareas de
verificación no tienen dónde correr.

Este change no cubre ningún caso de uso. Construye el piso sobre el que se
apoyan todos los demás.

## What Changes

- **Aplicación FastAPI** en `backend/app/main.py`, con lifespan y con dos routers
  vacíos montados en prefijos propios y disjuntos: uno para el webhook y otro
  para el panel (`API-4`).
- **Health check** en `GET /health` que informa el estado de la aplicación y la
  conectividad con la base, sin exponer cadena de conexión, usuario, host,
  versiones ni nombres de tablas.
- **Configuración validada al arrancar** (`VAL-4`, `TXT-3`): las settings de
  entorno se amplían y se suman `config/restaurant.yaml`,
  `config/messages.yaml` (solo copy de cara al cliente) y
  `config/http_errors.yaml` (textos de las respuestas de error), cada uno
  validado contra un modelo tipado. Clave
  faltante o YAML malformado ⇒ la aplicación no levanta, y el error nombra la
  clave sin revelar ningún valor. Los dos YAML se crean con defaults
  documentados y un encabezado que aclara que los valores definitivos salen de
  las cinco preguntas al dueño del local (`GEN-7`).
- **`echo` del engine por configuración**, apagado por defecto y prohibido en
  producción (`DAT-10`). **BREAKING** para quien dependiera del SQL impreso en
  consola: hoy está siempre encendido.
- **Jerarquía de excepciones** sin dependencias de framework, y **exception
  handler global** que las traduce a los códigos de `API-3` con el formato
  uniforme de `API-2`. Los errores de validación de payload pasan de `422` (el
  default de FastAPI) a `400`. Ningún stacktrace sale hacia afuera.
- **Logging estructurado** en JSON con enmascarado de números de teléfono
  (`SEC-3`).
- **Cliente HTTP centralizado** sobre httpx con timeouts explícitos, para que lo
  use después el adapter de WhatsApp. Sin lógica de WhatsApp.
- **Toolchain** (`SEC-5`, `VER-1`): versiones pineadas en `pyproject.toml` y
  `uv.lock` regenerado y commiteado; se quita `pytest-asyncio` (`DAT-3`); se
  agregan ruff y mypy estricto; pytest con markers `unit` e `integration`.
- **Tests**: `tests/unit/` y `tests/integration/` con sus `conftest.py`, un test
  de humo del health check y un test por cada escenario de las specs.
- **`.env.example`** completo, con todas las claves que esperan las settings y
  ningún valor real (`SEC-1`).

Nota sobre el estado de partida: `uv.lock` ya está trackeado desde el commit
`2288273`, pero resuelve dependencias sin pinear. Este change pinea las
versiones y lo regenera; no lo crea de cero.

## Capabilities

### New Capabilities

- `application-runtime`: arranque de la aplicación, montaje de routers en
  prefijos separados y health check.
- `runtime-configuration`: carga y validación tipada de entorno y YAML,
  fail-fast al arrancar, y control del logging de SQL.
- `error-contract`: traducción de excepciones a códigos HTTP y formato de error
  uniforme, sin filtrar detalles internos.
- `structured-logging`: logs estructurados con enmascarado de datos personales.
- `outbound-http-client`: cliente HTTP saliente con timeouts explícitos.
- `development-toolchain`: dependencias pineadas, lint, typecheck y suites de
  tests separadas por tipo.

### Modified Capabilities

Ninguna. `openspec/specs/` está vacío.

## Impact

- **Código nuevo**: `backend/app/main.py`, `backend/app/api/` (health, errores,
  routers vacíos), `backend/app/core/exceptions.py`,
  `backend/app/core/logging.py`, `backend/app/integrations/http_client.py`,
  `config/restaurant.yaml`, `config/messages.yaml`,
  `config/http_errors.yaml`, `tests/`.
- **Código modificado**: `backend/app/core/config.py`,
  `backend/app/core/database.py`, `pyproject.toml`, `uv.lock`,
  `.env.example`. Los nombres que importa `backend/alembic/env.py` (`settings`,
  `Base`) siguen existiendo, para no tener que tocar Alembic.
- **Dependencias**: se suman PyYAML, ruff, mypy y los stubs de tipos que haga
  falta; sale `pytest-asyncio`.
- **Operación**: la app exige los tres YAML de `config/` y
  `APP_ENV`. Alembic, que importa las settings, también pasa a exigir los YAML
  válidos para correr.
- **Tests de integración**: necesitan una PostgreSQL real alcanzable por
  `DATABASE_URL`. El `docker-compose` que la levanta es de otro change; hasta
  entonces la base la provee el desarrollador.

## Non-goals

- Cualquier caso de uso: pedidos, reservas, conversación, menú.
- Tocar, mover o renombrar `backend/app/models/`.
- Generar migraciones o tocar `backend/alembic/`.
- El repositorio de idempotencia y las tareas de los tres changes ya
  propuestos.
- PyWa y cualquier lógica de WhatsApp, incluida la verificación de firma.
- `docker-compose` y CI.
- Reestructurar el layout hacia `domain/<modulo>/`.
- Autenticación del panel, sesiones y CSRF.
