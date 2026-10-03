"""Escenarios de la spec `error-contract` (API-2, API-3)."""

import io
import json
from collections.abc import Callable
from typing import Any

import pytest
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError, OperationalError, PendingRollbackError

from app.api.errors import UnhandledErrorMiddleware
from app.core import exceptions
from app.core.config import get_config
from app.core.exceptions import (
    AppError,
    ConflictError,
    InvalidInputError,
    InvalidStateTransitionError,
    NotAuthenticatedError,
    NotFoundError,
    OutboundHttpError,
    OutboundTimeoutError,
    PermissionDeniedError,
)

PHONE = "5491122334455"
# Texto de excepción con SQL y un teléfono: no debe salir en ninguna respuesta.
LEAKY_DETAIL = "SELECT * FROM customers WHERE phone='5491122334455'"


class _Payload(BaseModel):
    quantity: int


def _raising(error: BaseException) -> Callable[[], None]:
    def endpoint() -> None:
        raise error

    return endpoint


def _client(app: FastAPI) -> TestClient:
    # Para los tests que solo miran la respuesta. Los que verifican que la
    # excepción no escapa de la app usan `TestClient(app)` con el default.
    return TestClient(app, raise_server_exceptions=False)


def _text(code: str) -> str:
    return get_config().http_errors.text_for(code)


@pytest.fixture
def app(make_app: Callable[[], FastAPI]) -> FastAPI:
    application = make_app()

    def accept_payload(payload: _Payload) -> dict[str, int]:
        return {"quantity": payload.quantity}

    application.add_api_route("/test/payload", accept_payload, methods=["POST"])
    return application


# --- Categorías → códigos de API-3 -------------------------------------------


@pytest.mark.parametrize(
    ("error_type", "status", "code"),
    [
        (InvalidInputError, 400, "invalid_input"),
        (NotAuthenticatedError, 401, "not_authenticated"),
        (PermissionDeniedError, 403, "permission_denied"),
        (NotFoundError, 404, "not_found"),
        (ConflictError, 409, "conflict"),
        (InvalidStateTransitionError, 409, "invalid_state_transition"),
    ],
)
def test_category_maps_to_status_with_uniform_body(
    app: FastAPI, error_type: type[AppError], status: int, code: str
) -> None:
    app.add_api_route("/test/raise", _raising(error_type(LEAKY_DETAIL)))

    response = _client(app).get("/test/raise")

    assert response.status_code == status
    assert response.json() == {
        "error": {"code": code, "message": _text(code), "field": None}
    }
    assert "SELECT" not in response.text
    assert PHONE not in response.text


def test_invalid_input_names_the_field(app: FastAPI) -> None:
    app.add_api_route(
        "/test/raise", _raising(InvalidInputError("too many", field="quantity"))
    )

    response = _client(app).get("/test/raise")

    assert response.status_code == 400
    assert response.json()["error"]["field"] == "quantity"


def test_subclass_without_mapping_inherits_ancestor_status(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(exceptions, "_TEXT_KEYS", set(exceptions._TEXT_KEYS))

    class _TableAlreadyTakenError(ConflictError):
        pass

    app.add_api_route("/test/raise", _raising(_TableAlreadyTakenError()))

    response = _client(app).get("/test/raise")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_unmapped_app_error_is_a_generic_500(app: FastAPI) -> None:
    app.add_api_route("/test/raise", _raising(OutboundTimeoutError(LEAKY_DETAIL)))

    response = _client(app).get("/test/raise")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "SELECT" not in response.text


# --- Validación de payload ---------------------------------------------------


def test_body_validation_failure_returns_400_without_echo(app: FastAPI) -> None:
    response = _client(app).post("/test/payload", json={"quantity": "many-SECRET"})

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "invalid_input",
            "message": _text("invalid_input"),
            "field": "quantity",
        }
    }
    assert "many-SECRET" not in response.text


def test_missing_body_returns_400(app: FastAPI) -> None:
    response = _client(app).post("/test/payload")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_input"


