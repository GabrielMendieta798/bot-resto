## Purpose

Defines the application log format and the personal-data masking every log
record goes through, so that no full phone number reaches the logs.

## ADDED Requirements

### Requirement: Structured log records

The system SHALL emit every application log record as a single line of JSON
containing at least the UTC timestamp, the level, the logger name and the
message, plus any structured fields attached to the record. The log level
SHALL be configurable.

#### Scenario: Record shape

- **WHEN** application code logs `health check failed` at WARNING with a field
  `component=database`
- **THEN** the output is one line that parses as JSON
- **AND** it contains the timestamp in UTC, the level `WARNING`, the logger
  name, the message and `component`

#### Scenario: Level filtering

- **GIVEN** the configured log level is `WARNING`
- **WHEN** application code logs a record at INFO
- **THEN** nothing is written

### Requirement: Phone numbers are masked

The system SHALL mask every phone number that appears in a log record, both
inside the message text and inside structured fields, keeping at most the last
four digits. Masking SHALL also apply to the formatted stacktrace and to
records emitted by third-party libraries through the root logger.

#### Scenario: Phone in the message

- **WHEN** application code logs `received from 5491122334455`
- **THEN** the output does not contain `5491122334455`
- **AND** the output does not contain any run of more than four of its
  consecutive digits
- **AND** the output still contains `4455`

#### Scenario: Phone in E.164 with formatting

- **WHEN** application code logs `+54 9 11 2233-4455`
- **THEN** the output does not contain the full number with or without its
  separators

#### Scenario: Phone in a structured field

- **WHEN** application code logs a record with a field `phone=5491122334455`
- **THEN** the output does not contain `5491122334455`

#### Scenario: Phone inside an exception

- **WHEN** an exception whose message contains `5491122334455` is logged with
  its stacktrace
- **THEN** the output does not contain `5491122334455`

#### Scenario: Short numbers are not masked

- **WHEN** application code logs `order 4521 has 3 items`
- **THEN** the output contains `4521` and `3` unchanged
