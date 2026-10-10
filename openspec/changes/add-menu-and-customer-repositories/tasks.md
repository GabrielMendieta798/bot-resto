# Tasks: Add menu and customer repositories

No implementation task starts until proposal, design and specs are explicitly
approved (`SDD-1`). The plan order was approved by Lautaro on 10/10/2026
(`SDD-6`, see proposal). After every task, run `run-verify`; red ⇒ stop and fix
(`VER-1`). If a task meets a case the specs do not cover, stop and propose the
scenario (`SDD-2`). `backend/app/models/`, `backend/alembic/`,
`backend/app/core/` and `backend/app/api/` stay untouched throughout.

## 1. Package skeleton and boundary checks

- [x] 1.1 Create the empty packages `backend/app/domain/__init__.py`,
  `domain/menu/__init__.py`, `domain/customers/__init__.py`,
  `backend/app/db/__init__.py` and `db/repositories/__init__.py` (design D1).
- [x] 1.2 Write `tests/unit/test_domain_boundaries.py`:
  - AST check over **every** `.py` under `backend/app/domain/`, discovered by
    walking the package (not a fixed list), that rejects imports of
    `sqlalchemy`, `app.models`, `app.core.database` and `app.db`, whether
    absolute, relative or inside a function.
  - AST check over every module of `backend/app/db/repositories/` that
    rejects calls to `commit`, `rollback`, `begin`, `begin_nested` and
    `close`.
  - Subprocess check that importing every module of `app.domain` in a fresh
    interpreter loads no `sqlalchemy` module.

  The checks must pass on the empty packages, and must go red on a scratch
  file that imports `sqlalchemy` (removed afterwards).

## 2. Menu schemas and service

Regrouped on 10/10/2026 at Lautaro's request, with the same content: each task
ships the behavior together with the tests of its scenarios, and the fake
comes before the service that is tested against it.

