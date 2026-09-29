# Database identifiers specification

## ADDED Requirements

### Requirement: Internal entity identifiers use BIGINT

The system MUST store every existing internal entity primary key as PostgreSQL
`BIGINT`.

#### Scenario: Upgrade the existing schema

- **WHEN** the BIGINT migration is applied to the initial schema
- **THEN** `customers.id`, `menu_items.id`, `orders.id`, `order_items.id`,
  `reservations.id` and `conversations.id` are PostgreSQL `BIGINT`
- **AND** their primary-key constraints remain present

### Requirement: Foreign-key types match their referenced identifiers

Every existing foreign-key column MUST use PostgreSQL `BIGINT` and MUST retain
its current referential behavior.

#### Scenario: Preserve valid relationships

- **WHEN** the migration upgrades a database containing related rows
- **THEN** all existing relationships remain valid
- **AND** `orders.customer_id`, `order_items.order_id`,
  `order_items.menu_item_id`, `reservations.customer_id`,
  `conversations.customer_id` and `conversations.current_order_id` are
  PostgreSQL `BIGINT`

#### Scenario: Reject an invalid relationship after upgrade

- **WHEN** an insert references a parent identifier that does not exist
- **THEN** PostgreSQL rejects it through the preserved foreign-key constraint

### Requirement: Identifier generation remains operational

The migration MUST preserve automatic identifier generation for every
existing entity table.

#### Scenario: Insert after upgrade

- **WHEN** a valid row is inserted without supplying its primary key after the
  migration
- **THEN** PostgreSQL generates a new identifier
- **AND** the generated identifier is stored as `BIGINT`

### Requirement: ORM mappings declare physical identifier types explicitly

The SQLAlchemy models MUST declare `BigInteger` for every affected PK and FK
while retaining `int` as their Python annotation.

#### Scenario: Alembic compares metadata after upgrade

- **WHEN** SQLAlchemy metadata is compared with the upgraded database
- **THEN** the affected PK and FK columns have matching `BIGINT` types
- **AND** no identifier type drift is reported

### Requirement: Downgrade preserves representable data

The migration MUST restore affected PK and FK columns to PostgreSQL `INTEGER`
when all stored identifiers fit within its range.

#### Scenario: Downgrade with in-range identifiers

- **WHEN** all identifiers fit in PostgreSQL `INTEGER`
- **AND** the migration is downgraded
- **THEN** all affected PK and FK columns become `INTEGER`
- **AND** rows, relationships and constraints remain intact

#### Scenario: Downgrade with an out-of-range identifier

- **WHEN** at least one stored primary-key identifier is outside the
  PostgreSQL `INTEGER` range
- **AND** the downgrade is attempted
- **THEN** the downgrade fails with an explicit error
- **AND** no affected table remains partially converted

### Requirement: Migration verification uses PostgreSQL

Upgrade and downgrade behavior MUST be verified against PostgreSQL rather than
SQLite.

#### Scenario: Complete migration verification

- **WHEN** the migration verification suite runs
- **THEN** it exercises upgrade, inserts with generated IDs, foreign-key
  enforcement and downgrade against PostgreSQL
- **AND** the verification result is recorded before closing the change
