"""Router del panel del staff. Vacío hasta el change del panel.

Vive bajo su propio prefijo, disjunto del webhook (API-4).
"""

from fastapi import APIRouter

PANEL_PREFIX = "/panel"

router = APIRouter(prefix=PANEL_PREFIX, tags=["panel"])
