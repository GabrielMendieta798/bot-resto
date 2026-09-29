# Tasks: Allow additions to an active order

No implementation task starts until this proposal, design and spec are
explicitly approved.

## 1. Prerequisites

- [ ] 1.1 Confirm the idempotency change implementing WA-4 is complete.
- [ ] 1.2 Confirm canonical Order statuses and monetary fields are migrated.
- [ ] 1.3 Confirm Conversation has the locked JSONB cart required by CONV-8.
- [ ] 1.4 Confirm the panel notification persistence required by NOT-2 exists.

## 2. Data model

- [ ] 2.1 Add `estimated_kitchen_ready_at` to Order with UTC semantics.
- [ ] 2.2 Add `added_at` to OrderItem with a PostgreSQL server default.
- [ ] 2.3 Preserve separate OrderItem rows for later additions.
- [ ] 2.4 Review the Alembic upgrade and downgrade, including existing-data handling.
- [ ] 2.5 Verify the partial unique index still protects one non-terminal Order.

## 3. Domain and persistence

- [ ] 3.1 Add the ETA calculation as a pure domain function using aware datetimes.
- [ ] 3.2 Add an Order repository operation that locks the target Order.
- [ ] 3.3 Implement preview without mutating the confirmed Order.
- [ ] 3.4 Implement atomic confirmation with state, availability and price revalidation.
- [ ] 3.5 Recalculate monetary fields with Decimal and preserve `delivery_fee`.
- [ ] 3.6 Produce `OrderItemsAdded` for dispatch after commit.

## 4. Conversation and WhatsApp

- [ ] 4.1 Represent initial and addition cart modes explicitly in Conversation.
- [ ] 4.2 Add response intents for preview, confirmation and state conflict.
- [ ] 4.3 Translate those intents in the WhatsApp adapter.
- [ ] 4.4 Clear only the addition draft after success, cancellation or timeout.

## 5. Panel notification

- [ ] 5.1 Persist `OrderItemsAdded` as a pending staff notification.
- [ ] 5.2 Present added lines distinctly from original lines.
- [ ] 5.3 Keep browser notification content free of customer PII.

## 6. Verification

- [ ] 6.1 Test ETA extension and non-extension cases.
- [ ] 6.2 Test price snapshots when the same product is added later.
- [ ] 6.3 Test that an abandoned draft leaves the Order unchanged.
- [ ] 6.4 Test concurrent addition versus transition to `READY` with PostgreSQL.
- [ ] 6.5 Test duplicate confirmation `message_id` applies the addition once.
- [ ] 6.6 Test rollback dispatches no notification.
- [ ] 6.7 Test Alembic upgrade and downgrade against PostgreSQL.
- [ ] 6.8 Run the complete `run-verify` workflow and record its result.

## 7. Documentation

- [ ] 7.1 Document the accepted commit-to-send consistency gap and outbox trigger signals.
- [ ] 7.2 Update `ESTADO.md` and the README session log when the change closes.
