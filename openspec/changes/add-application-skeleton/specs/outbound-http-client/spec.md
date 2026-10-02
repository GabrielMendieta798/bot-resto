## Purpose

Provides the single outbound HTTP client that adapters use to call external
services, so that no outbound call can hang without a time limit.

## ADDED Requirements

### Requirement: Explicit timeouts on every outbound request

The system SHALL perform outbound HTTP calls through one shared client whose
connect, read, write and pool timeouts are all set explicitly from
configuration. No outbound request SHALL run without a finite timeout.

#### Scenario: Timeouts come from configuration

- **GIVEN** configuration sets connect, read, write and pool timeouts
- **WHEN** the client is created
- **THEN** each of the four timeouts equals its configured value
- **AND** none of them is unlimited

#### Scenario: Server never answers

- **GIVEN** a server that accepts the connection but never sends a response
- **AND** a read timeout of 0.5 seconds
- **WHEN** the client sends a request to it
- **THEN** the client raises the outbound-timeout error
- **AND** control returns to the caller in less than 5 seconds

#### Scenario: Timeout error leaks no request details

- **WHEN** the outbound-timeout error is raised
- **THEN** its message does not contain the request headers, body or query
  string

### Requirement: Client lifecycle follows the application

The system SHALL create the shared client when the application starts and
close it when the application stops.

#### Scenario: Shutdown closes the client

- **WHEN** the application shuts down
- **THEN** the shared client is closed
- **AND** a later request through it fails instead of opening a new connection

### Requirement: Client carries no channel logic

The shared client SHALL NOT contain WhatsApp-specific URLs, tokens, headers or
payload handling.

#### Scenario: No channel coupling

- **WHEN** the client module is inspected
- **THEN** it does not import or reference any WhatsApp library, URL or token
