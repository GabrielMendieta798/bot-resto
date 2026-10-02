"""Router del webhook de WhatsApp. Vacío hasta el change que lo implemente.

Vive bajo su propio prefijo, disjunto del panel (API-4): ninguna operación de
staff cuelga de acá.
"""

from fastapi import APIRouter

WEBHOOK_PREFIX = "/webhook"

router = APIRouter(prefix=WEBHOOK_PREFIX, tags=["webhook"])
