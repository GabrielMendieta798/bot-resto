"""Fixtures de los tests de integración: corren contra una PostgreSQL real.

Usan la configuración real del entorno (`.env` + variables). Si la base no
responde, la sesión entera corta con un mensaje claro: nunca se saltean tests
en silencio (VER-6).
"""

import logging
from collections.abc import Iterator

import psycopg
import pytest
from sqlalchemy import make_url, text
from sqlalchemy.engine import URL
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


@pytest.fixture
def migration_database_url(monkeypatch: pytest.MonkeyPatch) -> Iterator[URL]:
    """Run destructive migration tests only against a dedicated test database."""
    configured_url = make_url(load_config().settings.database_url)
    if configured_url.get_backend_name() != "postgresql":
        pytest.fail(
            "Migration integration tests require PostgreSQL in DATABASE_URL.",
            pytrace=False,
        )

    application_database = configured_url.database
    if application_database is None or application_database.endswith("_test"):
        pytest.fail(
            "DATABASE_URL must point to the application database so the "
            "dedicated migration database can be derived safely.",
            pytrace=False,
        )

    test_database = f"{application_database}_test"
    test_url = configured_url.set(database=test_database)
    test_database_url = test_url.render_as_string(hide_password=False)

    _reset_migration_database(test_database_url, test_database)
    monkeypatch.setenv("DATABASE_URL", test_database_url)
    get_config.cache_clear()

    try:
        yield test_url
    finally:
        get_config.cache_clear()
        _reset_migration_database(test_database_url, test_database)


def _reset_migration_database(database_url: str, expected_database: str) -> None:
    """Remove every object only after confirming the dedicated test database."""
    psycopg_url = (
        make_url(database_url)
        .set(drivername="postgresql")
        .render_as_string(hide_password=False)
    )
    try:
        with psycopg.connect(psycopg_url, autocommit=True) as connection:
            row = connection.execute("SELECT current_database()").fetchone()
            actual_database = row[0] if row is not None else None

            if actual_database != expected_database or not expected_database.endswith(
                "_test"
            ):
                pytest.fail(
                    "Refusing to reset a database that is not the dedicated "
                    "migration test database.",
                    pytrace=False,
                )

            connection.execute("DROP SCHEMA public CASCADE")
            connection.execute("CREATE SCHEMA public AUTHORIZATION CURRENT_USER")
    except psycopg.Error:
        pytest.fail(
            "Could not reset the dedicated migration test database. Create it "
            "first and make the DATABASE_URL role its owner.",
            pytrace=False,
        )
