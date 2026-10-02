## Purpose

Defines how the application loads its environment settings and per-instance YAML
files, validates them as a typed whole at startup, and refuses to run when any
of them is missing, malformed or unsafe.

## ADDED Requirements

### Requirement: Configuration sources

The system SHALL read its configuration from four sources: environment
variables (optionally provided through a `.env` file outside version control),
`config/restaurant.yaml`, `config/messages.yaml` and `config/http_errors.yaml`.
The paths of the three YAML files SHALL be overridable by environment
variables. Secrets SHALL only come from the environment, never from the YAML
files.

#### Scenario: All sources present and valid

- **WHEN** the environment defines every required key and the three YAML files
  contain every required key with values of the right shape
- **THEN** the configuration loads successfully
- **AND** the application starts

### Requirement: Customer copy is kept apart from internal text

`config/messages.yaml` SHALL contain only customer-facing copy, which the
restaurant owner edits (`TXT-2`). The texts of HTTP error responses SHALL live
in `config/http_errors.yaml` and SHALL NOT appear in `config/messages.yaml`.

#### Scenario: Error texts placed in the customer copy file

- **GIVEN** `config/messages.yaml` contains an HTTP error section
- **WHEN** the application starts
- **THEN** the application does not start
- **AND** the error names the unexpected key in `messages.yaml`

#### Scenario: Committed customer copy file holds no internal text

- **WHEN** the committed `config/messages.yaml` is inspected
- **THEN** it contains no HTTP error code or error message

### Requirement: Missing keys prevent startup without revealing values

The system SHALL refuse to start when a required key is missing from the
environment or from any of the YAML files. The startup error SHALL name the source
and the full path of every missing or invalid key, and SHALL NOT contain the
value of any configuration key, present or missing.

#### Scenario: Required environment key missing

- **GIVEN** `DATABASE_URL` is not defined in the environment or `.env`
- **WHEN** the application starts
- **THEN** the application does not start
- **AND** the error names `DATABASE_URL` as missing
- **AND** the error does not contain the value of any other environment key

#### Scenario: Required YAML key missing

- **GIVEN** `config/restaurant.yaml` lacks a required nested key
- **WHEN** the application starts
- **THEN** the application does not start
- **AND** the error names `restaurant.yaml` and the dotted path of the missing
  key
- **AND** the error does not contain any value read from the file

#### Scenario: Value has the wrong shape

- **GIVEN** a key holds a value that does not match its declared type
- **WHEN** the application starts
- **THEN** the application does not start
- **AND** the error names the key and the expected type
- **AND** the error does not echo the offending value

#### Scenario: Secret-looking value never appears in the error

- **GIVEN** `DATABASE_URL` holds a value containing a password
- **AND** another required key is missing
- **WHEN** the application starts
- **THEN** the startup error, including any chained exception printed with it,
  does not contain the `DATABASE_URL` value or the password

#### Scenario: Unknown key in a YAML file

- **GIVEN** a YAML file contains a key that its model does not declare
- **WHEN** the application starts
- **THEN** the application does not start
- **AND** the error names the unexpected key

### Requirement: Malformed or absent YAML prevents startup

The system SHALL refuse to start when any of the YAML files is absent,
unparseable, or does not have a mapping at its top level, and when
`restaurant.yaml` or `http_errors.yaml` is empty. The error SHALL name the file
and, for a parse error, the line and column, without reproducing the file
content.

`messages.yaml` is the only exception to the empty rule: while no change has
added customer copy, a `messages.yaml` with no content (only comments) SHALL
be accepted as an empty set of texts. It SHALL still be required to exist, and
an unknown key in it SHALL still prevent startup.

#### Scenario: Comments-only messages file

- **GIVEN** `config/messages.yaml` contains only comments
- **WHEN** the application starts
- **THEN** the configuration loads successfully

#### Scenario: Comments-only restaurant file

