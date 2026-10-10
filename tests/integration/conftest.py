"""Fixtures de los tests de integración: corren contra una PostgreSQL real.

Usan la configuración real del entorno (`.env` + variables). Si la base no
responde, la sesión entera corta con un mensaje claro: nunca se saltean tests
en silencio (VER-6).
"""

import logging
import secrets
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_config, load_config
from app.core.database import build_engine


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
