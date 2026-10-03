## Purpose

Defines how failures are turned into HTTP responses: a fixed mapping from error
categories to the status codes of `API-3`, a single error body shape for every
endpoint, and a guarantee that no internal detail leaves the process.

## ADDED Requirements

### Requirement: Uniform error body

Every error response the application produces SHALL have a JSON body with an
`error` object containing a machine-readable `code`, a human-readable
`message`, and a `field` that names the offending input when one applies and
is `null` otherwise. The `message` SHALL come from `config/http_errors.yaml`,
never from an exception's text and never from the customer copy in
`config/messages.yaml`.

#### Scenario: Shape of an error

- **WHEN** any request ends in an error status
- **THEN** the body is `{"error": {"code": ..., "message": ..., "field": ...}}`
- **AND** it contains no other top-level key

### Requirement: Error categories map to API-3 status codes

The system SHALL provide error categories that domain and adapter code raise
without depending on the web framework, and SHALL translate each category to
its `API-3` status code. A subclass SHALL inherit the status code of its
nearest mapped ancestor.

| Category                          | Status |
|-----------------------------------|--------|
| invalid input                     | 400    |
| not authenticated                 | 401    |
| permission denied                 | 403    |
| resource not found                | 404    |
| state conflict                    | 409    |
| invalid state transition          | 409    |

#### Scenario: Not found

- **WHEN** a handler raises the resource-not-found category
- **THEN** the system returns HTTP 404 with code `not_found`

#### Scenario: Invalid state transition

- **WHEN** a handler raises the invalid-state-transition category
- **THEN** the system returns HTTP 409, not 400
- **AND** the code is `invalid_state_transition`

#### Scenario: Invalid input names the field

- **WHEN** a handler raises the invalid-input category for field `quantity`
- **THEN** the system returns HTTP 400
- **AND** `error.field` is `quantity`

#### Scenario: Not authenticated and permission denied

- **WHEN** a handler raises the not-authenticated category
- **THEN** the system returns HTTP 401
- **WHEN** a handler raises the permission-denied category
- **THEN** the system returns HTTP 403

#### Scenario: Subclass without its own mapping

- **GIVEN** a new error type that subclasses the state-conflict category
- **WHEN** a handler raises it
- **THEN** the system returns HTTP 409

### Requirement: Payload validation failures return 400

The system SHALL answer a request whose body, query or path parameters fail
schema validation with HTTP 400 and the uniform body, naming the first
offending field. It SHALL NOT return the framework default 422, and SHALL NOT
echo the rejected input.

#### Scenario: Body fails validation

- **WHEN** a client sends a body whose field `quantity` has the wrong type
- **THEN** the system returns HTTP 400 with code `invalid_input`
- **AND** `error.field` is `quantity`
- **AND** the body does not contain the submitted value

### Requirement: Framework HTTP errors use the uniform body

The system SHALL render errors raised by the framework itself, such as an
unknown route or an unsupported method, with the uniform body and their
original status code.

#### Scenario: Unknown route

- **WHEN** a client requests a path that no route matches
- **THEN** the system returns HTTP 404 with code `not_found`

#### Scenario: Unsupported method

- **WHEN** a client sends `POST /health`
- **THEN** the system returns HTTP 405 with the uniform body

#### Scenario: Framework authentication and conflict errors

- **WHEN** the framework or a library raises an HTTP error with status 401,
  403 or 409
- **THEN** the code is `not_authenticated`, `permission_denied` or `conflict`
  respectively
- **AND** any custom detail of that error is not returned

### Requirement: Unexpected errors never leak internals

The system SHALL answer any exception outside the mapped categories with HTTP
500 and the uniform body with code `internal_error`. The response SHALL NOT
contain a stacktrace, exception type, exception message, file path, SQL, or
table name. The full stacktrace SHALL be written to the log only, together
with the request method and path but without the query string.

#### Scenario: Unhandled exception

- **WHEN** a handler raises an exception whose message contains
  `SELECT * FROM customers WHERE phone='5491122334455'`
- **THEN** the system returns HTTP 500 with code `internal_error`
- **AND** the response body contains none of `Traceback`, the exception type,
  the exception message, `customers`, or `SELECT`
- **AND** the log contains the stacktrace of that exception
- **AND** the logged phone number is masked

#### Scenario: Database error escapes a handler

- **WHEN** a handler lets a database driver error propagate
- **THEN** the system returns HTTP 500 with code `internal_error`
- **AND** the response body contains no SQL, table name or driver message

#### Scenario: Any other exception still yields the uniform 500

- **WHEN** a handler raises an arbitrary exception such as `ValueError`
- **THEN** the system returns HTTP 500 with the uniform body and code
  `internal_error`
- **AND** the exception does not escape the application

### Requirement: Unexpected errors are logged once and without customer data

The log of an unexpected error SHALL contain its type and stack frames, and
SHALL NOT contain SQL parameters, driver row details or rejected input values.
Each unexpected error SHALL produce exactly one log record.

#### Scenario: Database error carrying customer data

- **WHEN** a handler raises a database integrity error whose parameters and
  driver detail contain a delivery address
- **THEN** the system returns HTTP 500 with the uniform body
- **AND** exactly one log record describes the error, with its type and stack
  frames
- **AND** no log record contains the address
