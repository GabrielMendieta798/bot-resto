## Purpose

Identifies every customer by their WhatsApp number: the first message from a
number creates the customer, and every later message from that number, even a
simultaneous one, resolves to that same customer.

## ADDED Requirements

### Requirement: Get or create a customer by phone

Given a phone number in canonical form, the registry SHALL return the customer
with that number, creating it when none exists. A number SHALL never resolve to
more than one customer.

#### Scenario: New number

- **GIVEN** no customer has phone `5491155551234`
- **WHEN** a customer is obtained for `5491155551234`
- **THEN** a customer with that phone is created and returned with its
  identifier and creation timestamp

#### Scenario: Known number

- **GIVEN** a customer with phone `5491155551234` and identifier `N`
- **WHEN** a customer is obtained for `5491155551234`
- **THEN** the customer with identifier `N` is returned
- **AND** the number of customers with that phone stays one

### Requirement: Only canonical phone numbers are accepted

The registry SHALL accept a phone number only in canonical form: ASCII digits
only, from 8 to 15 of them (E.164 without the `+`). Any other value SHALL raise
an invalid-input error (`InvalidInputError`, `400` by `API-3`) for field
`phone`, without touching the database. Turning what the channel sends into
canonical form is the channel adapter's job, not the registry's.

#### Scenario: Formatted number

- **WHEN** a customer is obtained for `+54 9 11 5555-1234`
- **THEN** an invalid-input error is raised for field `phone`

#### Scenario: Letters, empty or wrong length

- **WHEN** a customer is obtained for `54911abc1234`, for an empty value, for
  `1234567` (7 digits) or for `1234567890123456` (16 digits)
- **THEN** an invalid-input error is raised for field `phone`

#### Scenario: Non-ASCII digits

- **WHEN** a customer is obtained for a number written with digits from another
  script, such as `٥٤٩١١٥٥٥٥١٢٣٤`
- **THEN** an invalid-input error is raised for field `phone`

#### Scenario: Boundary lengths

- **WHEN** a customer is obtained for `12345678` (8 digits) or for
  `123456789012345` (15 digits)
- **THEN** the customer is returned

### Requirement: Concurrent requests for the same number create one customer

Two requests for the same new number, running at the same time in separate
transactions on separate database connections, SHALL end with exactly one
customer, and both SHALL return the same identifier. The guarantee SHALL come
from the database unique index on the phone, not from checking for an existing
customer before inserting (`VER-2`).

#### Scenario: Two simultaneous first messages

- **GIVEN** no customer has phone `5491166667777`
- **WHEN** two requests for `5491166667777` run in parallel, each in its own
  transaction and connection, and both transactions commit
- **THEN** exactly one customer with that phone exists
- **AND** both requests returned the same identifier

#### Scenario: Second request waits for the first

- **GIVEN** one request for a new number has inserted the customer and has not
  committed yet
- **WHEN** a second request for the same number starts
- **THEN** the second request does not finish before the first transaction
  ends
- **AND** after the first commits, the second returns the identifier the first
  created

#### Scenario: First transaction rolls back

- **GIVEN** one request for a new number has inserted the customer and a second
  request for the same number is waiting on it
- **WHEN** the first transaction rolls back
- **THEN** the second request creates the customer and returns its identifier

#### Scenario: No existence check before inserting

- **WHEN** a customer is obtained for a number
- **THEN** the first statement the registry sends to the customers table is the
  insert, not a query for an existing row

### Requirement: The phone number never appears in errors or logs

No error raised by the registry, and no log record it produces, SHALL contain
the full phone number, including the exception chain of a rejected number
(`SEC-3` and the requirement "Exception messages carry no customer data" of
`structured-logging`). The customer returned SHALL NOT show the phone in its
text representation, so that logging or printing it leaks nothing.

#### Scenario: Rejected number

- **WHEN** a customer is obtained for `+54 9 11 5555-1234` and the error is
  raised
- **THEN** neither the error message, nor its text representation, nor any
  exception in its chain contains `5555-1234` or `5555`
- **AND** the captured log output does not contain them

#### Scenario: Valid number

- **WHEN** a customer is obtained for `5491155551234`
- **THEN** the captured log output does not contain `5491155551234`

#### Scenario: Representation of a customer

- **WHEN** a returned customer is converted to text with `str` or `repr`
- **THEN** the text does not contain its phone number
