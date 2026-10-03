"""Punto de entrada de la aplicación: `uvicorn app.main:app` desde `backend/`.

`create_app()` valida toda la configuración ANTES de construir la app. Una
config inválida rompe el import de este módulo, así que uvicorn termina sin
llegar a abrir el puerto (VAL-4). La base no se prueba al arrancar: si está
caída la app levanta igual y `/health` lo informa.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import health, panel, webhook
from app.api.errors import register_exception_handlers
from app.core.config import get_config
from app.core.database import build_engine, build_session_factory
from app.core.logging import configure_logging
from app.integrations.http_client import OutboundHttpClient


def create_app() -> FastAPI:
    config = get_config()
    configure_logging(config.settings.log_level)

    engine = build_engine(config.settings)
    http_client = OutboundHttpClient.from_settings(config.settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            http_client.close()
            engine.dispose()

    app = FastAPI(title="bot-resto", lifespan=lifespan)
    app.state.config = config
    app.state.engine = engine
    app.state.session_factory = build_session_factory(engine)
    app.state.http_client = http_client

    register_exception_handlers(app)

    app.include_router(health.router)
    app.include_router(webhook.router)
    app.include_router(panel.router)

    return app


app = create_app()
