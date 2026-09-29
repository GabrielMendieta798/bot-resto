# WhatsApp webhook specification delta

## ADDED Requirements

### Requirement: Persist the inbound message identity

The system SHALL use the opaque WhatsApp `message_id` as the primary key of a
minimal processed-message record.

#### Scenario: A new message is claimed

- **GIVEN** the webhook signature is valid
- **AND** no committed row exists for the `message_id`
- **WHEN** processing begins
- **THEN** the system inserts the `message_id` in the current transaction
- **AND** `received_at` is populated as a UTC timestamp
- **AND** no webhook payload or customer PII is persisted in the record

### Requirement: Process a message once

The system SHALL claim a message with a single PostgreSQL insert using conflict
handling rather than a select-then-insert sequence.

#### Scenario: Meta retries a committed message

- **GIVEN** a committed row already exists for a `message_id`
- **WHEN** the same `message_id` is received again
- **THEN** the webhook returns HTTP 200 without a useful body
- **AND** no Conversation lock is acquired
- **AND** no domain effect or outgoing send is repeated

#### Scenario: Two requests claim the same message concurrently

- **GIVEN** no committed row initially exists for a `message_id`
- **WHEN** two transactions attempt to claim it concurrently
- **THEN** PostgreSQL allows only one transaction to retain the row
- **AND** exactly one transaction applies the domain effect
- **AND** the other request completes as a duplicate

### Requirement: Share the domain transaction

The system SHALL persist the processed-message row and all effects of that
inbound message in one transaction.

#### Scenario: Processing succeeds

- **WHEN** the domain effect commits successfully
- **THEN** the processed-message row commits with it
- **AND** external responses and notifications are attempted after commit

#### Scenario: Processing fails after the claim

- **GIVEN** the `message_id` was inserted in the current transaction
- **WHEN** processing raises an error before commit
- **THEN** the processed-message row and domain effects roll back together
- **AND** the webhook returns a 5xx response
- **AND** a later retry can claim and process the same `message_id`

### Requirement: Preserve lock order

The system SHALL acquire resources in the order defined by `CONV-9`.

#### Scenario: A message modifies an order

- **WHEN** an inbound message needs Conversation and Order locks
- **THEN** the system first attempts the idempotency insert
- **AND** then locks Conversation
- **AND** then locks Order
- **AND** no code path acquires them in another order

### Requirement: Validate authenticity before idempotency

The system SHALL reject an invalid webhook signature before inserting any
processed-message record.

#### Scenario: Signature is invalid

- **WHEN** a POST webhook has an invalid `X-Hub-Signature-256`
- **THEN** the webhook returns HTTP 403
- **AND** no processed-message row is created
- **AND** no domain processing occurs

### Requirement: Process batched messages independently

The system SHALL give every `message_id` in a batched webhook an independent
transactional outcome.

#### Scenario: One message in a batch fails

- **GIVEN** a webhook contains multiple new `message_id` values
- **AND** one message fails while another commits
- **WHEN** Meta retries the webhook
- **THEN** the committed message is recognized as a duplicate
- **AND** the rolled-back message can be claimed again
- **AND** the committed domain effect is not repeated

### Requirement: Keep processed-message records minimal

The system SHALL NOT store webhook payloads, customer messages, phone numbers,
delivery addresses or outbound delivery states in
`processed_whatsapp_messages`.

#### Scenario: Inspect a processed-message row

- **WHEN** a processed-message row is read
- **THEN** it contains only the opaque `message_id` and `received_at`