# --- Errores del framework ---------------------------------------------------


def test_unknown_route_returns_uniform_404(app: FastAPI) -> None:
    response = _client(app).get("/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "not_found", "message": _text("not_found"), "field": None}
    }


def test_unsupported_method_returns_uniform_405(app: FastAPI) -> None:
    response = _client(app).post("/health")

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"
    assert response.headers["allow"] == "GET"


# --- Errores inesperados -----------------------------------------------------


def test_unexpected_error_returns_500_and_logs_masked_stacktrace(
    app: FastAPI, log_buffer: Callable[[], io.StringIO]
) -> None:
    app.add_api_route("/test/boom", _raising(RuntimeError(LEAKY_DETAIL)))
    logs = log_buffer()

    response = _client(app).get("/test/boom?token=query-secret")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_error",
            "message": _text("internal_error"),
            "field": None,
        }
    }
    for leaked in ("Traceback", "RuntimeError", LEAKY_DETAIL, "customers", "SELECT"):
        assert leaked not in response.text

    records = [json.loads(line) for line in logs.getvalue().splitlines() if line]
    [error_record] = [r for r in records if r["message"] == "unhandled error"]
    assert "Traceback" in error_record["exc_info"]
    assert "RuntimeError" in error_record["exc_info"]
    assert error_record["method"] == "GET"
    assert error_record["path"] == "/test/boom"
    assert PHONE not in logs.getvalue()
    assert "query-secret" not in logs.getvalue()


def test_database_driver_error_leaks_nothing(app: FastAPI) -> None:
    driver_error = OperationalError(
        "SELECT total FROM orders WHERE id = 1",
        {},
        Exception("connection to server at db.internal.example failed"),
    )
    app.add_api_route("/test/db", _raising(driver_error))

    response = _client(app).get("/test/db")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    for leaked in ("SELECT", "orders", "db.internal.example", "connection to server"):
        assert leaked not in response.text


def test_error_body_has_only_the_error_key(app: FastAPI) -> None:
    response = _client(app).get("/does-not-exist")

    assert set(response.json()) == {"error"}
    assert set(response.json()["error"]) == {"code", "message", "field"}


# --- Log de errores inesperados: una vez y sin datos de clientes -------------

ADDRESS = "Av. Siempreviva 742"


class _DriverError(Exception):
    """Imita un error de psycopg: el DETAIL trae la fila completa."""

    sqlstate = "23502"


def test_any_exception_still_yields_uniform_500_without_escaping(
    app: FastAPI,
) -> None:
    app.add_api_route("/test/value", _raising(ValueError("bad value")))

    # TestClient por default re-lanza lo que escape de la app: si esto no
    # explota, la excepción no salió y uvicorn no puede volver a loguearla.
    response = TestClient(app).get("/test/value")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_error",
            "message": _text("internal_error"),
            "field": None,
        }
    }


def test_database_error_with_customer_data_is_logged_once_without_it(
    app: FastAPI, log_buffer: Callable[[], io.StringIO]
) -> None:
    error = IntegrityError(
        "INSERT INTO orders (delivery_address) VALUES (%(address)s)",
        {"address": ADDRESS},
        _DriverError(
            f"null value violates constraint\nDETAIL: Failing row contains ({ADDRESS})."
        ),
    )
    app.add_api_route("/test/integrity", _raising(error))
    logs = log_buffer()

    response = TestClient(app).get("/test/integrity")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert ADDRESS not in response.text

    output = logs.getvalue()
    records = [json.loads(line) for line in output.splitlines() if line]
    error_records = [r for r in records if r["level"] == "ERROR"]
    assert len(error_records) == 1
    [record] = error_records
    assert record["message"] == "unhandled error"
    assert record["error_type"] == "IntegrityError"
    assert record["sqlstate"] == "23502"
    assert "File " in record["stack"]
    assert ADDRESS not in output
    assert "Siempreviva" not in output


