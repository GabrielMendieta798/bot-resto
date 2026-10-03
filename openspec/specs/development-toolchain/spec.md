# development-toolchain Specification

## Purpose

Defines the reproducible toolchain every change is verified with: pinned
dependencies, a committed lockfile, lint, strict typecheck, and test suites
separated by kind.

## Requirements

### Requirement: Pinned dependencies and committed lockfile

Every runtime and development dependency SHALL be declared with an exact
version, and the lockfile SHALL be committed and consistent with those
declarations. The toolchain SHALL NOT include async test plugins, since the
data stack is synchronous.

#### Scenario: Exact versions

- **WHEN** the dependency declarations are inspected
- **THEN** every entry pins an exact version

#### Scenario: Lockfile in sync

- **WHEN** the lockfile is checked against the declarations
- **THEN** the check reports no drift

#### Scenario: No async test plugin

- **WHEN** the development dependencies are listed
- **THEN** `pytest-asyncio` is absent

### Requirement: Lint and format checks

The repository SHALL be checked by a linter and a formatter. Code frozen by
this change's non-goals (`backend/app/models/`, `backend/alembic/`) SHALL be
excluded explicitly, with a comment naming the change that lifts each
exclusion.

#### Scenario: Clean lint

- **WHEN** the lint and format checks run on the repository
- **THEN** both pass

### Requirement: Strict typecheck

The application package SHALL pass a strict static typecheck with no module
exempted. Adding an exemption requires an explicit decision recorded in the
change that needs it.

#### Scenario: Strict typecheck passes

- **WHEN** the typecheck runs on `backend/app`
- **THEN** it reports no errors
- **AND** strict mode is enabled
- **AND** no module is exempted or has its errors ignored

### Requirement: Separate unit and integration suites

Tests SHALL live in `tests/unit/` and `tests/integration/`, each tagged with a
registered marker (`unit` or `integration`), and unknown markers SHALL fail
the run. Unit tests SHALL run without network access other than loopback and
without a database. Integration tests SHALL run against a real PostgreSQL
instance and SHALL fail, not skip, when it is unreachable.

#### Scenario: Run only unit tests

- **WHEN** the unit suite runs with no database available
- **THEN** it passes

#### Scenario: Integration without a database

- **GIVEN** no PostgreSQL is reachable at the configured URL
- **WHEN** the integration suite runs
- **THEN** it fails with a message stating that the database is unreachable
- **AND** no integration test is reported as skipped

#### Scenario: Health smoke test

- **GIVEN** a reachable PostgreSQL
- **WHEN** the integration suite runs
- **THEN** a smoke test calls `GET /health` on the real application and
  receives HTTP 200
