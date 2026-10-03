"""Fixtures de los tests de integración: corren contra una PostgreSQL real.

Usan la configuración real del entorno (`.env` + variables). Si la base no
responde, la sesión entera corta con un mensaje claro: nunca se saltean tests
en silencio (VER-6).
"""

import logging
from collections.abc import Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

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
