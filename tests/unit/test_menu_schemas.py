"""Forma de los schemas del menú.

Spec `menu-catalog`, requirement "Edit shape is validated by the edit object", y
spec `domain-data-boundary`, requirement "Money is Decimal and time is
zone-aware". Las reglas de valor (signo, escala, rango) no se prueban acá: son
del servicio.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.domain.menu.schemas import MenuItemRead, MenuItemUpdate

BUENOS_AIRES = timezone(timedelta(hours=-3))


def _read(**overrides: Any) -> MenuItemRead:
    fields: dict[str, Any] = {
        "id": 1,
        "category": "Parrilla",
        "name": "Bondiola",
        "description": "Con papas",
        "price": Decimal("8500.00"),
        "estimated_time_min": 25,
        "available": True,
        "created_at": datetime(2026, 10, 10, 21, 0, tzinfo=BUENOS_AIRES),
    }
    return MenuItemRead(**(fields | overrides))


def _failing_field(**changes: Any) -> str:
    with pytest.raises(ValidationError) as caught:
        MenuItemUpdate(**changes)
    errors = caught.value.errors()
    assert len(errors) == 1
    return str(errors[0]["loc"][0])


# --- MenuItemUpdate: forma ---------------------------------------------------


@pytest.mark.parametrize("field", ["category", "available", "id", "created_at"])
def test_field_outside_the_edit_is_rejected(field: str) -> None:
    assert _failing_field(**{field: "x"}) == field


@pytest.mark.parametrize("name", ["", "   ", "x" * 151, None])
def test_blank_long_or_null_name_is_rejected(name: str | None) -> None:
    assert _failing_field(name=name) == "name"


def test_name_of_150_characters_is_accepted() -> None:
    assert MenuItemUpdate(name="x" * 150).name == "x" * 150


@pytest.mark.parametrize(
    "price",
    [9200.5, 1500.0, True, Decimal("NaN"), Decimal("Infinity"), None],
    ids=["float", "float-integral", "bool", "nan", "infinity", "null"],
)
def test_price_that_is_not_exact_is_rejected(price: object) -> None:
    assert _failing_field(price=price) == "price"


@pytest.mark.parametrize(
    ("price", "expected"),
    [
        ("9200.00", Decimal("9200.00")),
        (" 9200.00 ", Decimal("9200.00")),
        ("1E+3", Decimal("1E+3")),
        ("-1.005", Decimal("-1.005")),
        (1500, Decimal("1500")),
        (Decimal("9200.00"), Decimal("9200.00")),
    ],
)
def test_price_as_exact_decimal_text_or_integer(
    price: object, expected: Decimal
) -> None:
    value = MenuItemUpdate(price=price).price

    assert isinstance(value, Decimal)
    assert value == expected
    assert value.as_tuple() == expected.as_tuple()


@pytest.mark.parametrize(
    "price", ["", "   ", "NaN", "Infinity", "1,5", "1_000", "+5", "0x10", "١٢٣"]
)
def test_monetary_text_that_is_not_decimal_text_is_rejected(price: str) -> None:
    assert _failing_field(price=price) == "price"


@pytest.mark.parametrize(
    ("estimated_time_min", "expected"), [(25, 25), ("25", 25), (" 25 ", 25), ("-5", -5)]
)
def test_estimated_time_as_integer_or_integer_text(
    estimated_time_min: object, expected: int
) -> None:
    assert MenuItemUpdate(estimated_time_min=estimated_time_min).estimated_time_min == (
        expected
    )


@pytest.mark.parametrize("estimated_time_min", [True, 12.5, "", "25.0", "2.5", "١٢"])
def test_estimated_time_that_is_not_an_integer_is_rejected(
    estimated_time_min: object,
) -> None:
    assert _failing_field(estimated_time_min=estimated_time_min) == (
        "estimated_time_min"
    )


def test_form_encoded_values_arrive_as_text() -> None:
    # Lo que entrega un formulario HTMX: todo string. El POST form-encoded real
    # se prueba en el change del panel, que suma `python-multipart`.
    form = {
        "name": " Bondiola braseada ",
        "description": "",
        "price": "9200.00",
        "estimated_time_min": "25",
    }

    changes = MenuItemUpdate.model_validate(form)

    assert changes.name == "Bondiola braseada"
    assert changes.description is None
    assert changes.price == Decimal("9200.00")
    assert changes.estimated_time_min == 25
    assert changes.model_fields_set == set(form)


def test_estimated_time_cannot_go_back_to_unknown() -> None:
    assert _failing_field(estimated_time_min=None) == "estimated_time_min"


def test_absent_and_empty_are_different() -> None:
    only_price = MenuItemUpdate(price=Decimal("9200.00"))
    empty_description = MenuItemUpdate(description="")
    null_description = MenuItemUpdate(description=None)

    assert only_price.model_fields_set == {"price"}
    assert empty_description.model_fields_set == {"description"}
    assert empty_description.description is None
    assert null_description.model_fields_set == {"description"}
    assert MenuItemUpdate().model_fields_set == set()


def test_name_and_description_are_trimmed() -> None:
    changes = MenuItemUpdate(name="  Bondiola braseada  ", description="  Al disco ")

    assert changes.name == "Bondiola braseada"
    assert changes.description == "Al disco"


def test_value_rules_are_not_shape() -> None:
    # Signo, escala y rango son reglas del servicio: la forma los deja pasar.
    changes = MenuItemUpdate(price=Decimal("-1.005"), estimated_time_min=-5)

    assert changes.price == Decimal("-1.005")
    assert changes.estimated_time_min == -5


# --- MenuItemUpdate como payload de un request ------------------------------


@pytest.fixture
def client(make_app: Callable[[], FastAPI]) -> TestClient:
    application = make_app()

    # Ruta solo de test: la app no expone ningún endpoint de menú.
    def edit_item(changes: MenuItemUpdate) -> dict[str, Any]:
        # El precio vuelve como texto para comparar el valor exacto, no un float.
        dumped = changes.model_dump(include=changes.model_fields_set)
        if "price" in dumped:
            dumped["price"] = str(dumped["price"])
        return dumped

    application.add_api_route("/test/menu-item", edit_item, methods=["POST"])
    return TestClient(application, raise_server_exceptions=False)


@pytest.mark.parametrize(
    ("payload", "field", "echoed"),
    [
        ({"name": "   "}, "name", None),
        ({"price": "mucho-SECRET"}, "price", "mucho-SECRET"),
        ({"price": 1500.5}, "price", "1500.5"),
        ({"category": "Pastas-SECRET"}, "category", "Pastas-SECRET"),
        (
            {"estimated_time_min": "veinte-SECRET"},
            "estimated_time_min",
            "veinte-SECRET",
        ),
        ({"estimated_time_min": None}, "estimated_time_min", None),
    ],
)
def test_shape_error_as_request_payload_is_400_without_echo(
    client: TestClient, payload: dict[str, Any], field: str, echoed: str | None
) -> None:
    response = client.post("/test/menu-item", json=payload)

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "invalid_input"
    assert error["field"] == field
    if echoed is not None:
        assert echoed not in response.text


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"price": "9200.00"}, {"price": "9200.00"}),
        ({"price": 1500}, {"price": "1500"}),
        ({"estimated_time_min": "25"}, {"estimated_time_min": 25}),
        ({"description": None}, {"description": None}),
    ],
)
def test_valid_payload_reaches_the_handler_as_exact_values(
    client: TestClient, payload: dict[str, Any], expected: dict[str, Any]
) -> None:
    response = client.post("/test/menu-item", json=payload)

    assert response.status_code == 200
    assert response.json() == expected


# --- MenuItemRead -------------------------------------------------------------


def test_read_with_naive_created_at_is_rejected() -> None:
    with pytest.raises(ValidationError):
        # Naive a propósito: es el caso que se rechaza.
        _read(created_at=datetime(2026, 10, 10, 21, 0))


def test_read_created_at_is_normalized_to_utc() -> None:
    item = _read()

    assert item.created_at.utcoffset() == timedelta(0)
    assert item.created_at == datetime(2026, 10, 11, 0, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    "price", [Decimal("8500"), Decimal("8500.5"), Decimal("8500.000"), 8500.0]
)
def test_read_price_is_a_decimal_with_two_places(price: object) -> None:
    with pytest.raises(ValidationError):
        _read(price=price)


def test_read_is_frozen() -> None:
    item = _read()

    with pytest.raises(ValidationError):
        item.price = Decimal("1.00")  # type: ignore[misc]
    assert item.price == Decimal("8500.00")
