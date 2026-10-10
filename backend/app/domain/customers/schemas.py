"""Schemas del módulo de customers.

Validan forma de salida. El teléfono canónico de entrada lo valida el servicio:
no pasa por Pydantic, así ningún `ValidationError` puede arrastrar el número
(SEC-3). Este módulo no importa nada de persistencia (GEN-1).
"""

from datetime import UTC, datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator


class CustomerRead(BaseModel):
    """Un customer tal como lo devuelve el repositorio.

    El teléfono no aparece en `str` ni `repr`: un log o un print del objeto no
    filtra el número completo (SEC-3).
    """

    model_config = ConfigDict(frozen=True, strict=True, from_attributes=True)

    id: int
    phone: str = Field(repr=False)
    name: str | None
    created_at: AwareDatetime

    @field_validator("created_at")
    @classmethod
    def _created_at_in_utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)