@pytest.mark.parametrize(
    ("status", "code"),
    [(401, "not_authenticated"), (403, "permission_denied"), (409, "conflict")],
)
def test_framework_auth_and_conflict_errors_use_category_codes(
    app: FastAPI, status: int, code: str
) -> None:
    error = HTTPException(status_code=status, detail="internal detail for devs")
    app.add_api_route("/test/http", _raising(error))

    response = _client(app).get("/test/http")

    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert "internal detail" not in response.text


# --- La cadena de excepciones y las tareas en segundo plano ------------------


def _integrity_error() -> IntegrityError:
    return IntegrityError(
        "INSERT INTO orders (delivery_address) VALUES (%(address)s)",
        {"address": ADDRESS},
        _DriverError(f"DETAIL: Failing row contains ({ADDRESS})."),
    )


def _wrapped_with_cause() -> None:
    try:
        raise _integrity_error()
    except IntegrityError as exc:
        raise RuntimeError("order could not be saved") from exc


def _wrapped_in_context() -> None:
    try:
        raise _integrity_error()
    except IntegrityError:
        raise OutboundHttpError("order could not be saved")  # noqa: B904


def _pending_rollback() -> None:
    raise PendingRollbackError(
        f"This Session's transaction has been rolled back. Original exception "
        f"was: Failing row contains ({ADDRESS})."
    )


def _manual_validation() -> None:
    _Payload.model_validate({"quantity": ADDRESS})


def _assert_logged_once_without_address(logs: io.StringIO) -> dict[str, Any]:
    output = logs.getvalue()
    records = [json.loads(line) for line in output.splitlines() if line]
    error_records = [r for r in records if r["level"] == "ERROR"]
    assert len(error_records) == 1
    assert "Siempreviva" not in output
    return error_records[0]


@pytest.mark.parametrize(
    "endpoint",
    [_wrapped_with_cause, _wrapped_in_context, _pending_rollback, _manual_validation],
    ids=["cause", "context", "pending-rollback", "manual-validation"],
)
def test_customer_data_in_the_exception_chain_never_reaches_the_log(
    app: FastAPI, log_buffer: Callable[[], io.StringIO], endpoint: Callable[[], None]
) -> None:
    app.add_api_route("/test/chain", endpoint)
    logs = log_buffer()

    response = TestClient(app).get("/test/chain")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    record = _assert_logged_once_without_address(logs)
    assert "File " in record["stack"]


def test_background_task_error_is_logged_once_without_customer_data(
    app: FastAPI, log_buffer: Callable[[], io.StringIO]
) -> None:
    def failing_task() -> None:
        raise _integrity_error()

    def endpoint(background_tasks: BackgroundTasks) -> dict[str, str]:
        background_tasks.add_task(failing_task)
        return {"status": "accepted"}

    app.add_api_route("/test/background", endpoint)
    logs = log_buffer()

    # Si la excepción escapara de la app, TestClient la re-lanzaría acá.
    response = TestClient(app).get("/test/background")

    assert response.status_code == 200
    _assert_logged_once_without_address(logs)


def test_response_validation_error_is_logged_without_the_rejected_value(
    app: FastAPI, log_buffer: Callable[[], io.StringIO]
) -> None:
    def endpoint() -> _Payload:
        return {"quantity": ADDRESS}  # type: ignore[return-value]

    app.add_api_route("/test/response", endpoint, response_model=_Payload)
    logs = log_buffer()

    response = TestClient(app).get("/test/response")

    assert response.status_code == 500
    record = _assert_logged_once_without_address(logs)
    assert record["error_type"] == "ResponseValidationError"
    assert record["validation_errors"] == 1


def test_unhandled_error_middleware_is_the_innermost_user_middleware(
    app: FastAPI,
) -> None:
    # `add_middleware` inserta al principio: lo que se agregue después queda
    # por fuera y sus errores no pasan por este middleware (ver design D5).
    assert app.user_middleware[-1].cls is UnhandledErrorMiddleware
