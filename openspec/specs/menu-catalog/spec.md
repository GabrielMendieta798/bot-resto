# menu-catalog Specification

## Purpose
Lets the customer browse the menu by category and lets the staff take items off
the menu, put them back and edit them, without ever deleting an item or
altering the price of an order already confirmed.
## Requirements
### Requirement: Categories with something to offer

The menu SHALL list a category only when at least one of its items is
available. Each category appears once, and the list is ordered by name.

#### Scenario: Category with available items is listed

- **GIVEN** category `Pastas` has one available item and one unavailable item
- **WHEN** the categories are listed
- **THEN** `Pastas` appears exactly once

#### Scenario: Category with every item sold out is hidden

- **GIVEN** every item of category `Parrilla` is unavailable
- **WHEN** the categories are listed
- **THEN** `Parrilla` does not appear

#### Scenario: Last available item sold out

- **GIVEN** category `Postres` has exactly one available item
- **WHEN** that item is marked unavailable and the categories are listed again
- **THEN** `Postres` no longer appears

### Requirement: Available items of a category for the customer

The menu SHALL return the available items of one category, each with its
identifier, category, name, description, price and estimated preparation time.
Unavailable items SHALL NOT be returned. The order SHALL be deterministic: by
name and, for equal names, by identifier. The category is matched exactly as
listed by the categories query.

#### Scenario: Unavailable items are excluded

- **GIVEN** category `Parrilla` has `Bondiola` available and `Vacío` unavailable
- **WHEN** the available items of `Parrilla` are listed
- **THEN** the result contains `Bondiola` with its name, price and estimated
  time
- **AND** the result does not contain `Vacío`

#### Scenario: Deterministic order

- **GIVEN** three available items of one category named `Ravioles`, `Ñoquis`
  and `Ravioles`, the two `Ravioles` with different identifiers
- **WHEN** the available items of that category are listed twice
- **THEN** both results have the same order, sorted by name
- **AND** the two `Ravioles` appear by ascending identifier

#### Scenario: Unknown category

- **WHEN** the available items of a category that does not exist are listed
- **THEN** the result is an empty list and no error is raised

### Requirement: Full menu for the staff

The menu SHALL return every item, available or not, each with its availability,
in the same order as the customer listing: by name and, for equal names, by
identifier.

#### Scenario: Staff sees sold-out items

- **GIVEN** `Bondiola` is available and `Vacío` is unavailable
- **WHEN** the staff lists all items
- **THEN** both appear, `Bondiola` with availability true and `Vacío` with
  availability false

#### Scenario: Same order as the customer listing

- **WHEN** the staff lists all items
- **THEN** the items are sorted by name and, for equal names, by identifier

### Requirement: Item lookup by identifier

The menu SHALL return a single item by its identifier, whether available or
not.

#### Scenario: Unavailable item is still found

- **GIVEN** `Vacío` is unavailable
- **WHEN** it is looked up by its identifier
- **THEN** it is returned with availability false

### Requirement: Availability is set explicitly and never deletes

Changing availability SHALL set it to the value given, not toggle it. Marking an
item unavailable SHALL only change its availability: the item keeps existing
with all its other data (`DAT-5`). Setting the value an item already has SHALL
succeed and leave it unchanged.

#### Scenario: Sold out keeps the item

- **GIVEN** `Bondiola` is available
- **WHEN** its availability is set to false
- **THEN** the row for `Bondiola` still exists in the database
- **AND** its name, description, price, estimated time and category are
  unchanged
- **AND** it no longer appears among the available items of its category

#### Scenario: Back on the menu

- **GIVEN** `Bondiola` is unavailable
- **WHEN** its availability is set to true
- **THEN** it appears again among the available items of its category

#### Scenario: Setting the same value twice

- **WHEN** the availability of an item is set to false twice in a row
- **THEN** both calls succeed and the item ends unavailable
- **AND** the same holds for setting true twice in a row

### Requirement: Unknown item identifier

Looking up, changing the availability of, or editing an item that does not
exist SHALL raise a not-found error (`NotFoundError`, `404` by `API-3`). The
error message SHALL carry the identifier and nothing else about the request. An
identifier that cannot exist (zero, negative, or beyond the identifier range)
SHALL be reported as not found, never as a database error.

