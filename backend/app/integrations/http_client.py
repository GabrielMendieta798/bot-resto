"""Cliente HTTP saliente compartido, con timeouts explícitos.

Toda llamada a un servicio externo pasa por acá, así ninguna puede quedar
colgada sin límite de tiempo. Es sync, como el resto del stack (DAT-3): lo usan
path operations `def` y jobs del scheduler.

No sabe nada de ningún canal en particular: URLs, tokens y payloads los pone el
adapter que lo use.
"""

from collections.abc import Mapping
from urllib.parse import urlsplit

import httpx

from app.core.config import Settings
from app.core.exceptions import OutboundHttpError, OutboundTimeoutError


class OutboundHttpClient:
    def __init__(
        self,
        *,
        connect: float,
        read: float,
        write: float,
        pool: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._timeout = httpx.Timeout(
            connect=connect, read=read, write=write, pool=pool
        )
        self._client = httpx.Client(timeout=self._timeout, transport=transport)

    @classmethod
    def from_settings(cls, settings: Settings) -> "OutboundHttpClient":
        return cls(
            connect=settings.http_connect_timeout_seconds,
            read=settings.http_read_timeout_seconds,
            write=settings.http_write_timeout_seconds,
            pool=settings.http_pool_timeout_seconds,
        )

    @property
    def timeout(self) -> httpx.Timeout:
        return self._timeout

    @property
    def is_closed(self) -> bool:
        return self._client.is_closed

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
        json: object = None,
        content: bytes | None = None,
    ) -> httpx.Response:
        try:
            return self._client.request(
                method, url, headers=headers, params=params, json=json, content=content
            )
        except httpx.TimeoutException as exc:
            # El mensaje nombra solo método y host: los headers llevan tokens y
            # la query o el body pueden llevar datos del cliente. `from None`
            # porque la excepción de httpx guarda el request completo.
            raise OutboundTimeoutError(_describe(exc, method, url)) from None
        except httpx.HTTPError as exc:
            raise OutboundHttpError(_describe(exc, method, url)) from None

    def close(self) -> None:
        self._client.close()


def _describe(exc: httpx.HTTPError, method: str, url: str) -> str:
    host = urlsplit(url).hostname or "unknown host"
    return f"{type(exc).__name__} on {method.upper()} {host}"
