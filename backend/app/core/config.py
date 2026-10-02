"""Carga y validación de la configuración completa (VAL-4).

Cuatro fuentes, cuatro modelos tipados:

- entorno / `.env`             → `Settings` (secretos y parámetros técnicos)
- `config/restaurant.yaml`     → `RestaurantConfig` (valores de negocio, GEN-7)
- `config/messages.yaml`       → `MessagesConfig` (copy de cara al cliente, TXT-2)
- `config/http_errors.yaml`    → `HttpErrorsConfig` (textos de error HTTP, API-2)

`load_config()` es la única puerta de entrada. Si algo falta o tiene la forma
equivocada levanta `ConfigError`, cuyo mensaje nombra fuente y clave pero nunca
un valor: los errores de Pydantic y de PyYAML se traducen y la cadena de
excepciones se corta (`from None`), porque ambos incluyen el input en su texto.

Importar este módulo no lee nada. `settings` sigue disponible como atributo del
módulo para `backend/alembic/env.py`, pero se resuelve recién al accederlo.
"""

import functools
from dataclasses import dataclass
from datetime import time
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveFloat,
    PositiveInt,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.exceptions import ConfigError, registered_text_keys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = PROJECT_ROOT / "config"
ENV_FILE = PROJECT_ROOT / ".env"

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


# --- Entorno -----------------------------------------------------------------


class AppEnv(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        # `CLAVE=` vacío cuenta como no definida: aplica el default o, si es
        # obligatoria, falla como faltante.
        env_ignore_empty=True,
        extra="ignore",
        hide_input_in_errors=True,
    )

    # Sin default a propósito: un deploy que se olvida de setearlo no puede
    # caer en silencio en `development`, o el guard de DAT-10 no serviría.
    app_env: AppEnv

    # `str` y no `SecretStr` porque backend/alembic/env.py hace
    # `str(settings.database_url)`. `repr=False` lo saca del repr del modelo.
    database_url: str = Field(min_length=1, repr=False)

    # DAT-10: el SQL crudo expone teléfonos y direcciones.
    database_echo: bool = False
    health_db_timeout_seconds: PositiveFloat = 2

    log_level: LogLevel = "INFO"

    http_connect_timeout_seconds: PositiveFloat = 5
    http_read_timeout_seconds: PositiveFloat = 10
    http_write_timeout_seconds: PositiveFloat = 10
    http_pool_timeout_seconds: PositiveFloat = 5

    restaurant_config_path: Path = CONFIG_DIR / "restaurant.yaml"
    messages_config_path: Path = CONFIG_DIR / "messages.yaml"
    http_errors_config_path: Path = CONFIG_DIR / "http_errors.yaml"

    @field_validator("log_level", mode="before")
    @classmethod
    def _uppercase_log_level(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def _forbid_echo_in_production(self) -> Self:
        if self.database_echo and self.app_env is AppEnv.PRODUCTION:
            raise ValueError(
                "DATABASE_ECHO must be false when APP_ENV is production (DAT-10)"
            )
        return self


# --- YAML --------------------------------------------------------------------


class _ConfigModel(BaseModel):
    # extra="forbid": un typo en una clave es un error, no una clave ignorada.
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        str_strip_whitespace=True,
    )


class TimeSlot(_ConfigModel):
    opens: time
    closes: time

    @field_validator("opens", "closes", mode="before")
    @classmethod
    def _require_quoted_time(cls, value: object) -> object:
        # Sin comillas, YAML 1.1 lee `12:00` como el entero 720, y Pydantic lo
        # aceptaría como segundos desde medianoche: 00:12. Se exige texto.
        if not isinstance(value, str):
            raise ValueError('must be a quoted "HH:MM" string')
        return value

    @model_validator(mode="after")
    def _opens_before_closes(self) -> Self:
        if self.opens >= self.closes:
            raise ValueError("opens must be earlier than closes")
        return self


class OpeningHours(_ConfigModel):
    monday: list[TimeSlot]
    tuesday: list[TimeSlot]
    wednesday: list[TimeSlot]
    thursday: list[TimeSlot]
    friday: list[TimeSlot]
    saturday: list[TimeSlot]
    sunday: list[TimeSlot]


class DeliveryZone(_ConfigModel):
    name: str = Field(min_length=1)
    fee: Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]


class DeliveryConfig(_ConfigModel):
    zones: list[DeliveryZone] = Field(min_length=1)


class CartConfig(_ConfigModel):
    timeout_minutes: PositiveInt


class ConversationConfig(_ConfigModel):
    inactivity_timeout_minutes: PositiveInt
    max_retries: PositiveInt


class ReservationsConfig(_ConfigModel):
    max_days_ahead: PositiveInt
    max_party_size: PositiveInt
    escalation_minutes: PositiveInt


class RestaurantConfig(_ConfigModel):
    timezone: str
    opening_hours: OpeningHours
    delivery: DeliveryConfig
    cart: CartConfig
    conversation: ConversationConfig
    reservations: ReservationsConfig

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("unknown time zone") from None
        return value


class MessagesConfig(_ConfigModel):
    """Copy de cara al cliente. Vacío hasta los changes de conversación."""


