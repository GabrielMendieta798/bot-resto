"""Servicio del menú: consulta (UC-03), disponibilidad (UC-17) y edición (UC-18).

Valida las **reglas**: límites de valor y de negocio. La forma ya la validó
`MenuItemUpdate` (VAL-3). No ve la base: recibe el repositorio como interfaz y
no puede commitear lo que no ve; la transacción es de quien llama (GEN-1,
DAT-2, CONV-10).
"""

from decimal import Decimal
from typing import Protocol

from app.core.exceptions import InvalidInputError, NotFoundError
from app.domain.menu.schemas import MenuItemRead, MenuItemUpdate

# Ids válidos de una columna BIGINT. Fuera de rango no existe ningún item: se
# responde sin consultar la base, que fallaría con un error de tipo.
_MAX_ID = 2**63 - 1
_CENT = Decimal("0.01")
# Numeric(12,2): diez dígitos enteros.
_PRICE_LIMIT = Decimal(10) ** 10
# Integer de PostgreSQL.
_MAX_ESTIMATED_TIME = 2**31 - 1


class MenuRepository(Protocol):
    """Lo que el servicio necesita de la persistencia del menú.

    "No existe" es `None`: el error de dominio lo decide el servicio. Ningún
    método commitea.
    """

    def list_categories(self) -> list[str]: ...

    def list_available_items(self, category: str) -> list[MenuItemRead]: ...

    def list_all_items(self) -> list[MenuItemRead]: ...

    def get_item(self, item_id: int) -> MenuItemRead | None: ...

    def set_available(self, item_id: int, available: bool) -> MenuItemRead | None: ...

    def update_item(
        self, item_id: int, changes: MenuItemUpdate
    ) -> MenuItemRead | None: ...


class MenuService:
    def __init__(self, repository: MenuRepository) -> None:
        self._repository = repository

    def list_categories(self) -> list[str]:
        """Categorías con al menos un item disponible, cada una una vez."""
        return self._repository.list_categories()

    def list_available_items(self, category: str) -> list[MenuItemRead]:
        """Items disponibles de una categoría. Categoría inexistente: lista vacía."""
        return self._repository.list_available_items(category)

    def list_all_items(self) -> list[MenuItemRead]:
        """Todos los items, disponibles o no, para el staff."""
        return self._repository.list_all_items()

    def get_item(self, item_id: int) -> MenuItemRead:
        _check_id(item_id)
        return _found(self._repository.get_item(item_id), item_id)

    def set_available(self, item_id: int, available: bool) -> MenuItemRead:
        """Fija la disponibilidad al valor dado; no la invierte.

        Interpretación de DAT-5 (design D6): un toggle repetido dejaría el
        plato disponible por accidente. El item nunca se borra.
        """
        _check_id(item_id)
        return _found(self._repository.set_available(item_id, available), item_id)

    def update_item(self, item_id: int, changes: MenuItemUpdate) -> MenuItemRead:
        """Edita solo los campos presentes. Las reglas van antes de buscar el item."""
        _check_rules(changes)
        _check_id(item_id)
        return _found(self._repository.update_item(item_id, changes), item_id)


def _check_rules(changes: MenuItemUpdate) -> None:
    # Los mensajes son fijos: nunca llevan el valor rechazado.
    if not changes.model_fields_set:
        raise InvalidInputError("edit has no fields")

    # `None` solo puede ser "no vino": la forma rechaza el null explícito.
    price = changes.price
    if price is not None:
        if price < 0:
            raise InvalidInputError("price must not be negative", field="price")
        # El rango va antes que la escala: cuantizar un valor enorme excede la
        # precisión de Decimal.
        if abs(price) >= _PRICE_LIMIT:
            raise InvalidInputError("price is out of range", field="price")
        if price != price.quantize(_CENT):
            # Nunca se redondea en silencio.
            raise InvalidInputError(
                "price has more than two decimal places", field="price"
            )

    estimated_time = changes.estimated_time_min
    if estimated_time is not None and not 0 <= estimated_time <= _MAX_ESTIMATED_TIME:
        raise InvalidInputError(
            "estimated time is out of range", field="estimated_time_min"
        )


def _check_id(item_id: int) -> None:
    if not 1 <= item_id <= _MAX_ID:
        raise NotFoundError(f"menu item {item_id} not found")


def _found(item: MenuItemRead | None, item_id: int) -> MenuItemRead:
    if item is None:
        raise NotFoundError(f"menu item {item_id} not found")
    return item
