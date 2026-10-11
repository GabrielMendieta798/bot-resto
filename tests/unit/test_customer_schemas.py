"""Forma de salida de un customer.

Spec `customer-registry`, scenario "Representation of a customer", y spec
`domain-data-boundary`, requirement "Money is Decimal and time is zone-aware".
"""

from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from app.domain.customers.schemas import CustomerRead

PHONE = "5491155551234"
BUENOS_AIRES = timezone(timedelta(hours=-3))


def _customer(**overrides: Any) -> CustomerRead:
    fields: dict[str, Any] = {
        "id": 7,
        "phone": PHONE,
        "name": None,
        "created_at": datetime(2026, 10, 10, 21, 0, tzinfo=BUENOS_AIRES),
    }
    return CustomerRead(**(fields | overrides))


@pytest.mark.parametrize("render", [str, repr, format])
def test_text_representation_hides_the_phone(render: Any) -> None:
    text = render(_customer())

    assert PHONE not in text
    assert "7" in text


def test_phone_is_still_readable_as_data() -> None:
    assert _customer().phone == PHONE


def test_naive_created_at_is_rejected() -> None:
    with pytest.raises(ValidationError):
        # Naive a propósito: es el caso que se rechaza.
        _customer(created_at=datetime(2026, 10, 10, 21, 0))


def test_created_at_is_normalized_to_utc() -> None:
    customer = _customer()

    assert customer.created_at.utcoffset() == timedelta(0)
    assert customer.created_at == datetime(2026, 10, 11, 0, 0, tzinfo=UTC)


def test_customer_is_frozen() -> None:
    customer = _customer()

    with pytest.raises(ValidationError):
        customer.phone = "5490000000000"  # type: ignore[misc]
    assert customer.phone == PHONE