NonEmptyText = Annotated[str, Field(min_length=1)]


class HttpErrorsConfig(_ConfigModel):
    internal_error: NonEmptyText
    invalid_input: NonEmptyText
    not_authenticated: NonEmptyText
    permission_denied: NonEmptyText
    not_found: NonEmptyText
    conflict: NonEmptyText
    invalid_state_transition: NonEmptyText
    method_not_allowed: NonEmptyText

    def text_for(self, key: str) -> str:
        texts: dict[str, str] = self.model_dump()
        return texts[key]


@dataclass(frozen=True, slots=True)
class AppConfig:
    settings: Settings
    restaurant: RestaurantConfig
    messages: MessagesConfig
    http_errors: HttpErrorsConfig


# --- Lectura de YAML ---------------------------------------------------------


class _ConfigLoader(yaml.SafeLoader):
    """SafeLoader que lee los números con decimales como `Decimal` (DAT-8)."""


def _construct_decimal(loader: yaml.SafeLoader, node: yaml.Node) -> Decimal:
    if not isinstance(node, yaml.ScalarNode):
        raise yaml.constructor.ConstructorError(
            None, None, "expected a scalar number", node.start_mark
        )
    raw = str(loader.construct_scalar(node)).replace("_", "")
    try:
        number = Decimal(raw)
    except InvalidOperation:
        number = Decimal("NaN")
    if not number.is_finite():
        raise yaml.constructor.ConstructorError(
            None, None, "invalid decimal number", node.start_mark
        )
    return number


_ConfigLoader.add_constructor("tag:yaml.org,2002:float", _construct_decimal)


def _read_yaml(path: Path, *, allow_empty: bool) -> dict[str, object]:
    name = path.name
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ConfigError(f"{name}: file not found") from None
    except OSError:
        raise ConfigError(f"{name}: file could not be read") from None

    try:
        # _ConfigLoader hereda de SafeLoader: no construye objetos arbitrarios.
        data = yaml.load(text, Loader=_ConfigLoader)  # noqa: S506
    except yaml.MarkedYAMLError as exc:
        # Nunca `str(exc)`: PyYAML incluye un snippet del contenido del archivo.
        mark = exc.problem_mark
        where = f"line {mark.line + 1}, column {mark.column + 1}" if mark else ""
        raise ConfigError(f"{name}: invalid YAML syntax {where}".rstrip()) from None
    except yaml.YAMLError:
        raise ConfigError(f"{name}: invalid YAML syntax") from None

    if data is None:
        if allow_empty:
            return {}
        raise ConfigError(f"{name}: file is empty")
    if not isinstance(data, dict):
        raise ConfigError(f"{name}: top level must be a mapping")
    return data


def _describe(source: str, exc: ValidationError, *, env_keys: bool) -> list[str]:
    problems = []
    for error in exc.errors(include_url=False, include_input=False):
        location = ".".join(str(part) for part in error["loc"])
        if env_keys:
            location = location.upper()
        where = f"{source}: {location}" if location else source
        problems.append(f"{where}: {error['msg']}")
    return problems


def _fail(problems: list[str]) -> ConfigError:
    detail = "\n".join(f"  - {problem}" for problem in problems)
    return ConfigError(f"Invalid configuration:\n{detail}")


# --- Punto de entrada --------------------------------------------------------


def load_config(env_file: Path | None = ENV_FILE) -> AppConfig:
    """Lee y valida toda la configuración. Levanta `ConfigError` si algo falla."""
    try:
        settings = Settings(_env_file=env_file)
    except ValidationError as exc:
        raise _fail(_describe("environment", exc, env_keys=True)) from None

    problems: list[str] = []
    restaurant = _load_model(
        RestaurantConfig, settings.restaurant_config_path, problems, allow_empty=False
    )
    messages = _load_model(
        MessagesConfig, settings.messages_config_path, problems, allow_empty=True
    )
    http_errors = _load_model(
        HttpErrorsConfig, settings.http_errors_config_path, problems, allow_empty=False
    )

    if http_errors is not None:
        defined = set(http_errors.model_dump())
        for key in sorted(registered_text_keys() - defined):
            problems.append(
                f"{settings.http_errors_config_path.name}: {key}: "
                "text key referenced by code is missing"
            )

    if problems or restaurant is None or messages is None or http_errors is None:
        raise _fail(problems)

    return AppConfig(
        settings=settings,
        restaurant=restaurant,
        messages=messages,
        http_errors=http_errors,
    )


def _load_model[M: _ConfigModel](
    model: type[M], path: Path, problems: list[str], *, allow_empty: bool
) -> M | None:
    try:
        data = _read_yaml(path, allow_empty=allow_empty)
    except ConfigError as exc:
        problems.append(str(exc))
        return None
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        problems.extend(_describe(path.name, exc, env_keys=False))
        return None


@functools.cache
def get_config() -> AppConfig:
    """Configuración validada, leída una sola vez por proceso."""
    return load_config()


def __getattr__(name: str) -> Settings:
    # Compatibilidad con `from app.core.config import settings` en
    # backend/alembic/env.py, sin leer nada al importar el módulo.
    if name == "settings":
        return get_config().settings
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
