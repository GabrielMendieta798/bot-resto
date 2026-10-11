"""Escenarios de la spec `customer-registry` contra el repositorio en memoria.

La concurrencia (dos mensajes simultáneos del mismo número) depende del índice
único de la base y se prueba en `tests/integration/`.
"""

import io
import logging
from collections.abc import Callable

import pytest

from app.core.exceptions import InvalidInputError
from app.domain.customers.service import CustomerService
from unit.domain_fakes import InMemoryCustomerRepository

PHONE = "5491155551234"


@pytest.fixture
def repo() -> InMemoryCustomerRepository:
    return InMemoryCustomerRepository()


@pytest.fixture
def service(repo: InMemoryCustomerRepository) -> CustomerService:
    return CustomerService(repo)


def _exception_texts(error: BaseException) -> str:
    """Mensaje, repr y toda la cadena de la excepción, como texto."""
    texts: list[str] = []
    current: BaseException | None = error
    while current is not None:
        texts += [str(current), repr(current), repr(current.args)]
        current = current.__cause__ or current.__context__
    return "\n".join(texts)


def _raw_log_text(caplog: pytest.LogCaptureFixture) -> str:
    # Records crudos, antes de cualquier enmascarado: mensaje, args y
    # excepciones adjuntas.
    parts = [caplog.text]
    for record in caplog.records:
        parts += [record.getMessage(), repr(record.args), repr(record.__dict__)]
    return "\n".join(parts)


# --- Obtener o crear -----------------------------------------------------------


def test_new_number_creates_the_customer(
    service: CustomerService, repo: InMemoryCustomerRepository
) -> None:
    customer = service.get_or_create_by_phone(PHONE)

    assert customer.phone == PHONE
    assert customer.id >= 1
    assert customer.created_at.tzinfo is not None
    assert repo.count(PHONE) == 1


def test_known_number_returns_the_same_customer(
    service: CustomerService, repo: InMemoryCustomerRepository
) -> None:
    first = service.get_or_create_by_phone(PHONE)

    again = service.get_or_create_by_phone(PHONE)

    assert again.id == first.id
    assert repo.count(PHONE) == 1


# --- Solo teléfonos canónicos ----------------------------------------------------


@pytest.mark.parametrize(
    "phone",
    [
        "+54 9 11 5555-1234",
        "+5491155551234",
        "54911abc1234",
        "",
        "1234567",
        "1234567890123456",
        "٥٤٩١١٥٥٥٥١٢٣٤",
        " 5491155551234",
        "5491155551234\n",
    ],
    ids=[
        "formatted",
        "plus-sign",
        "letters",
        "empty",
        "7-digits",
        "16-digits",
        "non-ascii-digits",
        "leading-space",
        "trailing-newline",
    ],
)
def test_non_canonical_phone_is_rejected_without_calling_the_repository(
    service: CustomerService, repo: InMemoryCustomerRepository, phone: str
) -> None:
    with pytest.raises(InvalidInputError) as caught:
        service.get_or_create_by_phone(phone)

    assert caught.value.field == "phone"
    assert repo.calls == []


@pytest.mark.parametrize("phone", ["12345678", "123456789012345"])
def test_boundary_lengths_are_accepted(service: CustomerService, phone: str) -> None:
    assert service.get_or_create_by_phone(phone).phone == phone


# --- El teléfono no aparece en errores ni logs -----------------------------------


def test_rejected_number_is_absent_from_error_and_logs(
    service: CustomerService,
    caplog: pytest.LogCaptureFixture,
    log_buffer: Callable[[], io.StringIO],
) -> None:
    structured = log_buffer()
    caplog.set_level(logging.DEBUG)

    with pytest.raises(InvalidInputError) as caught:
        service.get_or_create_by_phone("+54 9 11 5555-1234")

    error_text = _exception_texts(caught.value)
    logged = _raw_log_text(caplog) + structured.getvalue()
    for fragment in ("5555-1234", "5555", "+54 9 11"):
        assert fragment not in error_text
        assert fragment not in logged
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_valid_number_is_absent_from_logs(
    service: CustomerService,
    caplog: pytest.LogCaptureFixture,
    log_buffer: Callable[[], io.StringIO],
) -> None:
    structured = log_buffer()
    caplog.set_level(logging.DEBUG)

    service.get_or_create_by_phone(PHONE)

    assert PHONE not in _raw_log_text(caplog)
    assert PHONE not in structured.getvalue()
