"""Escenarios de la spec `menu-catalog` contra el repositorio en memoria (VER-3).

Las reglas del menú no necesitan una base: el filtro, el orden, la
disponibilidad, el "no existe" y las reglas de edición se prueban acá, sin red.
Lo que solo la base puede probar (collation, tipos de psycopg, que la fila no
se borre, el snapshot de DAT-4) va en `tests/integration/`.
"""

from decimal import Decimal
from typing import Any

import pytest

from app.core.exceptions import InvalidInputError, NotFoundError
from app.domain.menu.schemas import MenuItemUpdate
from app.domain.menu.service import MenuService
from unit.domain_fakes import InMemoryMenuRepository


@pytest.fixture
def repo() -> InMemoryMenuRepository:
    repo = InMemoryMenuRepository()
    repo.add(  # id 1
        category="Parrilla",
        name="Bondiola",
        price="8500.00",
        estimated_time_min=25,
        description="Con papas",
    )
    repo.add(category="Parrilla", name="Vacío", price="9800", available=False)  # 2
    repo.add(category="Pastas", name="Ravioles", price="7000")  # id 3
    repo.add(category="Pastas", name="Ñoquis", price="6500")  # id 4
    repo.add(category="Pastas", name="Ravioles", price="7200")  # id 5
    repo.add(category="Postres", name="Flan", price="3000")  # id 6
    return repo


@pytest.fixture
def service(repo: InMemoryMenuRepository) -> MenuService:
    return MenuService(repo)


def _exception_texts(error: BaseException) -> str:
    """Mensaje, repr y toda la cadena de la excepción, como texto."""
    texts: list[str] = []
    current: BaseException | None = error
    while current is not None:
        texts += [str(current), repr(current)]
        current = current.__cause__ or current.__context__
    return "\n".join(texts)


# --- Categorías ----------------------------------------------------------------


def test_category_with_an_available_item_is_listed_once(service: MenuService) -> None:
    # Parrilla tiene un item disponible y uno agotado.
    assert service.list_categories().count("Parrilla") == 1


def test_category_with_every_item_sold_out_is_hidden(service: MenuService) -> None:
    service.set_available(1, False)

    assert "Parrilla" not in service.list_categories()


def test_last_available_item_sold_out_hides_the_category(
    service: MenuService,
) -> None:
    assert "Postres" in service.list_categories()

    service.set_available(6, False)

    assert "Postres" not in service.list_categories()


def test_categories_are_sorted(service: MenuService) -> None:
    categories = service.list_categories()

    assert categories == sorted(categories)


# --- Listados ------------------------------------------------------------------


def test_available_items_exclude_unavailable_ones(service: MenuService) -> None:
    items = service.list_available_items("Parrilla")

    assert [item.name for item in items] == ["Bondiola"]
    bondiola = items[0]
    assert bondiola.price == Decimal("8500.00")
    assert bondiola.estimated_time_min == 25


def test_available_items_order_is_deterministic(service: MenuService) -> None:
    first = service.list_available_items("Pastas")
    second = service.list_available_items("Pastas")

    assert first == second
    ravioles = [item.id for item in first if item.name == "Ravioles"]
    assert ravioles == [3, 5]
    assert [item.name for item in first] == sorted(item.name for item in first)


def test_unknown_category_is_an_empty_list(service: MenuService) -> None:
    assert service.list_available_items("Sushi") == []


def test_staff_sees_sold_out_items_with_their_availability(
    service: MenuService,
) -> None:
    availability = {item.name: item.available for item in service.list_all_items()}

    assert availability["Bondiola"] is True
    assert availability["Vacío"] is False


def test_staff_list_uses_the_customer_order(service: MenuService) -> None:
    items = service.list_all_items()

    assert [(item.name, item.id) for item in items] == sorted(
        (item.name, item.id) for item in items
    )


def test_unavailable_item_is_still_found(service: MenuService) -> None:
    item = service.get_item(2)

    assert item.name == "Vacío"
    assert item.available is False


# --- Disponibilidad ------------------------------------------------------------


def test_sold_out_keeps_the_item_and_its_data(
    service: MenuService, repo: InMemoryMenuRepository
) -> None:
    before = repo.stored(1)

    service.set_available(1, False)

    after = repo.stored(1)
    assert after.model_dump(exclude={"available"}) == before.model_dump(
        exclude={"available"}
    )
    assert after.available is False
    assert 1 not in [item.id for item in service.list_available_items("Parrilla")]


def test_back_on_the_menu(service: MenuService) -> None:
    service.set_available(2, True)

    assert "Vacío" in [item.name for item in service.list_available_items("Parrilla")]


@pytest.mark.parametrize("available", [False, True])
def test_setting_the_same_value_twice(service: MenuService, available: bool) -> None:
    first = service.set_available(1, available)
    second = service.set_available(1, available)

    assert first.available is available
    assert second == first


# --- No existe -----------------------------------------------------------------


@pytest.mark.parametrize(
    "call",
    [
        lambda s: s.get_item(999999),
        lambda s: s.set_available(999999, False),
        lambda s: s.update_item(999999, MenuItemUpdate(name="Matambre-SECRET")),
    ],
    ids=["get", "set_available", "update"],
)
def test_missing_item_raises_not_found_with_only_the_id(
    service: MenuService, call: Any
) -> None:
    with pytest.raises(NotFoundError) as caught:
        call(service)

    assert str(caught.value) == "menu item 999999 not found"
    assert "Matambre-SECRET" not in _exception_texts(caught.value)


