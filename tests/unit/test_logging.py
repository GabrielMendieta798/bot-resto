"""Escenarios de la spec `structured-logging` (SEC-3)."""

import io
import json
import logging
import re
from collections.abc import Iterator

import pytest

from app.core.logging import configure_logging

PHONE = "5491122334455"


@pytest.fixture
def log_output() -> Iterator[io.StringIO]:
    """Instala el logging estructurado sobre un buffer y restaura el root."""
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    buffer = io.StringIO()
    configure_logging("INFO", stream=buffer)
    yield buffer
    root.handlers[:] = saved_handlers
    root.setLevel(saved_level)


def _lines(buffer: io.StringIO) -> list[str]:
    return [line for line in buffer.getvalue().splitlines() if line]


def test_record_is_one_json_line_with_required_fields(log_output: io.StringIO) -> None:
    logging.getLogger("app.test").warning(
        "health check failed", extra={"component": "database"}
    )

    [line] = _lines(log_output)
    record = json.loads(line)
    assert record["level"] == "WARNING"
    assert record["logger"] == "app.test"
    assert record["message"] == "health check failed"
    assert record["component"] == "database"
    assert record["timestamp"].endswith("+00:00")


def test_records_below_configured_level_are_dropped(log_output: io.StringIO) -> None:
    configure_logging("WARNING", stream=log_output)

    logging.getLogger("app.test").info("not written")

    assert _lines(log_output) == []


def test_reconfiguring_does_not_duplicate_handlers(log_output: io.StringIO) -> None:
    configure_logging("INFO", stream=log_output)

    logging.getLogger("app.test").warning("once")

    assert len(_lines(log_output)) == 1


def test_phone_in_message_is_masked(log_output: io.StringIO) -> None:
    logging.getLogger("app.test").info("received from %s", PHONE)

    output = log_output.getvalue()
    assert PHONE not in output
    assert not re.search(r"\d{5,}", output.replace(json.loads(output)["timestamp"], ""))
    assert "4455" in output


def test_formatted_e164_phone_is_masked(log_output: io.StringIO) -> None:
    logging.getLogger("app.test").info("received from +54 9 11 2233-4455")

    message = json.loads(log_output.getvalue())["message"]
    assert "+54 9 11 2233-4455" not in message
    assert PHONE not in re.sub(r"\D", "", message)
    assert message.endswith("4455")


def test_phone_in_structured_field_is_masked(log_output: io.StringIO) -> None:
    logging.getLogger("app.test").info("inbound", extra={"phone": PHONE})

    assert PHONE not in log_output.getvalue()


def test_phone_inside_nested_field_is_masked(log_output: io.StringIO) -> None:
    logging.getLogger("app.test").info(
        "inbound", extra={"context": {"customer": {"phone": int(PHONE)}}}
    )

    assert PHONE not in log_output.getvalue()


def test_phone_inside_exception_is_masked(log_output: io.StringIO) -> None:
    try:
        raise ValueError(f"customer {PHONE} not found")
    except ValueError:
        logging.getLogger("app.test").exception("lookup failed")

    output = log_output.getvalue()
    record = json.loads(output)
    assert "Traceback" in record["exc_info"]
    assert PHONE not in output


def test_short_numbers_are_not_masked(log_output: io.StringIO) -> None:
    logging.getLogger("app.test").info("order 4521 has 3 items")

    assert json.loads(log_output.getvalue())["message"] == "order 4521 has 3 items"


def test_third_party_records_through_root_are_masked(log_output: io.StringIO) -> None:
    logging.getLogger("uvicorn.error").error("client %s disconnected", PHONE)

    assert PHONE not in log_output.getvalue()


def test_phone_as_key_of_structured_field_is_masked(log_output: io.StringIO) -> None:
    logging.getLogger("app.test").info("retries", extra={"retries": {PHONE: 2}})

    assert PHONE not in log_output.getvalue()


def test_phone_as_float_field_is_masked(log_output: io.StringIO) -> None:
    logging.getLogger("app.test").info("inbound", extra={"phone": float(PHONE)})

    assert PHONE not in log_output.getvalue()
