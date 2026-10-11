"""La transacción es de quien llama (spec `domain-data-boundary`, CONV-10).

Los repositorios no commitean ni revierten: si quien llama hace rollback, nada
de lo que hicieron persiste, y antes del commit nada se ve desde otra conexión.
"""

from collections.abc import Callable, Iterator
from decimal import Decimal

import pytest
from sqlalchemy import Connection, Engine, delete, func, insert, select
from sqlalchemy.orm import Session

from app.core.database import build_session_factory
from app.db.repositories.customers import SqlCustomerRepository
from app.db.repositories.menu import SqlMenuRepository
from app.domain.customers.service import CustomerService
from app.domain.menu.schemas import MenuItemUpdate
from app.domain.menu.service import MenuService
from app.models.customer import Customer
from app.models.menu_item import MenuItem

MakeItem = Callable[..., int]


def _price(session_or_connection: Session | Connection, item_id: int) -> Decimal:
    return session_or_connection.execute(
        select(MenuItem.price).where(MenuItem.id == item_id)
    ).scalar_one()


def _available(session: Session, item_id: int) -> bool:
    return session.execute(
        select(MenuItem.available).where(MenuItem.id == item_id)
    ).scalar_one()


# --- Rollback de quien llama ----------------------------------------------------


def test_price_edit_rolled_back_by_the_caller_keeps_the_previous_price(
    db_session: Session, make_item: MakeItem
) -> None:
    bondiola = make_item("Bondiola", price="8500.00")
    # Quien llama confirma el alta; la edición corre en una transacción nueva.
    db_session.commit()

    MenuService(SqlMenuRepository(db_session)).update_item(
        bondiola, MenuItemUpdate(price=Decimal("9200.00"))
    )
    assert _price(db_session, bondiola) == Decimal("9200.00")
    db_session.rollback()

    assert _price(db_session, bondiola) == Decimal("8500.00")


def test_availability_change_rolled_back_by_the_caller_is_undone(
    db_session: Session, make_item: MakeItem
) -> None:
    bondiola = make_item("Bondiola")
    db_session.commit()

    MenuService(SqlMenuRepository(db_session)).set_available(bondiola, False)
    assert _available(db_session, bondiola) is False
    db_session.rollback()

    assert _available(db_session, bondiola) is True


# --- Nada se ve antes del commit -------------------------------------------------


@pytest.fixture
def committed_item(db_engine: Engine, category: str) -> Iterator[int]:
    """Item commiteado de verdad, para que otra conexión pueda verlo.

    El teardown lo borra: es limpieza del test, no una operación del dominio
    (DAT-5 rige para la aplicación).
    """
    with db_engine.begin() as connection:
        item_id = connection.execute(
            insert(MenuItem.__table__)
            .values(
                category=category,
                name="Bondiola",
                price=Decimal("8500.00"),
                estimated_time_min=25,
                available=True,
            )
            .returning(MenuItem.__table__.c.id)
        ).scalar_one()
    yield int(item_id)
    with db_engine.begin() as connection:
        connection.execute(delete(MenuItem).where(MenuItem.id == item_id))


def test_customer_and_item_edit_are_invisible_before_the_caller_commits(
    db_engine: Engine, committed_item: int, phone: str
) -> None:
    with build_session_factory(db_engine)() as session:
        CustomerService(SqlCustomerRepository(session)).get_or_create_by_phone(phone)
        MenuService(SqlMenuRepository(session)).update_item(
            committed_item, MenuItemUpdate(price=Decimal("9200.00"))
        )

        with db_engine.connect() as other:
            customers = other.execute(
                select(func.count())
                .select_from(Customer)
                .where(Customer.phone == phone)
            ).scalar_one()
            price = other.execute(
                select(MenuItem.price).where(MenuItem.id == committed_item)
            ).scalar_one()

        session.rollback()

    assert customers == 0
    assert price == Decimal("8500.00")
    # Y después del rollback de quien llama, tampoco quedó nada.
    with db_engine.connect() as connection:
        assert (
            connection.execute(
                select(func.count())
                .select_from(Customer)
                .where(Customer.phone == phone)
            ).scalar_one()
            == 0
        )
        assert _price(connection, committed_item) == Decimal("8500.00")