#### Scenario: Missing item

- **WHEN** item `999999` is looked up, has its availability set, or is edited,
  and it does not exist
- **THEN** a not-found error is raised
- **AND** its message contains `999999` and no other value from the request

#### Scenario: Identifier out of range

- **WHEN** item `0`, `-1` or `2**63` is looked up
- **THEN** a not-found error is raised and no database error occurs

### Requirement: Partial edit of an item

The staff SHALL be able to edit any subset of an item's name, description,
price and estimated preparation time. An edit is expressed as a validated edit
object in which a field can be absent (not part of the edit) or present, and
present with an empty value is different from absent. Fields absent from the
edit SHALL keep their value. The edit SHALL NOT change the category, the
availability or the identifier. An edit with no field present SHALL be
rejected with an invalid-input error. Business rules are checked before the
item is looked up.

#### Scenario: Editing only the price

- **GIVEN** `Bondiola` with a name, description, price `8500.00`, estimated
  time `25`, category `Parrilla` and availability true
- **WHEN** only its price is edited to `9200.00`
- **THEN** its price is `9200.00`
- **AND** its name, description, estimated time, category, availability and
  creation timestamp are unchanged

#### Scenario: Absent and empty are different

- **GIVEN** an item with a description
- **WHEN** an edit containing only the price is applied
- **THEN** the description is unchanged
- **AND WHEN** an edit with the description present and empty is applied
- **THEN** the item has no description

#### Scenario: Name is trimmed

- **WHEN** an item's name is edited to `"  Bondiola braseada  "`
- **THEN** the stored name is `Bondiola braseada`

#### Scenario: Empty edit

- **WHEN** an edit with no field present is applied
- **THEN** an invalid-input error is raised and the item is unchanged

### Requirement: Edit shape is validated by the edit object

The edit object SHALL reject, with a validation error that follows the
validation path of the `error-contract` capability (`400` with the uniform
body and the field when it is the request payload, never echoing the input),
any edit whose shape is wrong: a field outside name, description, price and
estimated time (including category, availability and identifier); a name that
is empty, blank, longer than 150 characters, or explicitly null; a price that
is not exact (a binary floating-point number, including a JSON number with a
fractional part, or a boolean), is not finite, is text that is not decimal
text, or is explicitly null; an estimated time that is a boolean, a
floating-point number, text that is not integer text, or explicitly null.
Shape is checked when the edit object is built, before the service is called
(`VAL-1`).

Because panel forms send every value as text and JSON payloads send numbers,
the edit object SHALL also accept, as exact values:

- **Price:** a decimal, an integer, or *decimal text*: ASCII digits with an
  optional leading `-`, an optional fractional part and an optional exponent
  (`9200.00`, `1E+3`), with surrounding spaces ignored.
- **Estimated time:** an integer or *integer text*: ASCII digits with an
  optional leading `-`, with surrounding spaces ignored.

A negative value in text passes shape and is rejected by the business rules,
like a negative number.

#### Scenario: Field outside the edit

- **WHEN** an edit object is built with the category, the availability or the
  identifier
- **THEN** building it fails with a validation error for that field

#### Scenario: Blank, long or null name

- **WHEN** an edit object is built with name `""`, `"   "`, 151 characters, or
  an explicit null
- **THEN** building it fails with a validation error for field `name`

#### Scenario: Price that is not exact

- **WHEN** an edit object is built with a price that is a binary
  floating-point number (`9200.5`, `1500.0`), `true`, `NaN`, infinity, or an
  explicit null
- **THEN** building it fails with a validation error for field `price`

#### Scenario: Price as exact decimal text

- **WHEN** an edit object is built with price `"9200.00"`, whether from code,
  from a JSON payload or from form-encoded text
- **THEN** the price is `Decimal("9200.00")`
- **AND** a price given as a binary floating-point number, in Python or as a
  JSON number with a fractional part, is still rejected for field `price`

#### Scenario: Integer price

- **WHEN** an edit object is built with price `1500` (a Python or JSON
  integer)
- **THEN** the price is `Decimal("1500")`, an exact value

#### Scenario: Monetary text edge cases

