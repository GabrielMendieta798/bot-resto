"""Logging estructurado en JSON con enmascarado de teléfonos (SEC-3).

Un único handler en el root logger, con dos piezas:

- `PhoneMaskingFilter` enmascara el mensaje ya interpolado, los campos `extra`,
  el stacktrace y el stack info. Está en el handler, no en loggers sueltos, así
  cubre también lo que llega de librerías por propagación.
- `JsonFormatter` escribe una línea JSON por record.

El filtro es una red de seguridad, no el control principal: el código no
debería loguear teléfonos en primer lugar, sino `customer_id`.
"""

import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import TextIO

# 8 o más dígitos, con `+` inicial opcional y hasta dos separadores entre
# dígitos (espacio, guion, punto, paréntesis). Ocho es el número local
# argentino más corto sin característica; por debajo no se enmascara, para no
# destruir ids ni cantidades.
_PHONE_PATTERN = re.compile(r"\+?\d(?:[ \-.()]{0,2}\d){7,}")
_VISIBLE_DIGITS = 4

_STANDARD_RECORD_ATTRS = frozenset(
    vars(logging.LogRecord("", 0, "", 0, "", None, None))
) | {"message", "asctime"}

_HANDLER_NAME = "app.structured"

# Uvicorn instala sus propios handlers con propagate=False. Se los quita para
# que sus records pasen por el handler del root y salgan enmascarados en JSON.
_UVICORN_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access")

# A nivel INFO, httpx loguea la URL completa de cada request, query incluida:
# ahí puede viajar un token (SEC-2). Solo se dejan pasar advertencias y errores.
_HTTP_LIBRARY_LOGGERS = ("httpx", "httpcore")

_EXCEPTION_FORMATTER = logging.Formatter()


def _mask_match(match: re.Match[str]) -> str:
    text = match.group()
    total_digits = sum(char.isdigit() for char in text)
    seen = 0
    masked = []
    for char in text:
        if char.isdigit():
            seen += 1
            visible = seen > total_digits - _VISIBLE_DIGITS
            masked.append(char if visible else "*")
        else:
            masked.append(char)
    return "".join(masked)


def mask_phones(text: str) -> str:
    """Reemplaza cada teléfono por asteriscos, salvo sus últimos 4 dígitos."""
    return _PHONE_PATTERN.sub(_mask_match, text)


def _mask_value(value: object) -> object:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        masked = mask_phones(str(value))
        return value if masked == str(value) else masked
    if isinstance(value, dict):
        # Las claves también: un dict indexado por teléfono es un caso real.
        return {mask_phones(str(key)): _mask_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_mask_value(item) for item in value]
    return mask_phones(str(value))


class PhoneMaskingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = mask_phones(record.getMessage())
        record.args = None

        for key, value in list(vars(record).items()):
            if key not in _STANDARD_RECORD_ATTRS:
                setattr(record, key, _mask_value(value))

        if record.exc_info:
            formatted = _EXCEPTION_FORMATTER.formatException(record.exc_info)
            record.exc_text = mask_phones(formatted)
            record.exc_info = None
        elif record.exc_text:
            record.exc_text = mask_phones(record.exc_text)

        if record.stack_info:
            record.stack_info = mask_phones(record.stack_info)

        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key, value in vars(record).items():
            if key not in _STANDARD_RECORD_ATTRS and key not in payload:
                payload[key] = value

        exception_text = record.exc_text
        if not exception_text and record.exc_info:
            exception_text = self.formatException(record.exc_info)
        if exception_text:
            payload["exc_info"] = exception_text

        if record.stack_info:
            payload["stack_info"] = record.stack_info

        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(level: str, stream: TextIO | None = None) -> None:
    """Instala el handler estructurado en el root logger.

    Es idempotente: si ya hay un handler instalado por esta función, lo
    reemplaza en lugar de sumar otro.
    """
    root = logging.getLogger()
    for existing in list(root.handlers):
        if existing.get_name() == _HANDLER_NAME:
            root.removeHandler(existing)

    handler: logging.StreamHandler[TextIO] = logging.StreamHandler(
        stream if stream is not None else sys.stderr
    )
    handler.set_name(_HANDLER_NAME)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(PhoneMaskingFilter())

    root.addHandler(handler)
    root.setLevel(level)

    for name in _UVICORN_LOGGERS:
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True

    for name in _HTTP_LIBRARY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
