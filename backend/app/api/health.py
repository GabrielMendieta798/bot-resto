"""Health check: estado de la app y conectividad con la base.

Responde 200 si la base contesta y 503 si no, siempre con cuerpo. El cuerpo
nunca incluye la cadena de conexión, el host, versiones, tablas ni el texto del
error de la base: un health check es público por naturaleza.
"""

import logging
from typing import Literal

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import AppConfig

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


class HealthChecks(BaseModel):
    app: Literal["up"]
    database: Literal["up", "down"]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    checks: HealthChecks


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse, "description": "Base no disponible"}},
)
def health(request: Request, response: Response) -> HealthResponse:
    # `def` y no `async def` (DAT-1): toca la base y FastAPI lo corre en su
    # threadpool.
    config: AppConfig = request.app.state.config
    engine: Engine = request.app.state.engine

    if _database_is_up(engine, config.settings.health_db_timeout_seconds):
        return HealthResponse(status="ok", checks=HealthChecks(app="up", database="up"))

    response.status_code = 503
    return HealthResponse(
        status="degraded", checks=HealthChecks(app="up", database="down")
    )


def _database_is_up(engine: Engine, timeout_seconds: float) -> bool:
    try:
        with engine.connect() as connection:
            # Acota también la consulta, no solo la conexión. `is_local=true`:
            # vale solo para esta transacción.
            connection.execute(
                text("SELECT set_config('statement_timeout', :ms, true)"),
                {"ms": str(int(timeout_seconds * 1000))},
            )
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        # Solo el tipo: el mensaje de psycopg incluye host y puerto.
        logger.warning(
            "database health check failed",
            extra={"component": "database", "error_type": type(exc).__name__},
        )
        return False
    return True
