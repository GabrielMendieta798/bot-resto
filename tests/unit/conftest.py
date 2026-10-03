"""Fixtures de los tests unitarios: sin red (salvo loopback) y sin base de datos.

Ningún test unitario lee el `.env` del desarrollador ni modifica los YAML
reales: trabajan sobre copias en un directorio temporal.
"""

import functools
import io
import logging
import shutil
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI

from app.core import config as config_module
from app.core.config import CONFIG_DIR, Settings, get_config
from app.core.config import load_config as _load_config
from app.core.logging import configure_logging
from unit.fakes import FAKE_DATABASE_URL

SETTINGS_ENV_KEYS = tuple(name.upper() for name in Settings.model_fields)


@pytest.fixture(autouse=True)
def _fresh_config_cache() -> Iterator[None]:
    get_config.cache_clear()
    yield
    get_config.cache_clear()


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    """Copia de los tres YAML commiteados, para romperlos sin tocar los reales."""
    target = tmp_path / "config"
    target.mkdir()
    for name in ("restaurant.yaml", "messages.yaml", "http_errors.yaml"):
        shutil.copy(CONFIG_DIR / name, target / name)
    return target


@pytest.fixture
def config_env(monkeypatch: pytest.MonkeyPatch, config_dir: Path) -> Path:
    """Entorno mínimo válido apuntando a las copias de `config_dir`.

    También corta la lectura del `.env` real en todo camino que pase por
    `get_config()` (la app, el atributo `settings`): sin esto, una clave que el
    test borra del entorno vuelve desde el `.env` del desarrollador.
    """
    monkeypatch.setattr(
        config_module, "load_config", functools.partial(_load_config, env_file=None)
    )
    for key in SETTINGS_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", FAKE_DATABASE_URL)
    monkeypatch.setenv("RESTAURANT_CONFIG_PATH", str(config_dir / "restaurant.yaml"))
    monkeypatch.setenv("MESSAGES_CONFIG_PATH", str(config_dir / "messages.yaml"))
    monkeypatch.setenv("HTTP_ERRORS_CONFIG_PATH", str(config_dir / "http_errors.yaml"))
    return config_dir


@pytest.fixture
def restore_logging() -> Iterator[None]:
    """`create_app()` y `configure_logging()` tocan el root logger global."""
    root = logging.getLogger()
    saved_handlers, saved_level = list(root.handlers), root.level
    library_loggers = ("httpx", "httpcore", "uvicorn", "uvicorn.error")
    saved_levels = {name: logging.getLogger(name).level for name in library_loggers}
    yield
    root.handlers[:] = saved_handlers
    root.setLevel(saved_level)
    for name, level in saved_levels.items():
        logging.getLogger(name).setLevel(level)


@pytest.fixture
def make_app(config_env: Path, restore_logging: None) -> Callable[[], FastAPI]:
    """Construye la app real sobre el entorno aislado de `config_env`."""
    # Import diferido: `app.main` arma la app al importarse, así que el entorno
    # tiene que estar listo antes del primer import.
    from app.main import create_app

    def factory() -> FastAPI:
        get_config.cache_clear()
        return create_app()

    return factory


@pytest.fixture
def log_buffer(restore_logging: None) -> Callable[[], io.StringIO]:
    """Redirige el logging estructurado a un buffer. Llamar después de crear la app."""

    def capture() -> io.StringIO:
        buffer = io.StringIO()
        configure_logging("INFO", stream=buffer)
        return buffer

    return capture
