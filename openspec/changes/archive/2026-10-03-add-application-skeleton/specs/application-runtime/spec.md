## Purpose

Defines how the application starts, how its HTTP surfaces are separated, and how
it reports its own health and database connectivity without leaking internals.

## ADDED Requirements

### Requirement: Application starts only with valid configuration

The system SHALL load and validate its complete configuration before it begins
serving requests. If configuration cannot be validated, the process SHALL
terminate without opening any HTTP listener.

#### Scenario: Valid configuration

- **WHEN** the application starts with a complete environment and valid YAML
  files
- **THEN** it begins serving requests
- **AND** `GET /health` is reachable

#### Scenario: Invalid configuration

- **WHEN** the application starts with invalid configuration as defined by the
  `runtime-configuration` capability
- **THEN** the process terminates with a non-zero exit
- **AND** no request is ever served

### Requirement: Webhook and panel live under separate prefixes

The system SHALL mount the WhatsApp webhook routes and the staff panel routes
under two distinct URL prefixes, neither of which is a prefix of the other. The
webhook prefix SHALL NOT expose any staff route.

#### Scenario: Prefixes are disjoint

- **WHEN** the registered routes of the application are inspected
- **THEN** every webhook route path starts with the webhook prefix
- **AND** every panel route path starts with the panel prefix
- **AND** neither prefix starts with the other

#### Scenario: Webhook exposes no staff route

- **WHEN** the routes under the webhook prefix are listed
- **THEN** none of them is a route registered by the panel router

#### Scenario: Staff path requested under the webhook prefix

- **WHEN** a client sends a request to a panel route path re-rooted under the
  webhook prefix
- **THEN** the system returns HTTP 404 with the uniform error body

### Requirement: Health check reports application and database status

The system SHALL expose `GET /health` outside both the webhook and the panel
prefixes. The response SHALL always carry a JSON body that reports the
application status and the database status as separate fields. The database
check SHALL be bounded by a configured timeout so the endpoint never hangs on
an unreachable database.

#### Scenario: Database reachable

- **GIVEN** the database accepts connections and answers a trivial query
- **WHEN** a client sends `GET /health`
- **THEN** the system returns HTTP 200
- **AND** the body reports the overall status as healthy
- **AND** the body reports the application as up
- **AND** the body reports the database as up

#### Scenario: Database unreachable

- **GIVEN** the database refuses connections or does not answer within the
  configured timeout
- **WHEN** a client sends `GET /health`
- **THEN** the system returns HTTP 503
- **AND** the response has a JSON body; it is never an empty 500
- **AND** the body reports the overall status as degraded
- **AND** the body reports the application as up
- **AND** the body reports the database as down
- **AND** the response is returned within the configured database timeout plus
  a bounded margin

#### Scenario: Health response leaks no internals

- **WHEN** a client sends `GET /health` with the database either reachable or
  unreachable
- **THEN** the response body does not contain the database connection string
- **AND** does not contain the database user, password, host or port
- **AND** does not contain the PostgreSQL server version or any library version
- **AND** does not contain any table name or SQL text
- **AND** does not contain the text of the underlying database error

#### Scenario: Health failure is logged without secrets

- **GIVEN** the database is unreachable
- **WHEN** a client sends `GET /health`
- **THEN** a log record notes that the database check failed and the error
  type
- **AND** that log record does not contain the connection string or password