- **GIVEN** `config/restaurant.yaml` contains only comments
- **WHEN** the application starts
- **THEN** the application does not start
- **AND** the error names `restaurant.yaml`

#### Scenario: Messages file absent

- **GIVEN** `config/messages.yaml` does not exist at the configured path
- **WHEN** the application starts
- **THEN** the application does not start
- **AND** the error names the missing file

#### Scenario: YAML syntax error

- **GIVEN** `config/messages.yaml` contains invalid YAML syntax
- **WHEN** the application starts
- **THEN** the application does not start
- **AND** the error names `messages.yaml` and the line and column of the
  problem
- **AND** the error does not include a snippet of the file content

#### Scenario: YAML file absent

- **GIVEN** `config/restaurant.yaml` does not exist at the configured path
- **WHEN** the application starts
- **THEN** the application does not start
- **AND** the error names the missing file

#### Scenario: YAML top level is not a mapping

- **GIVEN** a YAML file whose top level is a list or a scalar
- **WHEN** the application starts
- **THEN** the application does not start

### Requirement: Business values come from documented defaults

The system SHALL take every configurable business value listed in `GEN-7`
(cart and inactivity timeouts, retry limit, delivery zones and fees,
reservation window and party cap, reservation escalation time, opening hours
including split shifts, and the local time zone) from `config/restaurant.yaml`.
The committed file SHALL contain documented defaults and a header stating that
the final values come from the five open questions to the restaurant owner,
not from a technical decision. Monetary values SHALL be parsed as exact
decimals, never as floating point.

#### Scenario: Committed defaults load

- **WHEN** the application starts with the committed `config/restaurant.yaml`
- **THEN** the configuration loads successfully

#### Scenario: Delivery fee is an exact decimal

- **WHEN** the configuration loads a delivery fee of `1500.10`
- **THEN** the loaded value equals the decimal `1500.10` exactly

#### Scenario: Unknown time zone

- **GIVEN** `config/restaurant.yaml` declares a time zone that does not exist
- **WHEN** the application starts
- **THEN** the application does not start
- **AND** the error names the time zone key

### Requirement: Every text key referenced by code exists at startup

The system SHALL verify at startup that every text key referenced by code
exists in the file that owns it (`messages.yaml` for customer copy,
`http_errors.yaml` for HTTP error texts), so that a missing key fails the
startup and never a response.

#### Scenario: Referenced error text key missing

- **GIVEN** an error type references an error text key
- **AND** `config/http_errors.yaml` does not define that key
- **WHEN** the application starts
- **THEN** the application does not start
- **AND** the error names `http_errors.yaml` and the missing key

#### Scenario: Committed error texts cover every error type

- **WHEN** the application starts with the committed `config/http_errors.yaml`
- **THEN** every error type defined in code finds its text key

### Requirement: SQL echo is configuration-controlled and off by default

The system SHALL keep SQL statement logging disabled unless configuration
explicitly enables it, and SHALL refuse to start if it is enabled while the
environment is production.

#### Scenario: Echo off by default

- **GIVEN** the environment does not define the SQL echo setting
- **WHEN** the database engine is created
- **THEN** SQL statement logging is disabled

#### Scenario: Echo enabled by configuration

- **GIVEN** the SQL echo setting is `true` and the environment is development
- **WHEN** the database engine is created
- **THEN** SQL statement logging is enabled

#### Scenario: Echo enabled in production

- **GIVEN** the SQL echo setting is `true` and the environment is production
- **WHEN** the application starts
- **THEN** the application does not start
- **AND** the error names the SQL echo setting

### Requirement: Environment template lists every key

The repository SHALL contain a `.env.example` that lists every environment key
the settings read, required or optional, with no real value.

#### Scenario: Template matches the settings

- **WHEN** the keys in `.env.example` are compared with the keys the settings
  declare
- **THEN** both sets are equal

#### Scenario: Template carries no real values

- **WHEN** `.env.example` is inspected
- **THEN** no key holds a credential, a real host or a real token
