"""Traducción de errores a respuestas HTTP (API-2, API-3).

Todo error sale con el mismo cuerpo: `{"error": {"code", "message", "field"}}`.
El `message` sale siempre de `config/http_errors.yaml`; nunca del texto de la
excepción, que lo escribe un desarrollador y puede contener SQL o datos del
cliente. Ningún stacktrace sale hacia afuera: queda solo en el log, una vez.
"""

import logging
import traceback
from collections.abc import Mapping

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

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

# Errores HTTP que levanta el framework o una librería. Su `detail` se descarta.
_FRAMEWORK_CODES: dict[int, str] = {
    401: "not_authenticated",
    403: "permission_denied",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
}

_INTERNAL = "internal_error"

# Excepciones cuyo texto transporta datos del cliente por construcción: el
# driver agrega la fila completa (`DETAIL: Failing row contains ...`), una
# `PendingRollbackError` repite el error original, y Pydantic/FastAPI incluyen
# el input rechazado. Si cualquiera aparece en la cadena de la excepción, se
# loguean frames y tipos, nunca un mensaje.
_OPAQUE_ERRORS: tuple[type[BaseException], ...] = (
    SQLAlchemyError,
    ValidationError,
    ResponseValidationError,
)


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


def _safe_metadata(exc: BaseException) -> dict[str, object]:
    if isinstance(exc, DBAPIError):
        original = exc.orig
        diag = getattr(original, "diag", None)
        return {
            "sqlstate": getattr(original, "sqlstate", None),
            "constraint": getattr(diag, "constraint_name", None),
        }
    if isinstance(exc, ResponseValidationError):
        return {"validation_errors": len(exc.errors())}
    return {}


def _exception_chain(exc: BaseException) -> list[BaseException]:
    """La excepción y las que encadena, en el orden en que Python las imprime."""
    chain: list[BaseException] = []
    current: BaseException | None = exc
    while current is not None and all(current is not seen for seen in chain):
        chain.append(current)
        if current.__cause__ is not None:
            current = current.__cause__
        elif current.__context__ is not None and not current.__suppress_context__:
            current = current.__context__
        else:
            current = None
    return chain


def _frames_only(chain: list[BaseException]) -> str:
    parts = []
    for link in chain:
        frames = "".join(traceback.format_tb(link.__traceback__))
        parts.append(f"{type(link).__name__}\n{frames}")
    return "--- chained from ---\n".join(parts)


def _log_unexpected(request: Request, exc: BaseException) -> None:
    # Solo el path: la query puede traer tokens (el verify token de Meta).
    context: dict[str, object] = {
        "method": request.method,
        "path": request.url.path,
        "error_type": type(exc).__name__,
    }
    chain = _exception_chain(exc)
    if any(isinstance(link, _OPAQUE_ERRORS) for link in chain):
        context["error_chain"] = [type(link).__name__ for link in chain]
        for link in reversed(chain):
            context.update(_safe_metadata(link))
        context["stack"] = _frames_only(chain)
        logger.error("unhandled error", extra=context)
        return
    logger.error("unhandled error", exc_info=exc, extra=context)


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


class UnhandledErrorMiddleware:
    """Atrapa lo que ningún handler tradujo: un log y el 500 uniforme.

    Reemplaza al handler de `Exception`. Ese handler lo corre
    `ServerErrorMiddleware`, que después re-levanta la excepción, y uvicorn la
    vuelve a loguear completa ("Exception in ASGI application"), con el texto
    del error incluido. Acá la excepción no sale de la app.

    Cubre lo que corre por dentro: los middlewares que se agreguen después con
    `add_middleware` quedan por fuera, y sus propios errores no pasan por acá.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def tracking_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, tracking_send)
        except Exception as exc:
            request = Request(scope)
            _log_unexpected(request, exc)
            if response_started:
                # Ya salieron los headers (streaming) o la respuesta completa
                # (BackgroundTasks): no hay 500 posible. No se re-levanta: el
                # servidor cerraría la conexión igual, pero logueando la
                # excepción completa por segunda vez.
                return
            response = _error_response(request, 500, _INTERNAL)
            await response(scope, receive, send)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    app.add_middleware(UnhandledErrorMiddleware)
