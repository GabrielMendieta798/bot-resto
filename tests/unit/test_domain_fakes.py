"""El repositorio en memoria cumple lo observable que los servicios esperan.

Si el fake filtrara u ordenara distinto que el repositorio real, los tests de
servicio estarían probando el fake. Estos chequeos fijan su comportamiento; la
paridad con PostgreSQL se prueba en `tests/integration/`.
"""

from decimal import Decimal

from app.domain.menu.schemas import MenuItemUpdate
from unit.domain_fakes import InMemoryMenuRepository


def _menu() -> InMemoryMenuRepository:
    repo = InMemoryMenuRepository()
    repo.add(category="Parrilla", name="Vacío", price="9800", available=False)
    repo.add(category="Parrilla", name="Bondiola", price="8500")
    repo.add(category="Pastas", name="Ravioles", price="7000")
    repo.add(category="Pastas", name="Ravioles", price="7200")
    repo.add(category="Postres", name="Flan", price="3000", available=False)
    return repo


def test_categories_only_with_available_items_once_and_sorted() -> None:
    assert _menu().list_categories() == ["Parrilla", "Pastas"]


def test_available_items_filtered_by_category_and_ordered_by_name_then_id() -> None:
    repo = _menu()

    pastas = repo.list_available_items("Pastas")
    parrilla = repo.list_available_items("Parrilla")

    assert [(item.name, item.id) for item in pastas] == [
        ("Ravioles", 3),
        ("Ravioles", 4),
    ]
    assert [item.name for item in parrilla] == ["Bondiola"]
    assert repo.list_available_items("Inexistente") == []


def test_all_items_include_unavailable_in_the_same_order() -> None:
    names = [item.name for item in _menu().list_all_items()]

    assert names == ["Bondiola", "Flan", "Ravioles", "Ravioles", "Vacío"]


def test_missing_item_is_none_for_every_lookup_and_change() -> None:
    repo = _menu()

    assert repo.get_item(999) is None
    assert repo.set_available(999, False) is None
    assert repo.update_item(999, MenuItemUpdate(name="x")) is None


def test_update_touches_only_present_fields_and_quantizes_the_price() -> None:
    repo = _menu()
    before = repo.stored(2)

    updated = repo.update_item(2, MenuItemUpdate(price=Decimal("9200.500")))

    assert updated is not None
    assert updated.price.as_tuple() == Decimal("9200.50").as_tuple()
    assert updated.model_dump(exclude={"price"}) == before.model_dump(exclude={"price"})


def test_calls_are_recorded() -> None:
    repo = _menu()

    repo.get_item(1)
    repo.list_categories()

    assert repo.calls == ["get_item", "list_categories"]
