# Design: Add application skeleton

## Context

Motivación en `proposal.md`. Lo que condiciona el enfoque es el código que ya
existe y que este change no puede tocar:

- `backend/alembic/env.py` hace `from app.core.config import settings` y
  `from app.core.database import Base`. Como Alembic es non-goal, esos dos
  nombres tienen que seguir existiendo con el mismo significado.
- `config.py` hoy instancia `Settings()` al importarse, y `database.py` crea el
  engine con `echo=True` también al importarse. Cualquier `import` dispara la
  lectura del `.env`, lo que hace imposible testear "falta una clave" sin
  manipular el entorno global del proceso de tests.
- El código vive en `backend/` y se importa como `app.*` (Alembic corre con
  `prepend_sys_path = .` desde `backend/`). `backend/app/` y `backend/app/core/`
  no tienen `__init__.py`: hoy son namespace packages.
- La skill `run-verify` fija los comandos: `ruff check .`,
  `ruff format --check .`, `mypy backend/app`, `pytest tests/unit`,
  `pytest tests/integration`, todos desde la raíz del repo.
- Stack sync (`DAT-3`): path operations `def` (`DAT-1`).

## Goals / Non-Goals

**Goals:**

- Que `uv run uvicorn app.main:app` (desde `backend/`) levante, y que no levante
  con config rota.
- Que la verificación de `VER-1` exista y corra en verde.
- Que las decisiones de contrato (formato de error, health, logging) queden
  fijadas antes de que el change 00 empiece a escribir endpoints.

**Non-Goals (de diseño, además de los del proposal):**

- Métricas, tracing o un endpoint de readiness separado del de liveness.
- Request IDs o correlación entre logs.
- Reintentos o circuit breaker en el cliente HTTP.
- Ocultar `/docs` y `/openapi.json` en producción (ver Open Questions).

## Decisions

### D1. Layout de los archivos nuevos

```
backend/app/
  __init__.py                 (nuevo, vacío)
  main.py                     create_app() + app = create_app()
  api/
    __init__.py
    health.py                 GET /health
    errors.py                 exception handlers + mapeo categoría → status
    webhook.py                APIRouter vacío, prefijo /webhook
    panel.py                  APIRouter vacío, prefijo /panel
  core/
    __init__.py               (nuevo, vacío)
    config.py                 (reescrito)
    database.py               (reescrito)
    exceptions.py             jerarquía de errores, sin FastAPI
    logging.py                formatter JSON + filtro de enmascarado
  integrations/
    http_client.py            cliente httpx
config/
  restaurant.yaml             valores de negocio (GEN-7)
  messages.yaml               solo copy de cara al cliente, lo edita el dueño (TXT-2)
  http_errors.yaml            textos de las respuestas de error HTTP (API-2)
tests/
  conftest.py                 aplica el marker según la carpeta
  unit/conftest.py
  integration/conftest.py
```

`app/api/` agrupa la capa HTTP. El change de dominio puede mover los routers
a cada módulo; mientras tanto la capa HTTP queda en un solo lugar y separada
del dominio (`GEN-1`). Los `__init__.py` nuevos convierten `app` y `app.core`
en paquetes regulares, que es lo que mypy estricto necesita para resolver
módulos sin ambigüedad. `app/models/` no recibe nada.

*Alternativa descartada:* poner los routers en `app/integrations/whatsapp/` y
`app/panel/`. Adelanta decisiones del layout de dominio, que es non-goal.

### D2. Configuración: carga perezosa, validación completa, errores sin valores

Tres modelos Pydantic:

