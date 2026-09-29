# WhatsApp inbound message idempotency specification

## ADDED Requirements

### Requirement: Persist a minimal inbound message claim

The system MUST persist successfully processed WhatsApp inbound message
identifiers in `processed_whatsapp_messages`.

The table MUST contain:

- `message_id` as a PostgreSQL `TEXT` primary key;
- `received_at` as a non-null PostgreSQL `TIMESTAMPTZ` with a server-side
  `now()` default.

The table MUST NOT require a numeric surrogate identifier.

#### Scenario: Persist a successfully processed message

- **WHEN** a new inbound `message_id` and its domain effect commit successfully
- **THEN** exactly one row exists for that `message_id`
- **AND** `received_at` is populated by PostgreSQL

#### Scenario: Keep the claim free of customer data

- **WHEN** a processed-message row is stored
- **THEN** it contains no webhook payload, message body, phone number, customer
  name or delivery address

### Requirement: Claim a message atomically

The idempotency repository MUST claim a message with PostgreSQL
`INSERT ... ON CONFLICT DO NOTHING RETURNING message_id` and MUST return an
explicit claimed-or-duplicate result.

It MUST NOT implement claim as a `SELECT` followed by a separate `INSERT`.

#### Scenario: Claim a new message

- **WHEN** no committed row exists for an inbound `message_id`
- **THEN** the insert returns that `message_id`
- **AND** the repository reports the message as claimed

#### Scenario: Receive a sequential duplicate

- **WHEN** a committed row already exists for an inbound `message_id`
- **THEN** the insert returns no row
- **AND** the repository reports the message as duplicate
- **AND** no domain effect is repeated

#### Scenario: Receive the same message concurrently

- **WHEN** two transactions concurrently claim the same new `message_id`
- **THEN** PostgreSQL allows at most one transaction to commit the claim
- **AND** exactly one transaction applies the domain effect
- **AND** the other transaction resolves as duplicate after the winner commits

### Requirement: Couple the claim to the domain transaction

The idempotency insert and every domain effect caused by one inbound message
MUST execute in the same database transaction. The idempotency repository MUST
NOT commit independently.

#### Scenario: Processing succeeds

- **WHEN** a new message is claimed and its domain processing succeeds
- **THEN** the claim and all domain changes commit together

#### Scenario: Processing fails after the claim

- **WHEN** an exception occurs after claiming a new message but before commit
- **THEN** the claim and all partial domain changes roll back together
- **AND** the webhook responds with a 5xx status
- **AND** a later retry can claim and process the same `message_id`

### Requirement: Preserve the global lock order

Inbound processing MUST acquire database coordination points in this order:

1. idempotency insert;
2. `SELECT ... FOR UPDATE` of the customer's Conversation;
3. any required `SELECT ... FOR UPDATE` of Order or Reservation.

#### Scenario: Process a new domain message

- **WHEN** a new inbound message requires Conversation and Order state
- **THEN** the idempotency insert occurs before the Conversation lock
- **AND** the Conversation lock occurs before the Order lock

#### Scenario: Stop a duplicate early

- **WHEN** the idempotency insert identifies a duplicate
- **THEN** processing stops before acquiring the Conversation lock
- **AND** no Order or Reservation lock is acquired

### Requirement: Verify the webhook signature before claiming

The webhook MUST validate the `X-Hub-Signature-256` signature before opening
message processing or writing an idempotency row.

#### Scenario: Reject an invalid signature

- **WHEN** an inbound webhook has an invalid signature
- **THEN** the endpoint responds with HTTP 403
- **AND** no processed-message row is inserted
- **AND** no domain effect occurs

### Requirement: Process batched messages independently

When one webhook payload contains multiple inbound messages, the system MUST
process each `message_id` in its own database transaction.

#### Scenario: One message in a batch fails

- **WHEN** earlier messages in a batch commit successfully
- **AND** a later message fails before commit
- **THEN** the successful messages remain committed
- **AND** the failed message leaves no committed claim or partial domain effect
- **AND** the webhook responds with a 5xx status

#### Scenario: Retry a partially successful batch

- **WHEN** Meta retries a partially successful batch
- **THEN** previously committed message IDs resolve as duplicates
- **AND** the rolled-back message can be claimed and processed again

### Requirement: Dispatch external effects after commit

WhatsApp responses and staff notifications MUST be dispatched only after the
database transaction commits.

#### Scenario: Transaction rolls back

- **WHEN** inbound processing rolls back
- **THEN** no WhatsApp response or staff notification for that processing is
  dispatched

#### Scenario: Transaction commits

- **WHEN** inbound processing commits
- **THEN** external dispatch may begin after the commit completes

#### Scenario: Process crashes after commit and before dispatch

- **WHEN** the database transaction commits
- **AND** the process crashes before an external dispatch completes
- **THEN** the committed `message_id` remains deduplicated
- **AND** the system does not claim exactly-once external delivery

### Requirement: Return stable webhook outcomes

The webhook MUST return HTTP 200 without a useful response body for a
successfully processed message and for a committed duplicate. It MUST return
HTTP 403 for an invalid signature and a 5xx status for a processing failure
that rolled back.

#### Scenario: Receive a committed duplicate

- **WHEN** a duplicate `message_id` is detected
- **THEN** the endpoint responds with HTTP 200
- **AND** it does not repeat domain or external effects

### Requirement: Log idempotency outcomes without PII

The system MAY log the `message_id`, processing duration and an outcome of
`claimed`, `duplicate` or `rolled_back`. It MUST NOT log the full webhook
payload, message body, complete phone number or delivery address.

#### Scenario: Processing fails

- **WHEN** message processing raises an error
- **THEN** the failure log can be correlated by `message_id`
- **AND** it contains no webhook payload or customer PII

### Requirement: Verify idempotency against PostgreSQL

Idempotency and concurrency tests MUST run against PostgreSQL rather than
SQLite.

#### Scenario: Complete idempotency verification

- **WHEN** the change verification suite runs
- **THEN** it covers sequential duplicates, concurrent claims, rollback and
  retry, invalid signatures and partial batch retry against PostgreSQL
- **AND** the complete `run-verify` workflow is green before closing the change
