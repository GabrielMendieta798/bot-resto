# Orders specification delta

## ADDED Requirements

### Requirement: Prepare an addition without mutating the order

The system SHALL keep newly selected lines in the locked Conversation cart
until the customer explicitly confirms the addition.

#### Scenario: Customer abandons an addition

- **GIVEN** a customer has one Order in `RECEIVED` or `PREPARING`
- **AND** the customer selected additional products
- **WHEN** the flow is cancelled or expires before confirmation
- **THEN** the confirmed Order, its lines, amounts and ETA remain unchanged
- **AND** the addition draft is removed from Conversation

### Requirement: Show the consequences before confirmation

The system SHALL show the additional amount, resulting total and resulting
estimated delay before asking the customer to confirm an addition.

#### Scenario: A slower new item extends the ETA

- **GIVEN** the existing Order has 10 minutes of estimated kitchen time left
- **AND** a new item has an estimated preparation time of 30 minutes
- **WHEN** the addition preview is calculated
- **THEN** the resulting estimated kitchen delay is 30 minutes
- **AND** the preparation times are not summed

#### Scenario: A faster new item does not extend the ETA

- **GIVEN** the existing Order has 10 minutes of estimated kitchen time left
- **AND** a new item has an estimated preparation time of 5 minutes
- **WHEN** the addition preview is calculated
- **THEN** the resulting estimated kitchen delay remains 10 minutes

### Requirement: Confirm an addition atomically

The system SHALL append all confirmed lines and update amounts and ETA in one
transaction after locking and revalidating the active Order.

#### Scenario: Addition to a received order

- **GIVEN** the customer's active Order is `RECEIVED`
- **AND** all new MenuItems remain available
- **WHEN** the customer confirms the addition
- **THEN** new OrderItem rows are appended
- **AND** existing OrderItem rows are not altered
- **AND** `subtotal`, `total` and `estimated_kitchen_ready_at` are updated
- **AND** `delivery_fee` remains unchanged
- **AND** the Order remains `RECEIVED`

#### Scenario: Addition to an order in preparation

- **GIVEN** the customer's active Order is `PREPARING`
- **AND** the customer was warned that new lines enter kitchen immediately
- **WHEN** the customer confirms the addition
- **THEN** the addition is committed atomically
- **AND** the Order remains `PREPARING`
- **AND** the new lines cannot be cancelled individually

### Requirement: Reject an addition outside the allowed window

The system SHALL accept additions only while the Order is `RECEIVED` or
`PREPARING`.

#### Scenario: Staff marks the order ready before confirmation

- **GIVEN** the customer prepared an addition draft
- **AND** staff changed the Order to `READY`
- **WHEN** the customer confirms the addition
- **THEN** no new OrderItem is persisted
- **AND** no amount or ETA changes
- **AND** the customer receives an order-state conflict response

#### Scenario: Order is terminal

- **GIVEN** an Order is `DELIVERED`, `CANCELLED_BY_CUSTOMER` or
  `CANCELLED_BY_STAFF`
- **WHEN** the customer tries to start or confirm an addition
- **THEN** the addition is rejected

### Requirement: Preserve snapshots for every addition

The system SHALL persist each newly confirmed line separately with the current
price and confirmation timestamp.

#### Scenario: Same product is added after its price changes

- **GIVEN** an existing line captured an earlier unit price
- **AND** the MenuItem price changed before the addition
- **WHEN** the same MenuItem is added and confirmed
- **THEN** a new OrderItem row captures the current unit price
- **AND** the original line retains its previous unit price

### Requirement: Apply an addition once

The system SHALL rely on inbound message idempotency so the same confirmation
message cannot apply an addition more than once.

#### Scenario: Meta retries the confirmation message

- **GIVEN** an addition was committed for a WhatsApp `message_id`
- **WHEN** the same `message_id` is received again
- **THEN** no additional OrderItem is inserted
- **AND** totals and ETA are not recalculated a second time

### Requirement: Notify staff after commit

The system SHALL emit `OrderItemsAdded` only after the addition transaction
commits.

#### Scenario: Addition commits successfully

- **WHEN** an addition transaction commits
- **THEN** `OrderItemsAdded` identifies the Order, added-line count, updated
  total and updated delay
- **AND** the event contains no customer PII

#### Scenario: Addition transaction rolls back

- **WHEN** an addition transaction rolls back
- **THEN** no `OrderItemsAdded` event is dispatched

## MODIFIED Requirements

### Requirement: One non-terminal order per customer

The system SHALL prevent a customer from having more than one non-terminal
Order. Additional products SHALL be appended to the existing Order only during
the allowed addition window.

#### Scenario: Customer already has an active order

- **GIVEN** a customer has an Order in any non-terminal state
- **WHEN** the customer attempts to create another Order
- **THEN** creation is rejected by the domain
- **AND** the database uniqueness invariant prevents concurrent creation

