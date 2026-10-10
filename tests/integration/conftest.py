"""Fixtures de los tests de integración: corren contra una PostgreSQL real.

Usan la configuración real del entorno (`.env` + variables). Si la base no
responde, la sesión entera corta con un mensaje claro: nunca se saltean tests
en silencio (VER-6).
"""

import logging
import secrets
from collections.abc import Callable, Iterator
from decimal import Decimal

import pytest
from sqlalchemy import Engine, insert, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_config, load_config
from app.core.database import build_engine
from app.models.customer import Customer
from app.models.menu_item import MenuItem
from app.models.order import Order
from app.models.order_item import OrderItem


@pytest.fixture(scope="session", autouse=True)
def database_available() -> None:
    engine = build_engine(load_config().settings)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        pytest.exit(
            "PostgreSQL unreachable at DATABASE_URL: start the database before "
            "running the integration suite.",
            returncode=1,
        )
    finally:
        engine.dispose()


@pytest.fixture(autouse=True)
def _fresh_config_and_logging() -> Iterator[None]:
    root = logging.getLogger()
    saved_handlers, saved_level = list(root.handlers), root.level
    get_config.cache_clear()
    yield
    get_config.cache_clear()
    root.handlers[:] = saved_handlers
    root.setLevel(saved_level)


@pytest.fixture(scope="session")
def db_engine(database_available: None) -> Iterator[Engine]:
    engine = build_engine(load_config().settings)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Iterator[Session]:
    """Sesión dentro de una transacción externa que se revierte al final.

    Con `create_savepoint`, el `session.rollback()` que hace el test (en el
    papel de quien llama al repositorio) revierte solo hasta el savepoint: lo
    que hizo el código bajo prueba. El teardown revierte la transacción externa,
    así que nada queda en la base (design D8).
    """
    with db_engine.connect() as connection:
        outer = connection.begin()
        session = Session(
            bind=connection,
            join_transaction_mode="create_savepoint",
            autoflush=False,
        )
        try:
            yield session
        finally:
            session.close()
            outer.rollback()


@pytest.fixture
def phone() -> str:
    """Teléfono canónico que no choca con filas de desarrollo ni de otro test."""
    return "549" + "".join(secrets.choice("0123456789") for _ in range(10))


@pytest.fixture
def category() -> str:
    """Categoría única por test: la base de desarrollo puede tener su menú."""
    return f"test-{secrets.token_hex(6)}"


MakeItem = Callable[..., int]


@pytest.fixture
def make_item(db_session: Session, category: str) -> MakeItem:
    """Inserta un item de menú dentro de la transacción del test y devuelve su id.

    El alta no es parte del repositorio (non-goal): se hace con `insert()` de
    Core sobre la tabla, sin pasar por el dominio.
    """

    def make(
        name: str,
        *,
        price: str = "8500.00",
        available: bool = True,
        estimated_time_min: int | None = 25,
        description: str | None = None,
        in_category: str | None = None,
    ) -> int:
        statement = (
            insert(MenuItem.__table__)
            .values(
                category=in_category or category,
                name=name,
                description=description,
                price=Decimal(price),
                estimated_time_min=estimated_time_min,
                available=available,
            )
            .returning(MenuItem.__table__.c.id)
        )
        return int(db_session.execute(statement).scalar_one())

    return make


@pytest.fixture
def make_order_line(db_session: Session, phone: str) -> Callable[[int, str], int]:
    """Inserta un pedido de una línea con su `unit_price_snapshot` (DAT-4).

    Con `insert()` de Core sobre las tablas: `Order` y `OrderItem` son
    non-goal de este change y no se tocan.
    """

    def make(menu_item_id: int, unit_price: str) -> int:
        customer_id = db_session.execute(
            insert(Customer.__table__)
            .values(phone=phone)
            .returning(Customer.__table__.c.id)
        ).scalar_one()
        order_id = db_session.execute(
            insert(Order.__table__)
            .values(
                customer_id=customer_id,
                status="RECEIVED",
                delivery_type="PICKUP",
                total=Decimal(unit_price),
            )
            .returning(Order.__table__.c.id)
        ).scalar_one()
        return int(
            db_session.execute(
                insert(OrderItem.__table__)
                .values(
                    order_id=order_id,
                    menu_item_id=menu_item_id,
                    quantity=1,
                    unit_price_snapshot=Decimal(unit_price),
                )
                .returning(OrderItem.__table__.c.id)
            ).scalar_one()
        )

    return make
