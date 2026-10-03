"""Escenarios de la spec `runtime-configuration` (VAL-4, TXT-2, TXT-3, GEN-7)."""

import os
import traceback
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest
import yaml

from app.core import exceptions
from app.core.config import (
    CONFIG_DIR,
    PROJECT_ROOT,
    HttpErrorsConfig,
    Settings,
    load_config,
)
from app.core.exceptions import ConfigError, registered_text_keys


def _edit_yaml(path: Path, mutate: Callable[[dict[str, Any]], None]) -> None:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    mutate(data)
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")


def _replace_in_file(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def _config_error() -> ConfigError:
    with pytest.raises(ConfigError) as caught:
        load_config(env_file=None)
    return caught.value


def _full_output(error: ConfigError) -> str:
    """Lo que se imprimiría al reventar el arranque, con excepciones encadenadas."""
    return "".join(traceback.format_exception(error))


# --- Fuentes válidas ---------------------------------------------------------


def test_all_sources_valid_load(config_env: Path) -> None:
    config = load_config(env_file=None)

    assert config.settings.app_env == "test"
    assert config.restaurant.timezone == "America/Argentina/Buenos_Aires"


def test_committed_defaults_load(
    config_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in (
        "RESTAURANT_CONFIG_PATH",
        "MESSAGES_CONFIG_PATH",
        "HTTP_ERRORS_CONFIG_PATH",
    ):
        monkeypatch.delenv(key)

    config = load_config(env_file=None)

    assert config.settings.restaurant_config_path == CONFIG_DIR / "restaurant.yaml"
    assert config.restaurant.delivery.zones


# --- Claves faltantes y formas inválidas -------------------------------------


def test_missing_env_key_names_it_without_other_values(
    config_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DATABASE_URL")
    monkeypatch.setenv("HTTP_READ_TIMEOUT_SECONDS", "7.25")

    message = str(_config_error())

    assert "DATABASE_URL" in message
    assert "7.25" not in message
    assert str(config_env) not in message


def test_missing_yaml_key_names_file_and_path_without_values(
    config_env: Path,
) -> None:
    _edit_yaml(config_env / "restaurant.yaml", lambda d: d["cart"].clear())

    message = str(_config_error())

    assert "restaurant.yaml: cart.timeout_minutes" in message
    assert "Centro" not in message
    assert "Buenos_Aires" not in message


def test_wrong_shape_names_key_and_type_without_value(config_env: Path) -> None:
    _edit_yaml(
        config_env / "restaurant.yaml",
        lambda d: d["reservations"].update(max_party_size="doce"),
    )

    message = str(_config_error())

    assert "restaurant.yaml: reservations.max_party_size" in message
    assert "integer" in message
    assert "doce" not in message


def test_unquoted_time_is_rejected(config_env: Path) -> None:
    _replace_in_file(config_env / "restaurant.yaml", 'opens: "20:00"', "opens: 20:00")

    assert "opening_hours.tuesday.1.opens" in str(_config_error())


def test_secret_never_appears_in_error_or_chained_output(
    config_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret_url = os.environ["DATABASE_URL"]
    password = urlsplit(secret_url).password
    assert password
    monkeypatch.delenv("APP_ENV")

    error = _config_error()
    output = _full_output(error)

    assert "APP_ENV" in str(error)
    assert error.__cause__ is None
    assert error.__suppress_context__
    assert password not in output
    assert secret_url not in output


def test_unknown_yaml_key_is_rejected(config_env: Path) -> None:
    _edit_yaml(config_env / "restaurant.yaml", lambda d: d.update(tables=4))

    assert "restaurant.yaml: tables" in str(_config_error())


# --- YAML malformado o ausente -----------------------------------------------


def test_yaml_syntax_error_reports_position_without_snippet(
    config_env: Path,
) -> None:
    (config_env / "messages.yaml").write_text(
        "greeting: [unclosed_list\nsecret_line: hola\n", encoding="utf-8"
    )

    output = _full_output(_config_error())

    assert "messages.yaml: invalid YAML syntax line" in output
    assert "column" in output
    assert "unclosed_list" not in output
    assert "secret_line" not in output


def test_absent_restaurant_file_is_rejected(config_env: Path) -> None:
    (config_env / "restaurant.yaml").unlink()

    assert "restaurant.yaml: file not found" in str(_config_error())


def test_absent_messages_file_is_rejected(config_env: Path) -> None:
    (config_env / "messages.yaml").unlink()

    assert "messages.yaml: file not found" in str(_config_error())


def test_non_mapping_top_level_is_rejected(config_env: Path) -> None:
    (config_env / "http_errors.yaml").write_text("- a\n- b\n", encoding="utf-8")

    assert "http_errors.yaml: top level must be a mapping" in str(_config_error())


def test_comments_only_messages_file_is_accepted(config_env: Path) -> None:
    (config_env / "messages.yaml").write_text(
        "# solo comentarios\n# todavía sin copy\n", encoding="utf-8"
    )

    load_config(env_file=None)


def test_comments_only_restaurant_file_is_rejected(config_env: Path) -> None:
    (config_env / "restaurant.yaml").write_text("# vacío\n", encoding="utf-8")

    assert "restaurant.yaml: file is empty" in str(_config_error())


# --- Valores de negocio ------------------------------------------------------


def test_delivery_fee_is_an_exact_decimal(config_env: Path) -> None:
    _replace_in_file(config_env / "restaurant.yaml", "fee: 1500.00", "fee: 1500.10")

    fee = load_config(env_file=None).restaurant.delivery.zones[0].fee

    assert isinstance(fee, Decimal)
    assert fee == Decimal("1500.10")
    assert str(fee) == "1500.10"


def test_unknown_time_zone_is_rejected(config_env: Path) -> None:
    _edit_yaml(
        config_env / "restaurant.yaml", lambda d: d.update(timezone="Mars/Olympus")
    )

    message = str(_config_error())

    assert "restaurant.yaml: timezone" in message
    assert "Mars/Olympus" not in message


# --- Textos: separación y claves referenciadas -------------------------------


def test_missing_error_text_key_is_rejected(config_env: Path) -> None:
    _edit_yaml(config_env / "http_errors.yaml", lambda d: d.pop("conflict"))

    assert "http_errors.yaml: conflict" in str(_config_error())


def test_error_type_with_unknown_text_key_is_rejected(
    config_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Registro aislado: la clase de prueba no queda registrada para el resto
    # de la suite.
    monkeypatch.setattr(exceptions, "_TEXT_KEYS", set(exceptions._TEXT_KEYS))

    class _PaymentRequiredError(exceptions.AppError):
        message_key = "payment_required"

    assert "http_errors.yaml: payment_required" in str(_config_error())


def test_committed_error_texts_cover_every_error_type() -> None:
    assert registered_text_keys() <= set(HttpErrorsConfig.model_fields)


def test_error_section_in_messages_file_is_rejected(config_env: Path) -> None:
    _edit_yaml(
        config_env / "messages.yaml",
        lambda d: d.update(errors={"not_found": "No encontramos"}),
    )

    assert "messages.yaml: errors" in str(_config_error())


def test_committed_messages_file_holds_no_internal_text() -> None:
    text = (CONFIG_DIR / "messages.yaml").read_text(encoding="utf-8")
    error_texts = yaml.safe_load(
        (CONFIG_DIR / "http_errors.yaml").read_text(encoding="utf-8")
    )

    assert yaml.safe_load(text) is None
    for key, value in error_texts.items():
        assert f"{key}:" not in text
        assert value not in text


# --- Plantilla de entorno ----------------------------------------------------


def _env_example() -> dict[str, str]:
    entries = {}
    lines = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            key, _, value = stripped.partition("=")
            entries[key] = value
    return entries


def test_env_example_lists_exactly_the_settings_keys() -> None:
    assert set(_env_example()) == {name.upper() for name in Settings.model_fields}


def test_env_example_carries_no_real_values() -> None:
    entries = _env_example()

    assert entries["DATABASE_URL"] == ""
    for value in entries.values():
        assert "@" not in value
        assert "://" not in value


def test_settings_representation_hides_the_connection_string(
    config_env: Path,
) -> None:
    config = load_config(env_file=None)
    secret_url = os.environ["DATABASE_URL"]

    for text in (repr(config.settings), str(config.settings), repr(config)):
        assert secret_url not in text
        assert "S3cretPassw0rd" not in text


def test_yaml_python_tag_constructs_nothing(
    config_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    monkeypatch.setattr("os.system", lambda command: calls.append(command) or 0)
    (config_env / "restaurant.yaml").write_text(
        "timezone: !!python/object/apply:os.system ['echo pwned']\n",
        encoding="utf-8",
    )

    message = str(_config_error())

    assert calls == []
    assert "restaurant.yaml: invalid YAML syntax" in message
    assert "pwned" not in message
