"""`backend/alembic/env.py` está fuera de alcance: los nombres que importa
(`settings` de config y `Base` de database) tienen que seguir resolviendo."""

import os
from pathlib import Path


def test_alembic_imports_still_resolve(config_env: Path) -> None:
    # Mismos imports que backend/alembic/env.py.
    from app import models  # noqa: F401
    from app.core.config import settings
    from app.core.database import Base

    assert str(settings.database_url) == os.environ["DATABASE_URL"]
    assert "processed_whatsapp_messages" in Base.metadata.tables
