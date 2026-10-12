"""Dos mensajes simultáneos del mismo número nunca crean dos customers (VER-2).

Spec `customer-registry`, requirement "Concurrent requests for the same number
create one customer". Transacciones reales, en conexiones y engines separados,
que commitean de verdad: es el único test que deja filas, y las borra al final.
La garantía sale del índice único de `customers.phone` (design D4).
"""

import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

import pytest
from sqlalchemy import Engine, delete, func, select, text

from app.core.config import load_config
from app.core.database import build_engine, build_session_factory
from app.db.repositories.customers import SqlCustomerRepository
from app.domain.customers.schemas import CustomerRead
from app.models.customer import Customer

WAIT_SECONDS = 10
RACERS = 8


@pytest.fixture
def engines() -> Iterator[tuple[Engine, Engine]]:
    settings = load_config().settings
    first, second = build_engine(settings), build_engine(settings)
    yield first, second
    first.dispose()
    second.dispose()


@pytest.fixture
def committed_phone(phone: str, db_engine: Engine) -> Iterator[str]:
    """Teléfono de un test que commitea: el teardown borra sus filas."""
    yield phone
    with db_engine.begin() as connection:
        connection.execute(delete(Customer).where(Customer.phone == phone))


def _count(engine: Engine, phone: str) -> int:
    with engine.connect() as connection:
        return connection.execute(
            select(func.count()).select_from(Customer).where(Customer.phone == phone)
        ).scalar_one()


@dataclass
class _Request:
    """Un pedido en su propio thread, con su sesión y su transacción."""

    engine: Engine
    phone: str
    before: Callable[[], None] = lambda: None
    pid: int | None = None
    result: CustomerRead | None = None
    error: BaseException | None = None
    started: threading.Event = field(default_factory=threading.Event)
    thread: threading.Thread | None = None

    def start(self) -> None:
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        assert self.started.wait(WAIT_SECONDS), "request thread did not start"

    def join(self) -> CustomerRead:
        assert self.thread is not None
        self.thread.join(WAIT_SECONDS)
        assert not self.thread.is_alive(), "request did not finish in time"
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result

    def _run(self) -> None:
        try:
            with build_session_factory(self.engine)() as session:
                self.pid = session.execute(text("SELECT pg_backend_pid()")).scalar_one()
                self.started.set()
                self.before()
                self.result = SqlCustomerRepository(session).get_or_create(self.phone)
                session.commit()
        except BaseException as error:  # se re-levanta en el thread principal
            self.error = error
            self.started.set()


def _wait_until_blocked_on_a_lock(observer: Engine, pid: int) -> None:
    deadline = time.monotonic() + WAIT_SECONDS
    query = text("SELECT wait_event_type FROM pg_stat_activity WHERE pid = :pid")
    while time.monotonic() < deadline:
        with observer.connect() as connection:
            if connection.execute(query, {"pid": pid}).scalar() == "Lock":
                return
        time.sleep(0.05)
    pytest.fail("the second request never waited on a lock")


def test_second_request_waits_for_the_first_and_returns_its_customer(
    engines: tuple[Engine, Engine], db_engine: Engine, committed_phone: str
) -> None:
    engine_a, engine_b = engines

    with build_session_factory(engine_a)() as session_a:
        created_by_a = SqlCustomerRepository(session_a).get_or_create(committed_phone)

        request_b = _Request(engine_b, committed_phone)
        request_b.start()
        assert request_b.pid is not None
        _wait_until_blocked_on_a_lock(db_engine, request_b.pid)

        # B sigue esperando mientras A no termine.
        assert request_b.thread is not None
        assert request_b.thread.is_alive()
        session_a.commit()

    result_b = request_b.join()
    assert result_b.id == created_by_a.id
    assert _count(db_engine, committed_phone) == 1


def test_first_transaction_rolls_back_and_the_second_creates_the_customer(
    engines: tuple[Engine, Engine], db_engine: Engine, committed_phone: str
) -> None:
    engine_a, engine_b = engines

    with build_session_factory(engine_a)() as session_a:
        created_by_a = SqlCustomerRepository(session_a).get_or_create(committed_phone)

        request_b = _Request(engine_b, committed_phone)
        request_b.start()
        assert request_b.pid is not None
        _wait_until_blocked_on_a_lock(db_engine, request_b.pid)

        session_a.rollback()

    result_b = request_b.join()
    assert result_b.phone == committed_phone
    assert result_b.id != created_by_a.id
    assert _count(db_engine, committed_phone) == 1


def test_simultaneous_first_messages_end_with_one_customer(
    engines: tuple[Engine, Engine], db_engine: Engine, committed_phone: str
) -> None:
    barrier = threading.Barrier(RACERS)
    requests = [
        _Request(engines[index % 2], committed_phone, before=barrier.wait)
        for index in range(RACERS)
    ]

    for request in requests:
        request.start()
    results: list[Any] = [request.join() for request in requests]

    assert len({customer.id for customer in results}) == 1
    assert _count(db_engine, committed_phone) == 1
