"""Fixtures de los tests unitarios: sin red (salvo loopback) y sin base de datos.

Ningún test unitario lee el `.env` del desarrollador ni modifica los YAML
reales: trabajan sobre copias en un directorio temporal.
"""

import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.core.config import CONFIG_DIR, Settings, get_config

SETTINGS_ENV_KEYS = tuple(name.upper() for name in Settings.model_fields)

# Valor con forma de secreto, para verificar que nunca aparece en errores.
FAKE_DATABASE_PASSWORD = "S3cretPassw0rd"  # noqa: S105 — ficticio a propósito
FAKE_DATABASE_URL = (
    f"postgresql+psycopg://bot_user:{FAKE_DATABASE_PASSWORD}"
    "@db.internal.example:5432/bot"
)


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
    """Entorno mínimo válido apuntando a las copias de `config_dir`."""
    for key in SETTINGS_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", FAKE_DATABASE_URL)
    monkeypatch.setenv("RESTAURANT_CONFIG_PATH", str(config_dir / "restaurant.yaml"))
    monkeypatch.setenv("MESSAGES_CONFIG_PATH", str(config_dir / "messages.yaml"))
    monkeypatch.setenv("HTTP_ERRORS_CONFIG_PATH", str(config_dir / "http_errors.yaml"))
    return config_dir
