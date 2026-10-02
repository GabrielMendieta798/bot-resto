"""Escenarios de la spec `outbound-http-client`."""

import inspect
import socket
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from app.core.config import load_config
from app.core.exceptions import OutboundHttpError, OutboundTimeoutError
from app.integrations import http_client
from app.integrations.http_client import OutboundHttpClient


@pytest.fixture
def silent_server_url() -> Iterator[str]:
    """Servidor en loopback que acepta la conexión TCP y nunca responde.

    No hace falta `accept()`: el kernel completa el handshake contra el
    backlog, así que el cliente conecta, envía el request y queda esperando
    la respuesta.
    """
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen()
    port = server.getsockname()[1]
    yield f"http://127.0.0.1:{port}/never-answers"
    server.close()


def _client(transport: httpx.BaseTransport | None = None) -> OutboundHttpClient:
    return OutboundHttpClient(connect=1, read=0.5, write=1, pool=1, transport=transport)


def test_timeouts_come_from_configuration(
    config_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HTTP_CONNECT_TIMEOUT_SECONDS", "1.5")
    monkeypatch.setenv("HTTP_READ_TIMEOUT_SECONDS", "2.5")
    monkeypatch.setenv("HTTP_WRITE_TIMEOUT_SECONDS", "3.5")
    monkeypatch.setenv("HTTP_POOL_TIMEOUT_SECONDS", "4.5")

    client = OutboundHttpClient.from_settings(load_config(env_file=None).settings)

    assert client.timeout == httpx.Timeout(connect=1.5, read=2.5, write=3.5, pool=4.5)
    client.close()


def test_default_timeouts_are_all_finite(config_env: Path) -> None:
    client = OutboundHttpClient.from_settings(load_config(env_file=None).settings)

    timeouts = client.timeout.as_dict()
    assert set(timeouts) == {"connect", "read", "write", "pool"}
    assert all(value is not None and value > 0 for value in timeouts.values())
    client.close()


def test_server_that_never_answers_raises_timeout_quickly(
    silent_server_url: str,
) -> None:
    client = _client()
    started = time.monotonic()

    with pytest.raises(OutboundTimeoutError):
        client.request("GET", silent_server_url)

    assert time.monotonic() - started < 5
    client.close()


def test_timeout_error_leaks_no_request_details() -> None:
    def raise_timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    client = _client(httpx.MockTransport(raise_timeout))

    with pytest.raises(OutboundTimeoutError) as caught:
        client.request(
            "POST",
            "https://api.example.com/v1/send?access_token=query-secret",
            headers={"Authorization": "Bearer header-secret"},
            json={"to": "5491122334455", "text": "body-secret"},
        )

    error = caught.value
    message = str(error)
    assert message == "ReadTimeout on POST api.example.com"
    assert error.__cause__ is None
    assert error.__suppress_context__
    for leaked in ("query-secret", "header-secret", "body-secret", "5491122334455"):
        assert leaked not in message
    client.close()


def test_other_transport_errors_become_outbound_http_error() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = _client(httpx.MockTransport(refuse))

    with pytest.raises(OutboundHttpError) as caught:
        client.request("GET", "https://api.example.com/health")

    assert not isinstance(caught.value, OutboundTimeoutError)
    client.close()


def test_closed_client_refuses_new_requests() -> None:
    calls: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200)

    client = _client(httpx.MockTransport(record))
    client.close()

    assert client.is_closed
    with pytest.raises(RuntimeError):
        client.request("GET", "https://api.example.com/health")
    assert calls == []


def test_client_module_has_no_channel_coupling() -> None:
    source = inspect.getsource(http_client).lower()

    for marker in ("whatsapp", "pywa", "facebook.com", "graph.", "wamid"):
        assert marker not in source
