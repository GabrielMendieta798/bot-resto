"""Jerarquía de errores de la aplicación.

No importa FastAPI ni Starlette (GEN-1): el dominio levanta estas excepciones sin
saber que existe HTTP. La traducción a códigos de estado vive en la capa API.

Cada clase declara un `code` legible por máquina y un `message_key`: la clave
del texto de la respuesta en `config/http_errors.yaml`. Toda clave declarada
queda registrada al definirse la clase, para que el arranque verifique que
existe en el archivo (TXT-3) y no falle recién frente a un request.
"""

from typing import ClassVar

_TEXT_KEYS: set[str] = set()


def registered_text_keys() -> frozenset[str]:
    """Claves de `http_errors.yaml` referenciadas por las clases de error."""
    return frozenset(_TEXT_KEYS)


class AppError(Exception):
    """Base de todos los errores propios. Sin mapeo explícito, es un 500."""

    code: ClassVar[str] = "internal_error"
    message_key: ClassVar[str] = "internal_error"

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        _TEXT_KEYS.add(cls.message_key)

    def __init__(self, detail: str = "", *, field: str | None = None) -> None:
        # `detail` es para el log y para el desarrollador. Nunca sale en la
        # respuesta HTTP: el texto de cara afuera sale de `message_key`.
        super().__init__(detail)
        self.field = field


_TEXT_KEYS.add(AppError.message_key)


class InvalidInputError(AppError):
    code = "invalid_input"
    message_key = "invalid_input"


class NotAuthenticatedError(AppError):
    code = "not_authenticated"
    message_key = "not_authenticated"


class PermissionDeniedError(AppError):
    code = "permission_denied"
    message_key = "permission_denied"


class NotFoundError(AppError):
    code = "not_found"
    message_key = "not_found"


class ConflictError(AppError):
    code = "conflict"
    message_key = "conflict"


class InvalidStateTransitionError(ConflictError):
    """Transición rechazada por la máquina de estados (ORD-13, RES-4)."""

    code = "invalid_state_transition"
    message_key = "invalid_state_transition"


class ConfigError(AppError):
    """Configuración inválida. Rompe el arranque; nunca llega a HTTP."""


class OutboundHttpError(AppError):
    """Falla de una llamada HTTP saliente."""


class OutboundTimeoutError(OutboundHttpError):
    """La llamada saliente superó su timeout."""
