"""Repositorio del menú sobre SQLAlchemy (DAT-2, DAT-3).

Recibe una `Session` abierta y no controla la transacción: no hace commit,
rollback ni begin. Quien abrió la transacción decide si sus efectos persisten
(CONV-10). Devuelve schemas del dominio, nunca objetos ORM. Ninguna operación
borra un item (DAT-5).

El orden por nombre usa la collation de la base. Con `en_US.utf8`, la Ñ se
ordena como una N acentuada: "Ñoquis" antes que "Nuez" (design D7).
"""

from decimal import Decimal
from typing import Any

from sqlalchemy import RowMapping, select, update
from sqlalchemy.orm import Session

from app.domain.menu.schemas import MenuItemRead, MenuItemUpdate
from app.domain.menu.service import MenuRepository
from app.models.menu_item import MenuItem

_CENT = Decimal("0.01")
_COLUMNS = (
    MenuItem.id,
    MenuItem.category,
    MenuItem.name,
    MenuItem.description,
    MenuItem.price,
    MenuItem.estimated_time_min,
    MenuItem.available,
    MenuItem.created_at,
)
_ORDER = (MenuItem.name, MenuItem.id)


class SqlMenuRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_categories(self) -> list[str]:
        statement = (
            select(MenuItem.category)
            .where(MenuItem.available.is_(True))
            .distinct()
            .order_by(MenuItem.category)
        )
        return list(self._session.scalars(statement))

    def list_available_items(self, category: str) -> list[MenuItemRead]:
        statement = (
            select(*_COLUMNS)
            .where(MenuItem.available.is_(True), MenuItem.category == category)
            .order_by(*_ORDER)
        )
        return [_read(row._mapping) for row in self._session.execute(statement)]

    def list_all_items(self) -> list[MenuItemRead]:
        statement = select(*_COLUMNS).order_by(*_ORDER)
        return [_read(row._mapping) for row in self._session.execute(statement)]

    def get_item(self, item_id: int) -> MenuItemRead | None:
        statement = select(*_COLUMNS).where(MenuItem.id == item_id)
        row = self._session.execute(statement).one_or_none()
        return None if row is None else _read(row._mapping)

    def set_available(self, item_id: int, available: bool) -> MenuItemRead | None:
        return self._update(item_id, {"available": available})

    def update_item(self, item_id: int, changes: MenuItemUpdate) -> MenuItemRead | None:
        """Escribe solo las columnas presentes en la edición.

        Lo que no vino no aparece en el `SET`: dos ediciones simultáneas de
        campos distintos no se pisan (design D6).
        """
        values = changes.model_dump(include=changes.model_fields_set)
        if "price" in values:
            # El servicio ya rechazó más de dos decimales: esto no redondea,
            # solo fija la escala (1500.500 -> 1500.50).
            values["price"] = values["price"].quantize(_CENT)
        return self._update(item_id, values)

    def _update(self, item_id: int, values: dict[str, Any]) -> MenuItemRead | None:
        statement = (
            update(MenuItem)
            .where(MenuItem.id == item_id)
            .values(**values)
            .returning(*_COLUMNS)
            # Sin objetos ORM en la sesión que sincronizar: solo filas.
            .execution_options(synchronize_session=False)
        )
        row = self._session.execute(statement).one_or_none()
        return None if row is None else _read(row._mapping)


def _read(row: RowMapping) -> MenuItemRead:
    return MenuItemRead.model_validate(dict(row))


# Conformidad con la interfaz del dominio: mypy estricto falla acá si el
# repositorio deja de cumplir `MenuRepository` (design D1).
_CONFORMS_TO_PROTOCOL: type[MenuRepository] = SqlMenuRepository
