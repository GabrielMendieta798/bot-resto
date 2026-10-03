"""Escenarios de la spec `application-runtime` (VAL-4, API-4, API-5, DAT-1)."""

import io
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.api import health, panel, webhook
from app.api.panel import PANEL_PREFIX
from app.api.webhook import WEBHOOK_PREFIX
from app.core.config import PROJECT_ROOT
from app.core.exceptions import ConfigError
from unit.fakes import FAKE_DATABASE_PASSWORD, UNREACHABLE_DATABASE_URL

HEALTH_TIMEOUT_SECONDS = 2
# Margen acotado por encima del timeout configurado: conexión rechazada en
# Windows reintenta el SYN y tarda ~2 s.
HEALTH_MARGIN_SECONDS = 4


@pytest.fixture
def unreachable_database(monkeypatch: pytest.MonkeyPatch, config_env: Path) -> None:
    monkeypatch.setenv("DATABASE_URL", UNREACHABLE_DATABASE_URL)
    monkeypatch.setenv("HEALTH_DB_TIMEOUT_SECONDS", str(HEALTH_TIMEOUT_SECONDS))


# --- Arranque ----------------------------------------------------------------


def test_invalid_configuration_prevents_building_the_app(
    make_app: Callable[[], FastAPI], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("APP_ENV")

    with pytest.raises(ConfigError):
        make_app()


def test_invalid_configuration_stops_the_server_process(config_env: Path) -> None:
    # Proceso real de uvicorn. APP_ENV con un valor inválido (no vacío), así
    # un `.env` local no puede completarlo.
    env = {**os.environ, "APP_ENV": "bogus", "PYTHONIOENCODING": "utf-8"}

    result = subprocess.run(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", "0"],
        cwd=PROJECT_ROOT / "backend",
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    output = result.stdout + result.stderr

    assert result.returncode != 0
    assert "APP_ENV" in output
    assert "Uvicorn running" not in output
    assert "bogus" not in output
    assert FAKE_DATABASE_PASSWORD not in output


# --- Prefijos ----------------------------------------------------------------


def test_webhook_and_panel_prefixes_are_disjoint() -> None:
    assert WEBHOOK_PREFIX != PANEL_PREFIX
    assert not WEBHOOK_PREFIX.startswith(PANEL_PREFIX)
    assert not PANEL_PREFIX.startswith(WEBHOOK_PREFIX)


def _api_routes(router: APIRouter) -> list[APIRoute]:
    return [route for route in router.routes if isinstance(route, APIRoute)]


def test_routes_hang_from_their_own_prefix() -> None:
    for route in _api_routes(webhook.router):
        assert route.path.startswith(WEBHOOK_PREFIX + "/")
    for route in _api_routes(panel.router):
        assert route.path.startswith(PANEL_PREFIX + "/")
        assert not route.path.startswith(WEBHOOK_PREFIX)


def test_app_exposes_no_route_outside_the_known_routers(
    make_app: Callable[[], FastAPI],
) -> None:
    # Todo path publicado tiene que venir de un router conocido, así los
    # chequeos de prefijo y de response_model no pueden quedar esquivados.
    known = {
        route.path
        for router in (health.router, webhook.router, panel.router)
        for route in _api_routes(router)
    }

    assert set(make_app().openapi()["paths"]) == known


@pytest.mark.parametrize(
    "path", ["/webhook/panel", "/webhook/panel/orders", "/webhook/orders"]
)
def test_staff_paths_under_the_webhook_prefix_return_404(
    make_app: Callable[[], FastAPI], path: str
) -> None:
    response = TestClient(make_app()).get(path)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_every_endpoint_declares_a_response_model() -> None:
    routes = [
        route
        for router in (health.router, webhook.router, panel.router)
        for route in _api_routes(router)
    ]

    assert routes
    for route in routes:
        assert route.response_model is not None, route.path


# --- Health check con la base caída ------------------------------------------


def test_health_with_unreachable_database_returns_503_with_body(
    unreachable_database: None, make_app: Callable[[], FastAPI]
) -> None:
    client = TestClient(make_app())
    started = time.monotonic()

    response = client.get("/health")

    elapsed = time.monotonic() - started
    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "checks": {"app": "up", "database": "down"},
    }
    assert elapsed < HEALTH_TIMEOUT_SECONDS + HEALTH_MARGIN_SECONDS


def test_health_response_leaks_no_internals(
    unreachable_database: None, make_app: Callable[[], FastAPI]
) -> None:
    body = TestClient(make_app()).get("/health").text.lower()

    for leaked in (
        UNREACHABLE_DATABASE_URL.lower(),
        "bot_user",
        FAKE_DATABASE_PASSWORD.lower(),
        "127.0.0.1",
        "postgres",
        "psycopg",
        "sqlalchemy",
        "select",
        "connection",
        "refused",
        "processed_whatsapp_messages",
    ):
        assert leaked not in body


def test_health_failure_is_logged_without_secrets(
    unreachable_database: None,
    make_app: Callable[[], FastAPI],
    log_buffer: Callable[[], io.StringIO],
) -> None:
    client = TestClient(make_app())
    logs = log_buffer()

    client.get("/health")

    output = logs.getvalue()
    records = [json.loads(line) for line in output.splitlines() if line]
    [failure] = [r for r in records if r["message"] == "database health check failed"]
    assert failure["error_type"] == "OperationalError"
    assert UNREACHABLE_DATABASE_URL not in output
    assert FAKE_DATABASE_PASSWORD not in output
    assert "127.0.0.1" not in output


# --- Ciclo de vida -----------------------------------------------------------


def test_shutdown_closes_the_outbound_http_client(
    make_app: Callable[[], FastAPI],
) -> None:
    app = make_app()

    with TestClient(app):
        assert not app.state.http_client.is_closed

    assert app.state.http_client.is_closed
