"""Escenarios de SQL echo de la spec `runtime-configuration` (DAT-10)."""

from pathlib import Path

import pytest

from app.core import database
from app.core.config import load_config
from app.core.database import build_engine
from app.core.exceptions import ConfigError


def test_echo_is_off_by_default(config_env: Path) -> None:
    engine = build_engine(load_config(env_file=None).settings)

    assert engine.echo is False


def test_echo_is_enabled_only_by_configuration(
    config_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_ECHO", "true")

    engine = build_engine(load_config(env_file=None).settings)

    assert engine.echo is True


def test_echo_in_production_prevents_startup(
    config_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_ECHO", "true")

    with pytest.raises(ConfigError) as caught:
        load_config(env_file=None)

    assert "DATABASE_ECHO" in str(caught.value)


def test_importing_the_module_creates_no_engine() -> None:
    assert not hasattr(database, "engine")
    assert not hasattr(database, "SessionLocal")


def test_engine_hides_statement_parameters_in_errors(config_env: Path) -> None:
    engine = build_engine(load_config(env_file=None).settings)

    assert engine.hide_parameters is True