- [x] 2.1 Write `domain/menu/schemas.py`, with its tests:
  - `MenuItemRead`: frozen; `price` is a `Decimal` with exponent `-2`;
    `created_at` is an `AwareDatetime` normalized to UTC;
    `estimated_time_min: int | None`.
  - `MenuItemUpdate`: every field optional; `strict`, `extra="forbid"` and
    `str_strip_whitespace`; `name` not nullable, 1 to 150 characters;
    `description` nullable; `price` a non-nullable, finite `Decimal` that also
    accepts `int` and decimal text and rejects `float` and `bool`;
    `estimated_time_min` a non-nullable `int` that also accepts integer text
    and rejects `bool` and `float` (design D5, shape table and "Texto en los
    campos numéricos"). No sign, scale or range constraint: those are rules
    and belong in the service.
  - `tests/unit/test_menu_schemas.py` for the requirement "Edit shape is
    validated by the edit object":
    - the field outside the edit (category, availability, identifier);
    - a name that is blank, 151 characters long, or null;
    - a price that is a float (`9200.5`, `1500.0`), `true`, `NaN`, infinity
      or null;
    - a price as decimal text (`"9200.00"`, `" 9200.00 "`, `"1E+3"`) or an
      integer, accepted as exact values; `""`, `"NaN"`, `"Infinity"`,
      `"1,5"`, `"1_000"`, `"+5"` and non-ASCII digits rejected;
    - an estimated time as integer text (`"25"`, `" 25 "`, `"-5"`) accepted;
      `true`, `12.5`, `""`, `"25.0"`, `"2.5"` and non-ASCII digits rejected;
      null rejected, meaning the estimated time cannot go back to unknown;
    - form-encoded input, covered by validating a dict of strings, which is
      what a form delivers (`python-multipart` is not installed and
      `pyproject.toml` is off limits, so the real form `POST` test goes with
      the panel change);
    - "absent and empty are different" at the `model_fields_set` level;
    - the name is trimmed.

    Then request-level tests with a throwaway FastAPI route that takes
    `MenuItemUpdate` as its JSON body, run through `create_app`'s error
    handlers:
    - a shape error gives a `400` with `invalid_input` and the field, and the
      body does not echo the value;
    - a valid text price, a JSON integer price and a text estimated time reach
      the handler as exact values;
    - a JSON number with a fractional part is rejected for `price` (`DAT-8`).

    The route is test-only; no endpoint is added to the app.
  - Unit tests for `domain-data-boundary`: building `MenuItemRead` with a
    naive `created_at` fails, and returned objects are frozen.
- [x] 2.2 Write `InMemoryMenuRepository` in `tests/unit/domain_fakes.py`,
  implementing the same ordering and filters as design D7.
- [x] 2.3 Write `domain/menu/service.py`, with its tests:
  - `MenuRepository` `Protocol`, and `MenuService` with `list_categories`,
    `list_available_items`, `list_all_items`, `get_item`, `set_available` and
    `update_item(item_id, changes: MenuItemUpdate)`.
  - The rules of design D5 (rules table) raise `InvalidInputError(field=...)`
    with a fixed detail, checked before the lookup.
  - An empty `model_fields_set` is rejected.
  - An out-of-range id raises `NotFoundError` without calling the repository,
    and the `NotFoundError` detail carries only the id.
  - The changes are built from `model_fields_set` (design D6).
  - Unit tests for `menu-catalog` against the fake:
    - **Categories:** listed only when they have an available item, each
      once; selling out the last item hides the category.
    - **Listings:** available items are filtered and ordered by name, then
      id; an unknown category gives an empty list; the staff list includes
      unavailable items, in the same order; looking up an unavailable item
      works.
    - **Availability:** `set_available` to false, to true, and twice with the
      same value.
    - **Not found:** get, set and edit with an id-only message; ids `0`, `-1`
      and `2**63`.
    - **Edits:** an edit of only the price leaves the rest; an empty
      description clears it; an empty edit is rejected.
    - **Rules:** every case of "Edit business rules are enforced by the
      menu", with the right `field`; `1500.500` is stored as `1500.50`; zero
      price and zero time are accepted; the rejected value is absent from the
      message, the `repr` and the exception chain.

## 3. Customer schemas and service

Regrouped on 10/10/2026 at Lautaro's request, like group 2: each task ships
the behavior with the tests of its scenarios, and the fake comes before the
service that is tested against it.

- [x] 3.1 Write `domain/customers/schemas.py`, with its tests:
  - `CustomerRead`: frozen, with `phone` set to `repr=False` and `created_at`
    as an `AwareDatetime` normalized to UTC.
  - Unit tests: `str` and `repr` of `CustomerRead` hide the phone; a naive
    `created_at` is rejected; `created_at` is normalized to UTC; the object is
    frozen.
- [x] 3.2 Write `InMemoryCustomerRepository` in `tests/unit/domain_fakes.py`.
- [x] 3.3 Write `domain/customers/service.py`, with its tests:
  - The `CustomerRepository` `Protocol`, and
    `CustomerService.get_or_create_by_phone`.
  - It validates the phone with `re.fullmatch(r"[0-9]{8,15}", ...)` and
    raises `InvalidInputError(field="phone")` with a fixed detail, before
    calling the repository (design D5).
  - No Pydantic validation of the phone and no logging of it.
  - Unit tests for `customer-registry`:
    - A new number creates the customer; a known number returns the same id
      without duplicating.
    - Formatted numbers, letters, an empty value, 7 and 16 digits, and
      non-ASCII digits are rejected without calling the repository; 8 and 15
      digits are accepted.
    - The phone is absent from the message, `str`, `repr`, the exception
      chain and the captured log (`caplog` plus the JSON handler of
      `configure_logging`).

## 4. Customer repository

Regrouped on 10/10/2026 at Lautaro's request: each repository ships with its
integration tests in its own group. The scenarios did not change, only the
order.

Protocol conformance: mypy only checks `backend/app` (`pyproject.toml`), so a
typed assignment in `tests/integration/` would be checked by nothing. The
check lives in each repository module instead, as
`_x: type[CustomerRepository] = SqlCustomerRepository`, which is verified on
10/10 to make mypy fail on an incompatible class.

- [x] 4.1 Write `db/repositories/customers.py`, with its tests:
  - `SqlCustomerRepository(session)`: `INSERT ... ON CONFLICT (phone) DO
    NOTHING RETURNING`, followed by a `SELECT` only when nothing was returned
    (design D4); ORM or parametrized statements only (`SEC-4`); flushing
    allowed, no transaction control. Its docstring states that the caller
    owns the transaction and the `read committed` assumption.
  - The module-level conformance check against `CustomerRepository`.
  - The `db_session` fixture in `tests/integration/conftest.py`: an outer
    transaction, a `Session` with `join_transaction_mode="create_savepoint"`,
    and a rollback at teardown (design D8).
  - `tests/integration/test_customer_repository.py`:
    - creating and then getting again returns the same id, with one row per
      phone;
    - a creation undone by `session.rollback()` leaves zero rows, and it is
      not visible from a second connection before the commit;
    - the first statement sent to `customers` is the `INSERT`, captured with
      a `before_cursor_execute` listener;
    - `created_at` is aware and in UTC;
    - returned values are not ORM instances.
- [x] 4.2 Write `tests/integration/test_customer_concurrency.py` (`VER-2`),
  using two engines:
  - **Deterministic test:** B is observed waiting on a lock in
    `pg_stat_activity` until A commits, and then returns A's id.
  - **Rollback variant:** A rolls back and B creates the customer.
  - **Race test:** several threads synchronized with a `threading.Barrier`
    commit the same number, ending with one row and one id.

  Phones are unique per run, and the teardown deletes them.

## 5. Menu repository

- [ ] 5.1 Write `db/repositories/menu.py`, with its tests:
  - `SqlMenuRepository(session)`: the queries of design D6 and D7, ORM or
    parametrized statements only (`SEC-4`); `UPDATE ... RETURNING` with only
    the present columns and the price quantized before writing; results
    converted to `MenuItemRead`; flushing allowed, no transaction control.
    Its docstring states that the caller owns the transaction.
  - The module-level conformance check against `MenuRepository`.
  - In `tests/integration/conftest.py`: a helper that inserts menu items
    under a unique category per test, and one that inserts an `Order` and an
    `OrderItem` with Core `insert()` (design D8).
  - `tests/integration/test_menu_repository.py`:
    - categories, filters and order against PostgreSQL, including the `Ñ`
      case under `en_US.utf8`;
    - a sold-out row is still present, queried directly and not through the
      repository, with every other column unchanged;
    - a price edit keeps the order line's `unit_price_snapshot` (`DAT-4`);
    - an edit of only the price leaves the rest unchanged;
    - price `10000000000.00` and estimated time `2147483648` raise
      `InvalidInputError` and no database error;
    - the price comes back as a `Decimal` with exponent `-2`;
    - `created_at` is aware and in UTC with the session time zone set to
      `America/Argentina/Buenos_Aires`;
    - returned values are not ORM instances.
- [ ] 5.2 Rollback scenarios of `domain-data-boundary` for the menu: a price
  edit and an availability change are undone by `session.rollback()`; and a
  customer created and an item edited in one uncommitted transaction are
  both invisible from a second connection.
- [ ] 5.3 Confirm that the group 1 boundary tests are still green with both
  repositories in place, and that mypy strict passes on `backend/app/domain`
  and `backend/app/db` with no `# type: ignore`.

## 6. Closing

- [ ] 6.1 Run the full `run-verify` (ruff, format, mypy strict, unit and
  integration) until it is green, and record the result.
- [ ] 6.2 Confirm that `backend/app/models/`, `backend/alembic/`,
  `backend/app/core/` and `backend/app/api/` have no diff, and that no
  migration was generated.
- [ ] 6.3 Run `@security` on the change, paying attention to `raise`
  statements built from customer data (the `structured-logging` requirement)
  and to SQL construction (`SEC-4`). Fix the medium and high findings.
- [ ] 6.4 Update `ESTADO.md`:
  - D-9 confirmed (`configure_mappers()` is now exercised).
  - New debt, **prerequisite of the orders change**: the `NOT NULL`
    migration of `menu_items.estimated_time_min` (`ORD-12`).
  - New debts:
    - the canonical-phone `CHECK` on `customers.phone`;
    - the `read committed` requirement for the webhook transaction;
    - the panel endpoint must take `MenuItemUpdate` as its validated payload
      (design D5);
    - the database collation for `docker-compose`;
    - the suggested rewording of `DAT-5` ("sets" instead of "toggles"),
      pending approval under `PRI-2`.
  - D-5 partly advanced: `db/` now exists.

  Then add the README session log.
