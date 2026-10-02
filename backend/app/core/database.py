"""Engine y sesiones de SQLAlchemy (sync, DAT-3).

Importar este módulo no crea ningún engine ni lee configuración: el engine se
construye en el arranque de la app a partir de las settings validadas. `Base`
se mantiene acá porque los modelos y `backend/alembic/env.py` lo importan.
"""

import math

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import Settings


class Base(DeclarativeBase):
    pass


def build_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.database_url,
        # DAT-10: apagado por default; el guard de producción está en Settings.
        echo=settings.database_echo,
        # Descarta conexiones muertas del pool tras un corte de la base.
        pool_pre_ping=True,
        # libpq acepta segundos enteros: sin esto, una base que no responde
        # cuelga la conexión durante el timeout del sistema operativo.
        connect_args={
            "connect_timeout": max(1, math.ceil(settings.health_db_timeout_seconds))
        },
    )


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False)
