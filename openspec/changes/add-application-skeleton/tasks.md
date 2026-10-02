# Tasks: Add application skeleton

No implementation task starts until proposal, design and specs are explicitly
approved (`SDD-1`). After every task, run `run-verify`; red ⇒ stop and fix
(`VER-1`). Group 1 has no tests yet, so its verification is ruff + mypy only;
pytest joins from group 2 onwards.

## 1. Toolchain

- [x] 1.1 Pin every dependency in `pyproject.toml` with `==`, using the versions
  currently resolved in `uv.lock`; add `pyyaml`; remove `pytest-asyncio`.
- [x] 1.2 Add `ruff`, `mypy` and `types-pyyaml` to the dev group, pinned.
- [x] 1.3 Configure ruff (rules, `S101` allowed in `tests/`, exclusions of
  `backend/alembic` and `backend/app/models` with a comment naming the change
  that lifts each one).
- [x] 1.4 Configure mypy strict with `mypy_path`, `explicit_package_bases` and
  the pydantic plugin, with no per-module override.
- [x] 1.5 Configure pytest: `testpaths`, `pythonpath = ["backend"]`,
  `--strict-markers`, markers `unit` and `integration`.
- [x] 1.6 Add empty `backend/app/__init__.py` and `backend/app/core/__init__.py`.
- [x] 1.7 Regenerate `uv.lock` and confirm `uv lock --check` passes.
- [x] 1.8 Run ruff and format on the repo. If they require changes in
  `idempotency_repository.py`, stop and ask (design, Open Questions).
- [x] 1.9 Create `tests/conftest.py` (marker by folder), `tests/unit/conftest.py`
  and `tests/integration/conftest.py` (fixtures land in later tasks).

## 2. Exceptions and logging

- [x] 2.1 Write `core/exceptions.py`: the hierarchy of design D5 with `code`,
  `message_key`, optional `field`, and the registry of message keys. No
  FastAPI import.
- [x] 2.2 Write `core/logging.py`: JSON formatter, phone masking filter on the
  root handler, idempotent `configure_logging`.
- [x] 2.3 Unit tests for `structured-logging`: record shape, level filtering,
  phone in message, formatted E.164, structured field, exception stacktrace,
  short numbers untouched.

## 3. Configuration

- [x] 3.1 Create `config/restaurant.yaml` with documented defaults for every
  `GEN-7` value and the header about the five owner questions.
- [x] 3.2 Create `config/http_errors.yaml` with one text per key in the D5
  registry, and `config/messages.yaml` with only a comment header (what goes
  there, that internal errors live in `http_errors.yaml`, that copy arrives
  with the conversation changes).
- [x] 3.3 Rewrite `core/config.py`: `Settings`, `RestaurantConfig`,
  `MessagesConfig`, `HttpErrorsConfig`, `load_config`, cached `get_config`, `ConfigError` raised
  `from None`, lazy `settings` attribute for Alembic.
- [x] 3.4 Add the startup check that every registered error text key exists
  in `http_errors.yaml`.
- [x] 3.5 Rewrite `.env.example` with every settings key and no real value.
- [x] 3.6 Unit tests for `runtime-configuration`: missing env key, missing YAML
  key, wrong shape, secret never in error (including chained output), unknown
  YAML key, YAML syntax error without snippet, absent file, non-mapping top
  level, committed defaults load, exact decimal fee, unknown time zone, missing
  error text key, committed error texts cover every error type, error section
  in `messages.yaml` rejected, committed `messages.yaml` holds no internal
  text, comments-only `messages.yaml` accepted, comments-only
  `restaurant.yaml` rejected, absent `messages.yaml` rejected, `.env.example` keys equal settings keys.
- [x] 3.7 Verify `backend/alembic/env.py` still imports `settings` and `Base`
  unchanged (`alembic check` or an import test), without editing it.

## 4. Database

- [x] 4.1 Rewrite `core/database.py`: keep `Base`; add `build_engine` with
  `echo` from settings, `pool_pre_ping`, connect timeout; add
  `build_session_factory`. No engine at import time.
- [x] 4.2 Unit tests: echo off by default, on by configuration in development,
  startup refused with echo in production.

## 5. Outbound HTTP client

- [x] 5.1 Write `integrations/http_client.py`: sync httpx client with the four
  explicit timeouts, translation to `OutboundTimeoutError` /
  `OutboundHttpError` with method and host only.
- [x] 5.2 Unit tests for `outbound-http-client`: timeouts equal configuration,
  silent loopback server raises in under 5 s, error message has no headers,
  body or query, closed client refuses requests, module has no WhatsApp
  reference, outbound request URL never logged.

## 6. Application and HTTP layer

- [x] 6.1 Write `api/errors.py`: status map resolved by MRO, handlers for
  `AppError`, `RequestValidationError` (400), `StarletteHTTPException` and
  `Exception` (500, stacktrace to log only, path without query).
- [x] 6.2 Write `api/webhook.py` and `api/panel.py` as empty routers with
  disjoint prefixes.
- [x] 6.3 Write `api/health.py`: `def` endpoint, `HealthResponse`, bounded
  `SELECT 1`, 200/503, error type logged without message.
- [x] 6.4 Write `main.py`: `create_app()` loads config, configures logging,
  builds engine and HTTP client, registers handlers and routers; lifespan
  disposes engine and closes client; `app = create_app()`.
- [ ] 6.5 Unit tests for `error-contract`: each category to its status and
  code, field on invalid input, subclass inherits status, 400 instead of 422
  without echoing input, unknown route 404, `POST /health` 405, unexpected
  exception 500 with no internals and stacktrace in the log with masked phone,
  driver error 500.
- [ ] 6.6 Unit tests for `application-runtime`: invalid config prevents
  `create_app`, prefixes disjoint, webhook exposes no panel route, staff path
  under webhook prefix 404, health with unreachable database returns 503 with
  body in bounded time, no internals in either health response, failure log
  without connection string.

## 7. Integration

- [ ] 7.1 Integration `conftest.py`: session fixture that checks PostgreSQL and
  calls `pytest.exit` on failure, never skip.
- [ ] 7.2 Health smoke test against real PostgreSQL: 200, both checks up, no
  internals in the body.

## 8. Closing

- [ ] 8.1 Full `run-verify` in green, result recorded.
- [ ] 8.2 Manual check: start the app, remove `APP_ENV` from `.env`, confirm it
  does not start and the message names the key only.
- [ ] 8.3 Confirm `backend/app/models/`, `backend/alembic/` and
  `idempotency_repository.py` have no diff and no migration was generated.
- [ ] 8.4 Functional verification scenario by scenario with `@api-explorer`.
- [ ] 8.5 Update `ESTADO.md` (debts D-6 and D-7 resolved; access-log risk
  handed to change 00) and the README session log.
