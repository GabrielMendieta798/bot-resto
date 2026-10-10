"""Repositorios en memoria para los tests de los servicios de dominio.

Cumplen la misma interfaz que los repositorios reales (`app/db/repositories/`)
y reproducen lo observable que los servicios necesitan: filtros, orden y
"no existe" como `None`. No reproducen la base: la collation del orden, los
tipos que devuelve psycopg y la concurrencia se prueban en `tests/integration/`
(VER-3).
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from app.domain.menu.schemas import MenuItemRead, MenuItemUpdate

CENT = Decimal("0.01")
FIXED_CREATED_AT = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)


@dataclass
class InMemoryMenuRepository:
    """Menú en memoria. `calls` registra cada método invocado, para verificar
    que el servicio no consulta el repositorio cuando no corresponde."""

    _items: dict[int, MenuItemRead] = field(default_factory=dict)
    _next_id: int = 1
    calls: list[str] = field(default_factory=list)

    def add(
        self,
        *,
        category: str,
        name: str,
        price: str,
        estimated_time_min: int | None = 20,
        available: bool = True,
        description: str | None = None,
    ) -> MenuItemRead:
        """Alta solo para preparar tests: el servicio no da altas (non-goal)."""
        item = MenuItemRead(
            id=self._next_id,
            category=category,
            name=name,
            description=description,
            price=Decimal(price).quantize(CENT),
            estimated_time_min=estimated_time_min,
            available=available,
            created_at=FIXED_CREATED_AT,
        )
        self._items[item.id] = item
        self._next_id += 1
        return item

    def stored(self, item_id: int) -> MenuItemRead:
        """Lectura directa, sin pasar por la interfaz ni registrar la llamada."""
        return self._items[item_id]

    # --- Interfaz del repositorio ------------------------------------------

    def list_categories(self) -> list[str]:
        self.calls.append("list_categories")
        return sorted(
            {item.category for item in self._items.values() if item.available}
        )

    def list_available_items(self, category: str) -> list[MenuItemRead]:
        self.calls.append("list_available_items")
        return [
            item
            for item in self._sorted()
            if item.available and item.category == category
        ]

    def list_all_items(self) -> list[MenuItemRead]:
        self.calls.append("list_all_items")
        return self._sorted()

    def get_item(self, item_id: int) -> MenuItemRead | None:
        self.calls.append("get_item")
        return self._items.get(item_id)

    def set_available(self, item_id: int, available: bool) -> MenuItemRead | None:
        self.calls.append("set_available")
        return self._replace(item_id, {"available": available})

    def update_item(self, item_id: int, changes: MenuItemUpdate) -> MenuItemRead | None:
        self.calls.append("update_item")
        values = changes.model_dump(include=changes.model_fields_set)
        if "price" in values:
            # Igual que el repositorio real: cuantiza antes de escribir.
            values["price"] = values["price"].quantize(CENT)
        return self._replace(item_id, values)

    # --- Internos ----------------------------------------------------------

    def _sorted(self) -> list[MenuItemRead]:
        # Orden por nombre y, a igualdad, por id. Python ordena por punto de
        # código (como la collation C); la de la base se prueba en integración.
        return sorted(self._items.values(), key=lambda item: (item.name, item.id))

    def _replace(self, item_id: int, values: dict[str, object]) -> MenuItemRead | None:
        current = self._items.get(item_id)
        if current is None:
            return None
        updated = MenuItemRead.model_validate(current.model_dump() | values)
        self._items[item_id] = updated
        return updated