- **WHEN** an edit object is built with price `" 9200.00 "` or `"1E+3"`
- **THEN** the price is `Decimal("9200.00")` or `Decimal("1E+3")` respectively
- **AND WHEN** it is built with price `""`, `"NaN"`, `"Infinity"`, `"1,5"`,
  `"1_000"`, `"+5"` or digits from another script such as `"١٢٣"`
- **THEN** building it fails with a validation error for field `price`

#### Scenario: Estimated time as integer text

- **WHEN** an edit object is built with estimated time `"25"` or `" 25 "`
- **THEN** the estimated time is `25`
- **AND WHEN** it is built with `"-5"`
- **THEN** it is `-5`, left for the business rules to reject

#### Scenario: Estimated time that is not an integer

- **WHEN** an edit object is built with estimated time `true`, `12.5`, `""`,
  `"25.0"`, `"2.5"` or digits from another script such as `"١٢"`
- **THEN** building it fails with a validation error for field
  `estimated_time_min`

#### Scenario: Estimated time cannot go back to unknown

- **GIVEN** an item with estimated time `25`
- **WHEN** an edit object is built with the estimated time present and null
- **THEN** building it fails with a validation error for field
  `estimated_time_min`
- **AND** the service is never called and the estimated time is still `25`

#### Scenario: Shape error as a request payload

- **WHEN** a request whose payload is the edit object, sent as JSON, carries a
  shape error
- **THEN** the response is `400` with code `invalid_input` and the field, and
  the body does not contain the rejected value

### Requirement: Edit business rules are enforced by the menu

Applying an edit SHALL raise an invalid-input error (`InvalidInputError`, `400`
by `API-3`) naming the offending field, and SHALL leave the item unchanged,
when: the price is negative, has more than two decimal places, or does not fit
in twelve digits with two decimals; or the estimated time is negative or
exceeds the integer range of the database. A price with more decimal places is never rounded. No value
breaking these rules SHALL reach the database or produce a database error. The
error message SHALL NOT contain the rejected value. Price `0` and estimated
time `0` are valid.

#### Scenario: Negative price

- **WHEN** an edit with price `-1.00` is applied
- **THEN** an invalid-input error is raised for field `price`

#### Scenario: Too many decimals

- **WHEN** an edit with price `1500.505` is applied
- **THEN** an invalid-input error is raised for field `price`
- **AND** the stored price is unchanged, not `1500.50` nor `1500.51`

#### Scenario: Trailing zeros are not extra decimals

- **WHEN** an edit with price `1500.500` is applied
- **THEN** the stored price is `1500.50`

#### Scenario: Price beyond the column range

- **WHEN** an edit with price `10000000000.00` is applied
- **THEN** an invalid-input error is raised for field `price`
- **AND** no database error occurs

#### Scenario: Negative or out-of-range estimated time

- **WHEN** an edit with estimated time `-5` or `2147483648` is applied
- **THEN** an invalid-input error is raised for field `estimated_time_min`
- **AND** no database error occurs

#### Scenario: Zero is valid

- **WHEN** an edit with price `0` and estimated time `0` is applied
- **THEN** the edit succeeds and both values are stored

#### Scenario: Rejected value is not echoed

- **WHEN** an edit is rejected for any of the reasons above
- **THEN** the error message and its exception chain do not contain the
  rejected value

### Requirement: Price changes do not alter confirmed orders

Editing the price of an item SHALL NOT change the unit price recorded in any
order line already persisted (`DAT-4`).

#### Scenario: Snapshot survives a price update

- **GIVEN** an order line for `Bondiola` with unit price snapshot `8500.00`
- **WHEN** the price of `Bondiola` is edited to `9200.00`
- **THEN** the item price is `9200.00`
- **AND** the order line still has unit price snapshot `8500.00`

### Requirement: Estimated time may be unknown on existing items

The stored schema allows an item without an estimated preparation time. Such an
item SHALL be returned with the estimated time absent, never as `0`, and an
edit SHALL NOT set it back to unknown (see "Edit shape is validated by the edit
object"). This tolerance is transitional: making the estimated time
mandatory in the database (`NOT NULL`) is a prerequisite of the orders change,
because the kitchen-ready estimate of `ORD-12` needs it for every item. This
change does not migrate.

#### Scenario: Item without estimated time

- **GIVEN** an item stored without an estimated time
- **WHEN** it is listed or looked up
- **THEN** its estimated time is absent, not `0`

