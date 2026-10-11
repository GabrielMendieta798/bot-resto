"""Servicio de customers: identificar al cliente por su número de WhatsApp.

El teléfono llega en forma canónica (solo dígitos, de 8 a 15: E.164 sin el
`+`). Normalizar lo que manda Meta es del adapter de WhatsApp; acá se rechaza lo
que no es canónico. Que un número nunca produzca dos customers lo garantiza el
índice único de `customers.phone` dentro del repositorio, no un chequeo previo
(design D4). No ve la base y no commitea (GEN-1, DAT-2, CONV-10).
"""

import re
from typing import Protocol

from app.core.exceptions import InvalidInputError
from app.domain.customers.schemas import CustomerRead

# `[0-9]` y no `\d`: `\d` acepta dígitos de otras escrituras (árabe, devanagari).
_CANONICAL_PHONE = re.compile(r"[0-9]{8,15}")


class CustomerRepository(Protocol):
    """Lo que el servicio necesita de la persistencia de customers.

    `get_or_create` devuelve el mismo customer para el mismo teléfono aunque dos
    transacciones lo pidan a la vez. No commitea.
    """

    def get_or_create(self, phone: str) -> CustomerRead: ...


class CustomerService:
    def __init__(self, repository: CustomerRepository) -> None:
        self._repository = repository

    def get_or_create_by_phone(self, phone: str) -> CustomerRead:
        """El customer de ese teléfono, creado si no existía.

        No loguea el teléfono, y el error de un teléfono inválido no lo lleva
        (SEC-3): el mensaje es fijo y nada queda encadenado.
        """
        if not _CANONICAL_PHONE.fullmatch(phone):
            raise InvalidInputError("phone is not canonical", field="phone")
        return self._repository.get_or_create(phone)