- `Settings(BaseSettings)` — entorno. Claves:

  | Clave                            | Requerida | Default                    |
  |----------------------------------|-----------|----------------------------|
  | `APP_ENV`                        | sí        | — (`development`, `test`, `production`) |
  | `DATABASE_URL`                   | sí        | —                          |
  | `DATABASE_ECHO`                  | no        | `false`                    |
  | `HEALTH_DB_TIMEOUT_SECONDS`      | no        | `2`                        |
  | `LOG_LEVEL`                      | no        | `INFO`                     |
  | `HTTP_CONNECT_TIMEOUT_SECONDS`   | no        | `5`                        |
  | `HTTP_READ_TIMEOUT_SECONDS`      | no        | `10`                       |
  | `HTTP_WRITE_TIMEOUT_SECONDS`     | no        | `10`                       |
  | `HTTP_POOL_TIMEOUT_SECONDS`      | no        | `5`                        |
  | `RESTAURANT_CONFIG_PATH`         | no        | `<repo>/config/restaurant.yaml` |
  | `MESSAGES_CONFIG_PATH`           | no        | `<repo>/config/messages.yaml`   |
  | `HTTP_ERRORS_CONFIG_PATH`        | no        | `<repo>/config/http_errors.yaml` |

  `APP_ENV` no tiene default a propósito: si lo tuviera, un deploy que se
  olvida de setearlo quedaría en `development` y el guard de `DAT-10` no
  serviría. `DATABASE_URL` es `str` con `Field(repr=False)`, así el `repr` de
  las settings nunca muestra el valor. No es `SecretStr` porque
  `backend/alembic/env.py` (non-goal) hace `str(settings.database_url)`, y con
  `SecretStr` eso devolvería `**********`. `env_ignore_empty=True`: una clave
  vacía (`CLAVE=`, como en `.env.example`) cuenta como no definida.
  Un `model_validator` rechaza `DATABASE_ECHO=true` con `APP_ENV=production`.
  Los timeouts técnicos tienen default en código porque no son valores de
  negocio (`GEN-7` enumera cuáles lo son).

- `RestaurantConfig` — `restaurant.yaml`. Cubre lo que enumera `GEN-7`:
  `timezone` (validada con `zoneinfo`), `opening_hours` por día de semana como
  lista de franjas `{opens, closes}` (horario partido = dos franjas),
  `delivery.zones` con `name` y `fee: Decimal` (`DAT-8`), `cart.timeout_minutes`,
  `conversation.inactivity_timeout_minutes`, `conversation.max_retries`,
  `reservations.max_days_ahead`, `reservations.max_party_size`,
  `reservations.escalation_minutes`. `extra="forbid"` en todos los niveles para
  que un typo sea error y no una clave ignorada. Solo valida **forma**
  (`VAL-3`): tipos, positivos, `opens < closes` dentro de una franja. Ninguna
  regla de negocio.

- `MessagesConfig` — `messages.yaml`. Solo copy de cara al cliente: es el
  archivo que abre el dueño del local (`TXT-2`) y no tiene que encontrarse con
  textos internos. `extra="forbid"` hace que una sección de errores HTTP puesta
  ahí por error rompa el arranque. Este change no agrega copy; los changes de
  conversación la suman. Mientras tanto el archivo tiene solo un encabezado de
  comentarios (qué va ahí, que los errores internos viven en
  `http_errors.yaml`, que el copy llega con los changes de conversación).
  YAML de puros comentarios parsea como `None`; solo para este archivo se lee
  como mapping vacío. Es más legible para el dueño que un `{}` literal.

- `HttpErrorsConfig` — `http_errors.yaml`. Un texto por cada `message_key` de
  la jerarquía de errores (D5). Lo mantiene el equipo, no el dueño.

`load_config() -> AppConfig` arma los cuatro y es la única puerta de entrada.
`get_config()` la envuelve en `functools.lru_cache`. Para no tocar
`alembic/env.py`, `config.py` expone `settings` como atributo perezoso de módulo
(`__getattr__` de PEP 562) que devuelve `get_config().settings`. Importar el
módulo ya no lee nada; leer `settings` sí.

**Errores sin valores.** El `ValidationError` de Pydantic incluye
`input_value=...` en su `str()`, y la excepción encadenada se imprime en el
traceback. Por eso:

1. Los modelos usan `hide_input_in_errors=True`.
2. `load_config()` captura `ValidationError` y `yaml.YAMLError`, arma un
   `ConfigError` propio con solo `fuente + ruta punteada + tipo de error`, y lo
   levanta con `from None` para cortar la cadena.
3. Para YAML se reporta `archivo, línea, columna` desde `problem_mark`; nunca el
   `str()` del error, porque PyYAML incluye un snippet del contenido.

`yaml.load` con `_ConfigLoader`, una subclase de `SafeLoader` que solo agrega
el constructor de `Decimal`; nunca el loader completo, que puede instanciar
objetos arbitrarios. Los tags `!!python/...` no tienen constructor y fallan
como YAML inválido.

