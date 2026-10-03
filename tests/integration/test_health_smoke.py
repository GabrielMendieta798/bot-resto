"""Smoke test del health check contra la app real y una PostgreSQL real."""

from fastapi.testclient import TestClient
from sqlalchemy import make_url, text

from app.core.config import get_config
from app.main import create_app


def test_health_with_real_database_is_ok_and_leaks_nothing() -> None:
    app = create_app()
    database_url = make_url(get_config().settings.database_url)

    with TestClient(app) as client:
        response = client.get("/health")
        with app.state.engine.connect() as connection:
            server_version = connection.execute(
                text("SHOW server_version")
            ).scalar_one()

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "checks": {"app": "up", "database": "up"},
    }

    body = response.text
    for leaked in (
        database_url.render_as_string(hide_password=False),
        database_url.username,
        database_url.password,
        database_url.host,
        database_url.database,
        server_version,
        "PostgreSQL",
        "processed_whatsapp_messages",
    ):
        if leaked:
            assert str(leaked) not in body
