"""Schemas del módulo de menú.

Validan **forma**: tipo, largo, nulidad y campos desconocidos. Los límites de
valor y de negocio (signo y escala del precio, rangos) son reglas y viven en el
servicio (VAL-3). Este módulo no importa nada de persistencia (GEN-1).
"""

import re
from datetime import UTC, datetime
from decimal import Decimal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

NAME_MAX_LENGTH = 150  # menu_items.name es String(150)

# Texto que un formulario o un JSON pueden traer para un número exacto. ASCII
# explícito: el parser de Pydantic aceptaría "١٢٣" o "1_000". El signo se
# admite para que un negativo llegue a la regla de negocio, no a la forma.
_DECIMAL_TEXT = re.compile(r"-?[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?")
_INTEGER_TEXT = re.compile(r"-?[0-9]+")


class MenuItemRead(BaseModel):
    """Un item del menú tal como lo devuelve el repositorio.

    Inmutable: modificarlo no puede confundirse con un cambio persistido.
    Estricto: un precio `float` se rechaza en lugar de convertirse (DAT-8).
    """

    model_config = ConfigDict(frozen=True, strict=True, from_attributes=True)

    id: int
    category: str
    name: str
    description: str | None
    price: Decimal
    estimated_time_min: int | None
    available: bool
    created_at: AwareDatetime

    @field_validator("price")
    @classmethod
    def _price_has_two_decimal_places(cls, value: Decimal) -> Decimal:
        if value.as_tuple().exponent != -2:
            raise ValueError("price must have exactly two decimal places")
        return value

    @field_validator("created_at")
    @classmethod
    def _created_at_in_utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class MenuItemUpdate(BaseModel):
    """Edición parcial de un item: solo los campos presentes se modifican.

    Un campo que no vino queda fuera de `model_fields_set`; uno que vino vacío
    queda adentro con su valor. `name`, `price` y `estimated_time_min` son
    opcionales pero no nulos: un `null` explícito es error de forma, así el
    tiempo estimado nunca vuelve a desconocido.
    """

    model_config = ConfigDict(strict=True, extra="forbid", str_strip_whitespace=True)

    # `X | None = None` solo para que "no vino" tenga un default: los
    # validadores no corren sobre el default, así que el `None` que llega es
    # siempre uno explícito, y `_present_fields_are_not_null` lo rechaza.
    name: str | None = Field(default=None, min_length=1, max_length=NAME_MAX_LENGTH)
    description: str | None = None
    price: Decimal | None = Field(default=None, allow_inf_nan=False)
    estimated_time_min: int | None = None

    @field_validator("price", mode="before")
    @classmethod
    def _price_is_exact(cls, value: object) -> object:
        # FastAPI valida el payload después de `json.loads` y los formularios
        # mandan texto: sin esto, ningún request podría traer un precio.
        if isinstance(value, bool | float):
            # Un número binario nunca se convierte en dinero (DAT-8).
            raise ValueError("price must be an exact decimal")
        if isinstance(value, int):
            return Decimal(value)
        if isinstance(value, str):
            text = value.strip()
            if not _DECIMAL_TEXT.fullmatch(text):
                raise ValueError("price must be decimal text")
            return Decimal(text)
        return value

    @field_validator("estimated_time_min", mode="before")
    @classmethod
    def _estimated_time_is_an_integer(cls, value: object) -> object:
        # `bool` y `float` no llegan acá convertidos: los rechaza `strict`.
        if isinstance(value, str):
            text = value.strip()
            if not _INTEGER_TEXT.fullmatch(text):
                raise ValueError("estimated time must be integer text")
            return int(text)
        return value

    @field_validator("name", "price", "estimated_time_min")
    @classmethod
    def _present_fields_are_not_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("field must not be null")
        return value

    @field_validator("description")
    @classmethod
    def _blank_description_is_none(cls, value: str | None) -> str | None:
        return value or None
