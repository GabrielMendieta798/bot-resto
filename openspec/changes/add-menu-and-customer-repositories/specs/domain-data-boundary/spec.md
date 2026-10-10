## Purpose

Fixes the rules every domain module follows when it touches the database: who
owns the transaction, what a service is allowed to see, and the types of the
amounts and timestamps a repository hands back.

## ADDED Requirements

### Requirement: The caller owns the transaction

A repository SHALL be the only code a domain module relies on to use the
database session. It MAY flush, but SHALL NOT commit or roll back: the code that opened the
transaction decides whether its effects persist (`CONV-10`). A service SHALL
NOT commit or roll back either.

#### Scenario: Customer creation rolled back

- **GIVEN** a transaction in which a customer is obtained for a new number
- **WHEN** the caller rolls back that transaction
- **THEN** no customer with that number exists, seen from another connection

#### Scenario: Price edit rolled back

- **GIVEN** an item with price `8500.00`
- **WHEN** its price is edited to `9200.00` and the caller rolls back the
  transaction
- **THEN** the item price is `8500.00`

#### Scenario: Availability change rolled back

- **GIVEN** an available item
- **WHEN** it is marked unavailable and the caller rolls back the transaction
- **THEN** the item is available

#### Scenario: Nothing is committed before the caller commits

- **WHEN** a customer is created and an item is edited in one transaction that
  the caller has not committed
- **THEN** another connection sees neither change

### Requirement: Services never see the database

No module of the domain package SHALL import SQLAlchemy, the ORM models, the
database setup, or any repository implementation (`GEN-1`, strict reading, and
`DAT-2`). Repository implementations live outside the domain package. A service
SHALL receive its repository as an interface, declared by the domain and
injected by the caller. Service tests SHALL run against an in-memory repository,
with no database and no network (`VER-3`).

#### Scenario: Import check over the whole domain package

- **WHEN** a static check parses every module under the domain package,
  including modules added by later changes
- **THEN** none imports `sqlalchemy`, `app.models`, `app.core.database` or
  `app.db`, directly, by a relative import, or inside a function

#### Scenario: Importing the domain loads no persistence

- **WHEN** every module of the domain package is imported in a fresh
  interpreter
- **THEN** no `sqlalchemy` module has been loaded

#### Scenario: Repositories satisfy the domain interface

- **WHEN** the typecheck runs over the repository implementations
- **THEN** each one is checked against the interface declared by its service

#### Scenario: Service tests without a database

- **WHEN** the unit test suite runs the services of `menu` and `customers`
- **THEN** it uses in-memory repositories and opens no database connection

### Requirement: Repositories return plain data, not database objects

A repository SHALL return validated data objects, never ORM instances, so that
nothing outside the repository can lazy-load, modify or flush through what it
receives (`API-5`).

#### Scenario: Returned objects are detached from the database

- **WHEN** any repository method of `menu` or `customers` returns an item or a
  customer
- **THEN** the returned value is not an ORM instance
- **AND** changing one of its attributes is rejected or has no effect on the
  database

### Requirement: Money is Decimal and time is zone-aware

Every amount a repository returns SHALL be a `Decimal` with two decimal places,
never a `float` (`DAT-8`). Every timestamp it returns SHALL carry a time zone
and be expressed in UTC (`GEN-6`); a naive datetime is a failure.

#### Scenario: Price read from the database

- **WHEN** an item is read through the repository
- **THEN** its price is a `Decimal` with exponent `-2`
- **AND** no amount in the result is a `float`

#### Scenario: Timestamps read from the database

- **WHEN** an item or a customer is read through the repository, whatever the
  time zone of the database session
- **THEN** its creation timestamp has a time zone with UTC offset zero

#### Scenario: Naive timestamp rejected

- **WHEN** a data object for an item or a customer is built with a naive
  creation timestamp
- **THEN** building it fails
