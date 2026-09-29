# Tasks: Add WhatsApp inbound message idempotency

No implementation task starts until this proposal, design and spec are
explicitly approved.

## 1. Data model and migration

- [x] 1.1 Add the `ProcessedWhatsAppMessage` SQLAlchemy model.
- [x] 1.2 Export the model so Alembic metadata includes it.
- [ ] 1.3 Generate a new Alembic revision without editing the initial migration.
- [ ] 1.4 Review `upgrade()` for a `TEXT` PK and UTC `received_at` server default.
- [ ] 1.5 Review `downgrade()` so it removes only the new table.
- [ ] 1.6 Test migration upgrade and downgrade against PostgreSQL.

## 2. Repository

- [x] 2.1 Add a WhatsApp idempotency repository operation using PostgreSQL
  `INSERT ... ON CONFLICT DO NOTHING RETURNING`.
- [x] 2.2 Return an explicit claimed/duplicate result.
- [x] 2.3 Ensure the repository never commits independently.

## 3. Webhook transaction

- [ ] 3.1 Validate the webhook signature before opening message processing.
- [ ] 3.2 Process each `message_id` in its own transaction.
- [ ] 3.3 Attempt the idempotency insert before locking Conversation.
- [ ] 3.4 Preserve the remaining lock order for Order and Reservation.
- [ ] 3.5 Commit domain effects and the idempotency row together.
- [ ] 3.6 Dispatch external sends only after commit.
- [ ] 3.7 Return 200 for duplicates, 403 for invalid signatures and 5xx for
  rolled-back processing failures.

## 4. Verification

- [ ] 4.1 Test a sequential duplicate produces one domain effect.
- [ ] 4.2 Test two concurrent claims against PostgreSQL produce one effect.
- [ ] 4.3 Test failure after claim rolls back the row and permits retry.
- [ ] 4.4 Test an invalid signature creates no row.
- [ ] 4.5 Test partial failure and retry of a batched webhook.
- [ ] 4.6 Verify logs contain `message_id` but no payload or PII.
- [ ] 4.7 Run the complete `run-verify` workflow and record its result.

## 5. Documentation

- [ ] 5.1 Document that the change does not solve the commit-to-send gap.
- [ ] 5.2 Update `ESTADO.md` and the README session log when the change closes.
