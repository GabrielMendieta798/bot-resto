# Tasks: Migrate internal identifiers to BIGINT

No implementation task starts until this proposal, design and spec are
explicitly approved.

## 1. SQLAlchemy models

- [x] 1.1 Declare `BigInteger` on every existing internal primary key.
- [x] 1.2 Declare `BigInteger` on every foreign key referencing those keys.
- [x] 1.3 Confirm counts and durations remain `Integer`.
- [x] 1.4 Confirm Python annotations remain `Mapped[int]`.

## 2. Alembic migration

- [x] 2.1 Generate a new revision without editing the initial migration.
- [x] 2.2 Review the conversion order for PK and FK columns.
- [x] 2.3 Preserve FK delete actions, PKs, indexes and unique constraints.
- [x] 2.4 Verify every table still generates identifiers automatically.
- [x] 2.5 Add an explicit range guard before the downgrade to `INTEGER`.
- [x] 2.6 Review that downgrade restores only the identifier types changed here.

> Progress note (2026-10-02): the human reports that the generated Alembic
> upgrade was applied successfully in their environment. Downgrade safety,
> sequence behavior, preserved constraints and PostgreSQL verification remain
> pending in the tasks below.
>
> Progress note (2026-10-11): migration tests now use the dedicated PostgreSQL
> database `bot_resto_test`, which is reset before and after each test. The
> targeted test for 3.1 passes and verifies all twelve identifier columns plus
> the six primary keys after upgrading from the initial revision. The range
> guards and scoped downgrade required by 2.5 and 2.6 were reviewed. The full
> workflow passed: Ruff check and format, mypy over 24 source files, 92 unit
> tests and 4 integration tests. Existing related rows plus the complete PK,
> FK, delete-action, index and uniqueness contract are preserved, completing
> 2.3 and 3.2. All six sequences generate `BIGINT` identifiers beyond the
> `INTEGER` limit and PostgreSQL still rejects invalid FKs, completing 2.4 and
> 3.3.
>
> Downgrade verification treats each identifier revision independently:
> `c3a7b9d2e641` restores only sequences when downgraded to `57f88cf9ee63`,
> preserving `processed_whatsapp_messages`; `88d85f44fb7d` restores only the
> affected columns when downgraded to the initial revision. A one-command full
> identifier rollback from head is not an operational goal for this change.

## 3. Verification

- [x] 3.1 Test upgrade against the initial schema on PostgreSQL.
- [x] 3.2 Test upgrade with existing related rows.
- [x] 3.3 Test generated IDs and FK enforcement after upgrade.
- [x] 3.4 Test downgrade with identifiers inside the `INTEGER` range.
- [x] 3.5 Test downgrade rejection for an out-of-range identifier.
- [x] 3.6 Run the complete `run-verify` workflow and record its result.

## 4. Documentation

- [x] 4.1 Record operational lock and downtime considerations.
- [x] 4.2 Update `ESTADO.md` and the README session log when the change closes.

> Final verification (2026-10-11): Ruff check and format passed, mypy passed
> over 24 source files, 92 unit tests passed, and 8 integration tests passed.
> Seven integration scenarios cover the BIGINT upgrade, existing relationships,
> schema constraints, generated IDs beyond the INTEGER limit, FK enforcement,
> valid downgrades, and atomic rejection of out-of-range downgrades.
