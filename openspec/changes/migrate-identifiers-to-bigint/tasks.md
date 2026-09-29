# Tasks: Migrate internal identifiers to BIGINT

No implementation task starts until this proposal, design and spec are
explicitly approved.

## 1. SQLAlchemy models

- [x] 1.1 Declare `BigInteger` on every existing internal primary key.
- [x] 1.2 Declare `BigInteger` on every foreign key referencing those keys.
- [x] 1.3 Confirm counts and durations remain `Integer`.
- [x] 1.4 Confirm Python annotations remain `Mapped[int]`.

## 2. Alembic migration

- [ ] 2.1 Generate a new revision without editing the initial migration.
- [ ] 2.2 Review the conversion order for PK and FK columns.
- [ ] 2.3 Preserve FK delete actions, PKs, indexes and unique constraints.
- [ ] 2.4 Verify every table still generates identifiers automatically.
- [ ] 2.5 Add an explicit range guard before the downgrade to `INTEGER`.
- [ ] 2.6 Review that downgrade restores only the identifier types changed here.

## 3. Verification

- [ ] 3.1 Test upgrade against the initial schema on PostgreSQL.
- [ ] 3.2 Test upgrade with existing related rows.
- [ ] 3.3 Test generated IDs and FK enforcement after upgrade.
- [ ] 3.4 Test downgrade with identifiers inside the `INTEGER` range.
- [ ] 3.5 Test downgrade rejection for an out-of-range identifier.
- [ ] 3.6 Run the complete `run-verify` workflow and record its result.

## 4. Documentation

- [ ] 4.1 Record operational lock and downtime considerations.
- [ ] 4.2 Update `ESTADO.md` and the README session log when the change closes.