*Alternativa descartada:* `pydantic-settings` con `YamlConfigSettingsSource`.
Mezcla entorno y YAML en un solo modelo, lo que permitiría que un secreto
termine en un YAML commiteado, y sus errores no tienen el control fino de (2) y
(3).

### D3. Fail-fast: dónde se valida

`main.py` hace `app = create_app()`, y `create_app()` llama a `get_config()`
antes de construir la aplicación. Una config inválida rompe el import de
`app.main`, así que uvicorn termina antes de abrir el puerto. Si la validación
viviera en el lifespan, uvicorn ya habría bindeado el puerto y un healthcheck
externo podría ver la app "arriba" un instante.

En el mismo punto se valida que toda clave de texto referenciada exista
(`TXT-3` aplicado a los dos archivos de textos): cada clase de error declara su
`message_key`; la jerarquía registra todas las claves al definirse
(`__init_subclass__`), y `create_app()` verifica que todas existan en
`http_errors.yaml`. Una clave faltante es `ConfigError`. Cuando los changes de
conversación referencien claves de `messages.yaml`, se registran y verifican
con el mismo mecanismo.

### D4. Base de datos: engine construido, no importado

`database.py` mantiene `Base` igual (Alembic lo importa) y reemplaza el engine
global por `build_engine(settings) -> Engine` y
`build_session_factory(engine)`. `echo=settings.database_echo`. El engine se
crea en `create_app()` y se guarda en `app.state`; el lifespan hace
`engine.dispose()` al apagar.

La conexión no se prueba al arrancar: si la base está caída la app levanta y el
health lo informa (escenario de base caída). Que la app no levante por una
base caída transformaría un corte de red de cinco segundos en un loop de
reinicios.

`connect_args={"connect_timeout": ...}` toma `HEALTH_DB_TIMEOUT_SECONDS`, y el
pool usa `pool_pre_ping=True` para no devolver conexiones muertas tras un corte.

`hide_parameters=True`: sin esto, todo error de SQLAlchemy incluye en su texto
los parámetros de la sentencia (`[parameters: {...}]`), o sea direcciones y
cuerpos de mensaje apenas haya datos reales (`SEC-3`).

### D5. Jerarquía de errores y su traducción

`core/exceptions.py` no importa FastAPI ni Starlette (`GEN-1`):

```
AppError                       code="internal_error"   message_key="internal_error"
├── InvalidInputError          code="invalid_input"    (+ field opcional)
├── NotAuthenticatedError      code="not_authenticated"
├── PermissionDeniedError      code="permission_denied"
├── NotFoundError              code="not_found"
├── ConflictError              code="conflict"
│   └── InvalidStateTransitionError  code="invalid_state_transition"
├── ConfigError                (no llega nunca a HTTP: rompe el arranque)
└── OutboundHttpError
    └── OutboundTimeoutError
```

Los códigos HTTP **no** viven en las excepciones: viven en `api/errors.py` como
un dict `{NotFoundError: 404, ...}`, resuelto recorriendo el MRO. Así una
subclase nueva hereda el código de su ancestro mapeado, y el dominio no sabe que
existe HTTP. `OutboundHttpError` no está en el mapa: si un adapter la deja
escapar, es un 500 genérico. Decidir si corresponde 502/503 es del change que
introduzca el primer adapter.

Handlers registrados:

| Excepción                              | Respuesta |
|----------------------------------------|-----------|
| `AppError` y subclases mapeadas        | status del mapa, mensaje de `http_errors.yaml` |
| `RequestValidationError`               | 400 `invalid_input`, `field` = último elemento de `loc` del primer error |
| `StarletteHTTPException`               | su status, `code` derivado: 401 `not_authenticated`, 403 `permission_denied`, 404 `not_found`, 405 `method_not_allowed`, 409 `conflict`; otro 4xx `invalid_input` |
| cualquier otra excepción               | middleware `UnhandledErrorMiddleware`: 500 `internal_error`, un único log |

