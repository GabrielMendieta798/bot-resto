"""Repositorio de customers contra PostgreSQL real (VER-3).

Spec `customer-registry` (obtener o crear, sin chequeo previo) y spec
`domain-data-boundary` (la transacción es de quien llama; datos planos; fechas
con zona). La concurrencia está en `test_customer_concurrency.py`.
"""

from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import Engine, event, func, select, text
from sqlalchemy.orm import Session

from app.core.database import Base
from app.db.repositories.customers import SqlCustomerRepository
from app.domain.customers.schemas import CustomerRead
from app.models.customer import Customer


def _count(session_or_connection: Any, phone: str) -> int:
    return session_or_connection.execute(
        select(func.count()).select_from(Customer).where(Customer.phone == phone)
    ).scalar_one()


@pytest.fixture
def repo(db_session: Session) -> SqlCustomerRepository:
    return SqlCustomerRepository(db_session)


@pytest.fixture
def statements(db_engine: Engine) -> Iterator[list[str]]:
    """SQL que llega al driver mientras dura el test."""
    captured: list[str] = []

    def capture(*args: Any) -> None:
        captured.append(args[2])

    event.listen(db_engine, "before_cursor_execute", capture)
    yield captured
    event.remove(db_engine, "before_cursor_execute", capture)


def test_new_number_creates_and_known_number_returns_the_same_customer(
    repo: SqlCustomerRepository, db_session: Session, phone: str
) -> None:
    created = repo.get_or_create(phone)
    again = repo.get_or_create(phone)

    assert created.phone == phone
    assert again.id == created.id
    assert again.created_at == created.created_at
    assert _count(db_session, phone) == 1


def test_first_statement_on_customers_is_the_insert(
    repo: SqlCustomerRepository, phone: str, statements: list[str]
) -> None:
    repo.get_or_create(phone)
    repo.get_or_create(phone)

    on_customers = [sql.lstrip().upper() for sql in statements if "customers" in sql]
    assert on_customers[0].startswith("INSERT INTO CUSTOMERS")
    # La segunda llamada también arranca por el INSERT: nunca un SELECT previo.
    assert on_customers[1].startswith("INSERT INTO CUSTOMERS")
    assert on_customers[2].startswith("SELECT")


def test_creation_rolled_back_by_the_caller_leaves_no_row(
    repo: SqlCustomerRepository, db_session: Session, phone: str
) -> None:
    repo.get_or_create(phone)
    assert _count(db_session, phone) == 1

    db_session.rollback()

    assert _count(db_session, phone) == 0


def test_creation_is_invisible_from_another_connection_before_commit(
    repo: SqlCustomerRepository, db_engine: Engine, phone: str
) -> None:
    repo.get_or_create(phone)

    with db_engine.connect() as other:
        assert _count(other, phone) == 0


def test_created_at_is_aware_and_utc_whatever_the_session_time_zone(
    repo: SqlCustomerRepository, db_session: Session, phone: str
) -> None:
    db_session.execute(text("SET TIME ZONE 'America/Argentina/Buenos_Aires'"))

    created = repo.get_or_create(phone)
    found = repo.get_or_create(phone)

    for customer in (created, found):
        assert customer.created_at.tzinfo is not None
        assert customer.created_at.utcoffset() == timedelta(0)


def test_returned_value_is_plain_data_not_an_orm_instance(
    repo: SqlCustomerRepository, phone: str
) -> None:
    customer = repo.get_or_create(phone)

    assert type(customer) is CustomerRead
    assert not isinstance(customer, Base)