@pytest.mark.parametrize("item_id", [0, -1, 2**63])
def test_identifier_out_of_range_is_not_found_without_querying(
    service: MenuService, repo: InMemoryMenuRepository, item_id: int
) -> None:
    for call in (
        lambda: service.get_item(item_id),
        lambda: service.set_available(item_id, True),
        lambda: service.update_item(item_id, MenuItemUpdate(name="Matambre")),
    ):
        with pytest.raises(NotFoundError):
            call()

    assert repo.calls == []


# --- Edición parcial -----------------------------------------------------------


def test_editing_only_the_price_leaves_the_rest(
    service: MenuService, repo: InMemoryMenuRepository
) -> None:
    before = repo.stored(1)

    updated = service.update_item(1, MenuItemUpdate(price=Decimal("9200.00")))

    assert updated.price == Decimal("9200.00")
    assert updated.model_dump(exclude={"price"}) == before.model_dump(exclude={"price"})
    assert repo.stored(1) == updated


def test_absent_description_is_kept_and_empty_one_clears_it(
    service: MenuService,
) -> None:
    kept = service.update_item(1, MenuItemUpdate(price=Decimal("9000.00")))
    assert kept.description == "Con papas"

    cleared = service.update_item(1, MenuItemUpdate(description=""))
    assert cleared.description is None


def test_name_is_stored_trimmed(service: MenuService) -> None:
    updated = service.update_item(1, MenuItemUpdate(name="  Bondiola braseada  "))

    assert updated.name == "Bondiola braseada"


def test_empty_edit_is_rejected_and_the_item_is_unchanged(
    service: MenuService, repo: InMemoryMenuRepository
) -> None:
    before = repo.stored(1)

    with pytest.raises(InvalidInputError) as caught:
        service.update_item(1, MenuItemUpdate())

    assert caught.value.field is None
    assert repo.stored(1) == before
    assert "update_item" not in repo.calls


# --- Reglas de edición ---------------------------------------------------------


@pytest.mark.parametrize(
    ("changes", "field", "rejected"),
    [
        ({"price": Decimal("-1.00")}, "price", "-1.00"),
        ({"price": Decimal("1500.505")}, "price", "1500.505"),
        ({"price": Decimal("10000000000.00")}, "price", "10000000000"),
        ({"price": "1E+30"}, "price", "1E+30"),
        ({"price": "1.5E-3"}, "price", "1.5E-3"),
        ({"estimated_time_min": -5}, "estimated_time_min", "-5"),
        ({"estimated_time_min": 2147483648}, "estimated_time_min", "2147483648"),
        ({"estimated_time_min": "-5"}, "estimated_time_min", "-5"),
    ],
)
def test_edit_breaking_a_rule_is_rejected_without_touching_the_item(
    service: MenuService,
    repo: InMemoryMenuRepository,
    changes: dict[str, Any],
    field: str,
    rejected: str,
) -> None:
    before = repo.stored(1)

    with pytest.raises(InvalidInputError) as caught:
        service.update_item(1, MenuItemUpdate(**changes))

    assert caught.value.field == field
    assert rejected not in _exception_texts(caught.value)
    assert repo.stored(1) == before
    # Las reglas van antes de buscar el item.
    assert repo.calls == []


def test_too_many_decimals_is_never_rounded(
    service: MenuService, repo: InMemoryMenuRepository
) -> None:
    with pytest.raises(InvalidInputError):
        service.update_item(1, MenuItemUpdate(price=Decimal("1500.505")))

    assert repo.stored(1).price == Decimal("8500.00")


def test_rules_are_checked_before_the_item_is_looked_up(
    service: MenuService,
) -> None:
    # Edición inválida sobre un item inexistente: gana la regla, no el 404.
    with pytest.raises(InvalidInputError):
        service.update_item(999999, MenuItemUpdate(price=Decimal("-1.00")))


@pytest.mark.parametrize(
    ("price", "stored"),
    [
        (Decimal("1500.500"), Decimal("1500.50")),
        ("1E+3", Decimal("1000.00")),
        (Decimal("9999999999.99"), Decimal("9999999999.99")),
    ],
)
def test_exact_prices_are_stored_with_two_places(
    service: MenuService, price: object, stored: Decimal
) -> None:
    updated = service.update_item(1, MenuItemUpdate(price=price))

    assert updated.price.as_tuple() == stored.as_tuple()


def test_zero_price_and_zero_time_are_valid(service: MenuService) -> None:
    updated = service.update_item(
        1, MenuItemUpdate(price=Decimal("0"), estimated_time_min=0)
    )

    assert updated.price == Decimal("0.00")
    assert updated.estimated_time_min == 0


def test_item_without_estimated_time_reads_it_as_absent(
    repo: InMemoryMenuRepository, service: MenuService
) -> None:
    item = repo.add(
        category="Bebidas", name="Agua", price="1500", estimated_time_min=None
    )

    assert service.get_item(item.id).estimated_time_min is None
    listed = service.list_available_items("Bebidas")
    assert listed[0].estimated_time_min is None