El mensaje sale de `http_errors.yaml`, nunca de `str(exc)`: el texto de una
excepción lo escribe un desarrollador para otro desarrollador y puede contener
SQL o datos del cliente. Tampoco sale de `messages.yaml`: ese archivo es del
dueño del local y solo tiene copy de cara al cliente. Las claves de
`message_key` siguen la forma `<code>` plano (`not_found`, `conflict`, …) dentro
de `http_errors.yaml`, para que el archivo no repita un prefijo `errors.` que
ya está en su nombre. El path se loguea sin query string porque la query del
webhook de verificación de Meta trae el verify token (`SEC-2`).

**Errores inesperados: middleware propio, no handler de `Exception`.** Un
handler registrado para `Exception` lo ejecuta `ServerErrorMiddleware` de
Starlette, que devuelve nuestra respuesta y después **re-levanta** la
excepción; uvicorn la atrapa y loguea el traceback completo por segunda vez
("Exception in ASGI application"), por fuera de nuestro control. Con datos de
clientes eso es una fuga, no solo ruido (hallazgo medio de `@security`,
reproducido con uvicorn real). `UnhandledErrorMiddleware` es un middleware ASGI
puro que se ubica entre `ServerErrorMiddleware` y `ExceptionMiddleware`: atrapa
lo que los handlers no tradujeron, loguea una vez, responde el 500 uniforme y
no re-levanta. Si la respuesta ya había empezado a enviarse (streaming) o ya
terminó (`BackgroundTasks`, el mecanismo natural de "enviar después del
commit"), no hay 500 posible: loguea una vez y retorna sin re-levantar; el
servidor cierra la conexión sin volver a loguear la excepción.

Cubre solo lo que corre por dentro. `add_middleware` inserta al principio de la
pila, así que un middleware agregado después (CORS, sesión del panel en el
change 08) queda por fuera y sus errores vuelven al camino de
`ServerErrorMiddleware` + uvicorn. Un test fija que este middleware sea el más
interno; el change que agregue otro middleware tiene que decidir cómo cubre
sus errores.

**Qué se loguea de un error inesperado.** Siempre método, path sin query,
`error_type` y el stack. Para la mayoría de las excepciones, el traceback
completo con su mensaje (teléfonos enmascarados). Si en la **cadena** de la
excepción (`__cause__`, y `__context__` salvo que esté suprimido) aparece una
de estas familias, cuyo texto transporta datos del cliente por construcción,
no se loguea ningún mensaje de la cadena: solo `error_chain` (los tipos), los
frames de cada eslabón (`stack`) y metadatos seguros.

- `SQLAlchemyError` entera: además de los parámetros (ya ocultos por
  `hide_parameters`), el driver agrega `DETAIL: Failing row contains (...)`, y
  una `PendingRollbackError` repite el error original en su mensaje. Metadatos:
  `sqlstate` y nombre de constraint.
- `pydantic.ValidationError`: incluye `input_value`. Va a aparecer cuando el
  webhook valide a mano el cuerpo crudo después de verificar la firma.
- `ResponseValidationError` de FastAPI: incluye el `input` rechazado.
  Metadato: cantidad de errores.

Recorrer la cadena importa porque el patrón más común en un repositorio es
`except IntegrityError: raise AlgoMasClaro(...)`: sin `from None`, el error del
driver queda en `__context__` y el traceback lo imprime entero.

Que el resto de los mensajes sí se logueen es una decisión: sin ellos se
depura a ciegas. Lo que la sostiene es el requirement de `structured-logging`
"Exception messages carry no customer data": un `raise` no lleva datos del
cliente en su mensaje, y la auditoría de cada change lo revisa.

*Alternativa descartada:* `status_code` como atributo de clase en cada
excepción. Es más corto, pero acopla el dominio al transporte HTTP.

### D6. Logging estructurado sin dependencias nuevas

`logging` de la stdlib con:

- `JsonFormatter`: una línea JSON por record con `timestamp` (UTC, ISO 8601),
  `level`, `logger`, `message`, los `extra` del record y `exc_info` formateado.
- `PhoneMaskingFilter` instalado en el **handler** del root logger, no en
  loggers individuales, para cubrir también uvicorn, SQLAlchemy y httpx. Actúa
  sobre el mensaje ya interpolado, sobre los `extra` (valores y claves, en
  cualquier nivel de anidamiento) y sobre el texto del stacktrace.

Regla de enmascarado: toda secuencia de 8 o más dígitos, admitiendo `+`
inicial y separadores (espacio, guion, punto, paréntesis) entre ellos, se
reemplaza por `*` salvo los últimos 4 dígitos. `5491122334455` →
`*********4455`. Ocho dígitos es el número local argentino más corto sin
característica; por debajo de eso no se enmascara, para no destruir ids de
pedido ni cantidades.

`configure_logging(settings)` corre en `create_app()`, y es idempotente (no
duplica handlers si se llama dos veces, cosa que pasa en tests).

Los loggers `httpx` y `httpcore` quedan en WARNING: a nivel INFO, httpx
escribe la URL completa de cada request, query string incluida, y por ahí
puede salir un token (`SEC-2`). Si hace falta observar las llamadas salientes,
el adapter que las hace loguea método, host y status por su cuenta.

*Alternativa descartada:* `structlog`. Es mejor herramienta, pero es una
dependencia y un concepto nuevos para resolver algo que la stdlib resuelve en
cincuenta líneas. Si el change de hardening necesita más, se reevalúa ahí.

### D7. Cliente HTTP

`OutboundHttpClient` envuelve un `httpx.Client` **sync** (coherente con
`DAT-3`: lo van a llamar path operations `def` y jobs del scheduler). Se
construye con `httpx.Timeout(connect=..., read=..., write=..., pool=...)`, los
cuatro explícitos. Expone `request(method, url, **kwargs)` y traduce
`httpx.TimeoutException` a `OutboundTimeoutError` y el resto de
`httpx.HTTPError` a `OutboundHttpError`, con un mensaje que solo nombra método
y host; nunca headers (ahí va el bearer token de Meta), body ni query.

Se crea en `create_app()`, se guarda en `app.state` y se cierra en el lifespan.

El test de timeout levanta un socket en `127.0.0.1` que acepta la conexión y no
responde nunca, con `read=0.5`. Es loopback, no red: cumple `VER-3`. Un
`MockTransport` que levante `ReadTimeout` no probaría que el timeout está
configurado, solo que la traducción funciona; se usan los dos.

### D8. Health check

`GET /health` es `def` (`DAT-1`), está fuera de los dos prefijos y declara
`response_model=HealthResponse` (`API-5`):

```json
{"status": "ok" | "degraded", "checks": {"app": "up", "database": "up" | "down"}}
```

Ejecuta `SELECT 1` con el engine de `app.state`, acotado por
`HEALTH_DB_TIMEOUT_SECONDS` (connect timeout + `statement_timeout` de la
sesión). Ante cualquier `SQLAlchemyError` responde **503** con el mismo
`HealthResponse` y loguea `type(exc).__name__`, **no** `str(exc)`: el mensaje
de psycopg incluye host y puerto.

**Por qué 503 y no 200.** Un monitor externo o un orquestador decide por el
código de estado, no por el cuerpo. Con 200 en ambos casos, la base caída pasa
desapercibida para cualquier monitor que no parsee JSON. 503 con cuerpo cumple
"no un 500 sin cuerpo" y deja la distinción app/base en el cuerpo. `API-3` no
lista 503, pero tampoco lo prohíbe; es el código estándar de "servicio
temporalmente no disponible". **Esta decisión fija el escenario 2 de la spec:
revisarla al aprobar.**

### D9. Toolchain

- `pyproject.toml`: cada dependencia con `==`, tomando las versiones que hoy
  resuelve `uv.lock`. Se suman `pyyaml` (runtime) y `ruff`, `mypy`,
  `types-pyyaml` (dev). Sale `pytest-asyncio`. Después `uv lock` regenera el
  lockfile; `uv lock --check` es el test de "lockfile en sync".
- **ruff**: `target-version = "py312"`, `line-length = 88`, reglas
  `E, W, F, I, B, UP, S, SIM, RUF`; `S101` permitido en `tests/`.
  `extend-exclude = ["backend/alembic", "backend/app/models"]`, cada uno con
  comentario que nombra el change que levanta la exclusión. Sin excluir los
  modelos, `ruff format --check .` falla sobre archivos que este change no
  puede tocar.
- **mypy**: `strict = true`, `files = ["backend/app"]`,
  `mypy_path = "backend"`, `explicit_package_bases = true`,
  `plugins = ["pydantic.mypy"]`. Sin overrides: los modelos pasan estricto tal
  como están (verificado en el grupo 1). Si un modelo rompe mypy más adelante,
  la exención se decide en el change que lo cause.
- **pytest**: `testpaths = ["tests"]`, `pythonpath = ["backend"]`,
  `addopts = "-ra --strict-markers"`, markers `unit` e `integration`.
  `tests/conftest.py` asigna el marker por carpeta en
  `pytest_collection_modifyitems`, así ningún test queda sin marcar.

### D10. Aislamiento de los tests

- **Unit**: nunca leen el `.env` del desarrollador. Un fixture arma un
  directorio temporal con YAML válidos y setea las variables con `monkeypatch`;
  cada test que necesita romper algo parte de ahí. `get_config.cache_clear()`
  antes y después de cada test. El escenario de base caída usa un engine
  apuntado a un puerto cerrado de `127.0.0.1`.
- **Integration**: usan `DATABASE_URL` del entorno. El `conftest` hace un
  `SELECT 1` en una fixture de sesión y, si falla, aborta con
  `pytest.exit("PostgreSQL no alcanzable en DATABASE_URL", returncode=1)`.
  Nunca `skip` (`VER-6`). No crean ni migran tablas: el health no las necesita.

## Risks / Trade-offs

- **[Alembic pasa a exigir los YAML]** `env.py` lee `settings`, y `settings`
  ahora implica validar toda la config. → Los YAML viven en el repo con
  defaults válidos, así que en la práctica siempre están. Si molesta, el change
  que toque Alembic puede leer solo `Settings` del entorno.
- **[El regex de teléfono enmascara números largos que no son teléfonos]** Ids
  `BIGINT` grandes o timestamps epoch en el mensaje quedarían enmascarados. →
  Hoy los ids son chicos y el timestamp del record se agrega después del
  filtro. Es preferible enmascarar de más que filtrar un teléfono (`SEC-3`).
- **[El regex no ve teléfonos con menos de 8 dígitos o partidos en dos campos]**
  → Es una red de seguridad, no el control principal: el control es no loguear
  teléfonos. Los changes con PII deben loguear `customer_id`, no el número.
- **[Handlers ajenos al nuestro]** Un handler que ve el record antes que nuestro
  filtro escribe sin enmascarar. Pasa con el `StreamHandler` que SQLAlchemy
  cuelga cuando `DATABASE_ECHO=true`: SQL y parámetros en claro. → Producción
  está bloqueada por el guard de `DAT-10`; `.env.example` advierte que el echo
  saca datos personales en claro aun en desarrollo.
- **[Uvicorn access log con query string]** El access log de uvicorn imprime la
  query completa, y el `GET` de verificación de Meta trae el verify token. Este
  change no tiene ese endpoint. → Queda anotado para el change 00, que debe
  apagar o filtrar el access log antes de exponer el webhook.
- **[503 vs `API-3`]** Si el humano interpreta que `API-3` es una lista
  cerrada, el escenario de base caída cambia a 200 con `status: degraded`. →
  Pregunta explícita en la revisión de la spec (D8).
- **[Tests de integración sin compose]** Hasta el change de compose, cada
  desarrollador provee su PostgreSQL. → El conftest falla con un mensaje claro
  en vez de colgarse o skipear.

## Migration Plan

1. Mergear con `.env` local actualizado: hay que agregar `APP_ENV`. Sin eso la
   app no levanta, que es exactamente el comportamiento pedido.
2. Quien usaba el SQL impreso en consola tiene que poner `DATABASE_ECHO=true`
   en su `.env` de desarrollo.
3. Rollback: revertir el merge. No hay migraciones ni datos involucrados.

## Open Questions

- **`/docs` en producción.** FastAPI publica el esquema OpenAPI por defecto. No
  expone datos, pero sí la superficie del panel. Se decide en el change del
  panel.

Resueltas durante el apply: el repositorio de idempotencia pasa ruff sin
cambios y no necesitó exclusión; los textos de error HTTP van a
`http_errors.yaml`, separados del copy del cliente.
