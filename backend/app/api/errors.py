"""Traducción de errores a respuestas HTTP (API-2, API-3).

Todo error sale con el mismo cuerpo: `{"error": {"code", "message", "field"}}`.
El `message` sale siempre de `config/http_errors.yaml`; nunca del texto de la
excepción, que lo escribe un desarrollador y puede contener SQL o datos del
cliente. Ningún stacktrace sale hacia afuera: queda solo en el log.
"""

import logging
from collections.abc import Mapping

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import AppConfig
from app.core.exceptions import (
    AppError,
    ConflictError,
    InvalidInputError,
    NotAuthenticatedError,
    NotFoundError,
    PermissionDeniedError,
)

logger = logging.getLogger(__name__)

# Una subclase hereda el status de su ancestro mapeado más cercano (MRO).
# Lo que no está acá es un 500.
STATUS_BY_ERROR: dict[type[AppError], int] = {
    InvalidInputError: 400,
    NotAuthenticatedError: 401,
    PermissionDeniedError: 403,
    NotFoundError: 404,
    ConflictError: 409,
}

# Errores que levanta el framework (ruta inexistente, método no soportado).
_FRAMEWORK_CODES: dict[int, str] = {
    404: "not_found",
    405: "method_not_allowed",
}

_INTERNAL = "internal_error"


class ErrorDetail(BaseModel):
    code: str
    message: str
    field: str | None


class ErrorResponse(BaseModel):
    error: ErrorDetail


def status_for(error_type: type[AppError]) -> int:
    for cls in error_type.__mro__:
        if cls in STATUS_BY_ERROR:
            return STATUS_BY_ERROR[cls]
    return 500


def _error_response(
    request: Request,
    status_code: int,
    code: str,
    *,
    field: str | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    config: AppConfig = request.app.state.config
    body = ErrorResponse(
        error=ErrorDetail(
            code=code, message=config.http_errors.text_for(code), field=field
        )
    )
    return JSONResponse(
        status_code=status_code, content=body.model_dump(), headers=headers
    )


def _log_unexpected(request: Request, exc: BaseException) -> None:
    # Solo el path: la query puede traer tokens (el verify token de Meta).
    logger.error(
        "unhandled error",
        exc_info=exc,
        extra={"method": request.method, "path": request.url.path},
    )


async def _handle_app_error(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, AppError):  # pragma: no cover - registro por tipo
        raise exc
    status_code = status_for(type(exc))
    if status_code >= 500:
        _log_unexpected(request, exc)
        return _error_response(request, 500, _INTERNAL)
    return _error_response(request, status_code, exc.message_key, field=exc.field)


async def _handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):  # pragma: no cover
        raise exc
    field = None
    errors = exc.errors()
    if errors:
        location = [str(part) for part in errors[0].get("loc", ())]
        # ("body", "quantity") -> "quantity". Sin más que la sección, no hay campo.
        if len(location) > 1:
            field = location[-1]
    # Nunca se devuelve el input rechazado ni el detalle de Pydantic.
    return _error_response(request, 400, "invalid_input", field=field)


async def _handle_http_exception(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):  # pragma: no cover
        raise exc
    status_code = exc.status_code
    code = _FRAMEWORK_CODES.get(
        status_code, "invalid_input" if status_code < 500 else _INTERNAL
    )
    return _error_response(request, status_code, code, headers=exc.headers)


async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
    _log_unexpected(request, exc)
    return _error_response(request, 500, _INTERNAL)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    app.add_exception_handler(Exception, _handle_unexpected)
