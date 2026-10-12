"""Integration coverage for the BIGINT identifier Alembic change."""

import pytest
import sqlalchemy as sa
from alembic.config import Config
from sqlalchemy.engine import URL

from alembic import command
from app.core.config import PROJECT_ROOT

INITIAL_REVISION = "7c9704c6ace0"
BIGINT_COLUMN_REVISION = "88d85f44fb7d"
BIGINT_SEQUENCE_REVISION = "c3a7b9d2e641"
INTEGER_MAX = 2**31 - 1

IDENTIFIER_SEQUENCES = (
    "customers_id_seq",
    "menu_items_id_seq",
    "orders_id_seq",
    "order_items_id_seq",
    "reservations_id_seq",
    "conversations_id_seq",
)

IDENTIFIER_COLUMNS = {
    "customers": ("id",),
    "menu_items": ("id",),
    "orders": ("id", "customer_id"),
    "order_items": ("id", "order_id", "menu_item_id"),
    "reservations": ("id", "customer_id"),
    "conversations": ("id", "customer_id", "current_order_id"),
}

EXPECTED_FOREIGN_KEYS = {
    ("orders", ("customer_id",)): ("customers", ("id",), None),
    ("order_items", ("menu_item_id",)): ("menu_items", ("id",), None),
    ("order_items", ("order_id",)): ("orders", ("id",), "CASCADE"),
    ("reservations", ("customer_id",)): ("customers", ("id",), None),
    ("conversations", ("current_order_id",)): (
        "orders",
        ("id",),
        "SET NULL",
    ),
    ("conversations", ("customer_id",)): ("customers", ("id",), "CASCADE"),
}

EXPECTED_INDEXES = {
    ("conversations", "conversations_customer_id_key"): (
        ("customer_id",),
        True,
    ),
    ("customers", "ix_customers_phone"): (("phone",), True),
    ("orders", "ix_orders_customer_id"): (("customer_id",), False),
    ("order_items", "ix_order_items_order_id"): (("order_id",), False),
    ("reservations", "ix_reservations_customer_id"): (("customer_id",), False),
}

EXPECTED_UNIQUE_CONSTRAINTS = {
    ("conversations", ("customer_id",)),
}

EXPECTED_RELATED_IDENTIFIERS = {
    "order_id": 31,
    "order_customer_id": 11,
    "item_order_id": 31,
    "item_menu_item_id": 21,
    "reservation_customer_id": 11,
    "conversation_customer_id": 11,
    "conversation_order_id": 31,
}


def _alembic_config() -> Config:
    config_path = PROJECT_ROOT / "backend" / "alembic.ini"
    return Config(str(config_path))


def _column_types(engine: sa.Engine) -> dict[tuple[str, str], str]:
    inspector = sa.inspect(engine)
    return {
        (table_name, column["name"]): column["type"]
        .compile(dialect=engine.dialect)
        .upper()
        for table_name, column_names in IDENTIFIER_COLUMNS.items()
        for column in inspector.get_columns(table_name)
        if column["name"] in column_names
    }


def _schema_contract(engine: sa.Engine) -> dict[str, object]:
    inspector = sa.inspect(engine)
    primary_keys = {
        table_name: tuple(
            inspector.get_pk_constraint(table_name)["constrained_columns"]
        )
        for table_name in IDENTIFIER_COLUMNS
    }
    foreign_keys = {
        (table_name, tuple(foreign_key["constrained_columns"])): (
            foreign_key["referred_table"],
            tuple(foreign_key["referred_columns"]),
            foreign_key.get("options", {}).get("ondelete"),
        )
        for table_name in IDENTIFIER_COLUMNS
        for foreign_key in inspector.get_foreign_keys(table_name)
    }
    indexes = {
        (table_name, index["name"]): (
            tuple(index["column_names"]),
            index["unique"],
        )
        for table_name in IDENTIFIER_COLUMNS
        for index in inspector.get_indexes(table_name)
    }
    unique_constraints = {
        (table_name, tuple(constraint["column_names"]))
        for table_name in IDENTIFIER_COLUMNS
        for constraint in inspector.get_unique_constraints(table_name)
    }
    return {
        "primary_keys": primary_keys,
        "foreign_keys": foreign_keys,
        "indexes": indexes,
        "unique_constraints": unique_constraints,
    }


def _insert_related_rows(engine: sa.Engine) -> None:
    statements = (
        """
        INSERT INTO customers (id, phone, name)
        VALUES (11, '+5491100000011', 'Migration customer')
        """,
        """
        INSERT INTO menu_items (
            id, category, name, description, price, estimated_time_min, available
        )
        VALUES (21, 'PASTA', 'Ravioles', NULL, 12500.00, 25, TRUE)
        """,
        """
        INSERT INTO orders (
            id, customer_id, status, delivery_type, delivery_address, total
        )
        VALUES (31, 11, 'RECEIVED', 'PICKUP', NULL, 25000.00)
        """,
        """
        INSERT INTO order_items (
            id, order_id, menu_item_id, quantity, unit_price_snapshot, notes
        )
        VALUES (41, 31, 21, 2, 12500.00, 'Migration test')
        """,
        """
        INSERT INTO reservations (
            id, customer_id, reservation_date, reservation_time, people, status
        )
        VALUES (51, 11, DATE '2026-10-12', TIME '21:00', 4, 'REQUESTED')
        """,
        """
        INSERT INTO conversations (
            id, customer_id, state, active_flow, current_order_id, handoff_active
        )
        VALUES (61, 11, 'MAIN_MENU', NULL, 31, FALSE)
        """,
    )
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(sa.text(statement))


def _related_identifiers(engine: sa.Engine) -> dict[str, int]:
    with engine.connect() as connection:
        relationships = (
            connection.execute(
                sa.text(
                    """
                    SELECT
                        orders.id AS order_id,
                        orders.customer_id AS order_customer_id,
                        order_items.order_id AS item_order_id,
                        order_items.menu_item_id AS item_menu_item_id,
                        reservations.customer_id AS reservation_customer_id,
                        conversations.customer_id AS conversation_customer_id,
                        conversations.current_order_id AS conversation_order_id
                    FROM orders
                    JOIN order_items ON order_items.order_id = orders.id
                    JOIN reservations
                        ON reservations.customer_id = orders.customer_id
                    JOIN conversations
                        ON conversations.customer_id = orders.customer_id
                    """
                )
            )
            .mappings()
            .one()
        )
    return dict(relationships)


def _sequence_types(engine: sa.Engine) -> dict[str, str]:
    with engine.connect() as connection:
        return dict(
            connection.execute(
                sa.text(
                    """
                    SELECT sequence_name, data_type
                    FROM information_schema.sequences
                    WHERE sequence_schema = 'public'
                      AND sequence_name IN (
                          'customers_id_seq',
                          'menu_items_id_seq',
                          'orders_id_seq',
                          'order_items_id_seq',
                          'reservations_id_seq',
                          'conversations_id_seq'
                      )
                    """
                )
            ).all()
        )


def _current_revision(engine: sa.Engine) -> str:
    with engine.connect() as connection:
        return connection.execute(
            sa.text("SELECT version_num FROM alembic_version")
        ).scalar_one()


def test_bigint_upgrade_from_initial_schema(
    migration_database_url: URL,
) -> None:
    config = _alembic_config()
    command.upgrade(config, INITIAL_REVISION)

    engine = sa.create_engine(migration_database_url)
    try:
        initial_types = _column_types(engine)
        assert set(initial_types.values()) == {"INTEGER"}
    finally:
        engine.dispose()

    command.upgrade(config, BIGINT_COLUMN_REVISION)

    engine = sa.create_engine(migration_database_url)
    try:
        inspector = sa.inspect(engine)
        upgraded_types = _column_types(engine)

        assert set(upgraded_types) == {
            (table_name, column_name)
            for table_name, column_names in IDENTIFIER_COLUMNS.items()
            for column_name in column_names
        }
        assert set(upgraded_types.values()) == {"BIGINT"}

        for table_name in IDENTIFIER_COLUMNS:
            primary_key = inspector.get_pk_constraint(table_name)
            assert primary_key["constrained_columns"] == ["id"]
    finally:
        engine.dispose()


def test_bigint_upgrade_preserves_related_rows_and_schema_contract(
    migration_database_url: URL,
) -> None:
    config = _alembic_config()
    command.upgrade(config, INITIAL_REVISION)

    engine = sa.create_engine(migration_database_url)
    try:
        initial_contract = _schema_contract(engine)
        assert initial_contract == {
            "primary_keys": {table_name: ("id",) for table_name in IDENTIFIER_COLUMNS},
            "foreign_keys": EXPECTED_FOREIGN_KEYS,
            "indexes": EXPECTED_INDEXES,
            "unique_constraints": EXPECTED_UNIQUE_CONSTRAINTS,
        }
        _insert_related_rows(engine)
    finally:
        engine.dispose()

    command.upgrade(config, BIGINT_COLUMN_REVISION)

    engine = sa.create_engine(migration_database_url)
    try:
        assert _schema_contract(engine) == initial_contract
        assert _related_identifiers(engine) == EXPECTED_RELATED_IDENTIFIERS
    finally:
        engine.dispose()


def test_bigint_sequences_generate_ids_and_foreign_keys_remain_enforced(
    migration_database_url: URL,
) -> None:
    config = _alembic_config()
    command.upgrade(config, BIGINT_SEQUENCE_REVISION)

    engine = sa.create_engine(migration_database_url)
    try:
        assert _sequence_types(engine) == {
            sequence_name: "bigint" for sequence_name in IDENTIFIER_SEQUENCES
        }

        with engine.begin() as connection:
            for sequence_name in IDENTIFIER_SEQUENCES:
                connection.execute(
                    sa.text("SELECT setval(:sequence_name, :value, TRUE)"),
                    {"sequence_name": sequence_name, "value": INTEGER_MAX},
                )

            customer_id = connection.execute(
                sa.text(
                    """
                    INSERT INTO customers (phone, name)
                    VALUES ('+5491100000012', 'Generated customer')
                    RETURNING id
                    """
                )
            ).scalar_one()
            menu_item_id = connection.execute(
                sa.text(
                    """
                    INSERT INTO menu_items (
                        category, name, description, price,
                        estimated_time_min, available
                    )
                    VALUES ('PASTA', 'Sorrentinos', NULL, 15000.00, 30, TRUE)
                    RETURNING id
                    """
                )
            ).scalar_one()
            order_id = connection.execute(
                sa.text(
                    """
                    INSERT INTO orders (
                        customer_id, status, delivery_type,
                        delivery_address, total
                    )
                    VALUES (:customer_id, 'RECEIVED', 'PICKUP', NULL, 15000.00)
                    RETURNING id
                    """
                ),
                {"customer_id": customer_id},
            ).scalar_one()
            order_item_id = connection.execute(
                sa.text(
                    """
                    INSERT INTO order_items (
                        order_id, menu_item_id, quantity,
                        unit_price_snapshot, notes
                    )
                    VALUES (:order_id, :menu_item_id, 1, 15000.00, NULL)
                    RETURNING id
                    """
                ),
                {"order_id": order_id, "menu_item_id": menu_item_id},
            ).scalar_one()
            reservation_id = connection.execute(
                sa.text(
                    """
                    INSERT INTO reservations (
                        customer_id, reservation_date, reservation_time,
                        people, status
                    )
                    VALUES (
                        :customer_id, DATE '2026-10-13', TIME '20:30',
                        2, 'REQUESTED'
                    )
                    RETURNING id
                    """
                ),
                {"customer_id": customer_id},
            ).scalar_one()
            conversation_id = connection.execute(
                sa.text(
                    """
                    INSERT INTO conversations (
                        customer_id, state, active_flow,
                        current_order_id, handoff_active
                    )
                    VALUES (
                        :customer_id, 'MAIN_MENU', NULL,
                        :order_id, FALSE
                    )
                    RETURNING id
                    """
                ),
                {"customer_id": customer_id, "order_id": order_id},
            ).scalar_one()

        assert {
            customer_id,
            menu_item_id,
            order_id,
            order_item_id,
            reservation_id,
            conversation_id,
        } == {INTEGER_MAX + 1}

        with (
            pytest.raises(sa.exc.IntegrityError) as error,
            engine.begin() as connection,
        ):
            connection.execute(
                sa.text(
                    """
                    INSERT INTO orders (
                        id, customer_id, status,
                        delivery_type, delivery_address, total
                    )
                    VALUES (
                        :id, :missing_customer_id, 'RECEIVED',
                        'PICKUP', NULL, 0.00
                    )
                    """
                ),
                {
                    "id": INTEGER_MAX + 2,
                    "missing_customer_id": INTEGER_MAX + 999,
                },
            )

        assert getattr(error.value.orig, "sqlstate", None) == "23503"
    finally:
        engine.dispose()


def test_downgrade_restores_in_range_identifiers_and_relationships(
    migration_database_url: URL,
) -> None:
    config = _alembic_config()
    command.upgrade(config, INITIAL_REVISION)

    engine = sa.create_engine(migration_database_url)
    try:
        initial_contract = _schema_contract(engine)
        _insert_related_rows(engine)
    finally:
        engine.dispose()

    command.upgrade(config, BIGINT_COLUMN_REVISION)
    command.downgrade(config, INITIAL_REVISION)

    engine = sa.create_engine(migration_database_url)
    try:
        assert set(_column_types(engine).values()) == {"INTEGER"}
        assert _schema_contract(engine) == initial_contract
        assert _related_identifiers(engine) == EXPECTED_RELATED_IDENTIFIERS
        assert _current_revision(engine) == INITIAL_REVISION
    finally:
        engine.dispose()


def test_sequence_downgrade_only_restores_identifier_sequences(
    migration_database_url: URL,
) -> None:
    config = _alembic_config()
    command.upgrade(config, BIGINT_SEQUENCE_REVISION)
    command.downgrade(config, "57f88cf9ee63")

    engine = sa.create_engine(migration_database_url)
    try:
        assert _sequence_types(engine) == {
            sequence_name: "integer" for sequence_name in IDENTIFIER_SEQUENCES
        }
        assert set(_column_types(engine).values()) == {"BIGINT"}
        assert sa.inspect(engine).has_table("processed_whatsapp_messages")
        assert _current_revision(engine) == "57f88cf9ee63"
    finally:
        engine.dispose()


def test_column_downgrade_rejects_an_out_of_range_identifier_atomically(
    migration_database_url: URL,
) -> None:
    config = _alembic_config()
    command.upgrade(config, BIGINT_COLUMN_REVISION)

    engine = sa.create_engine(migration_database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    """
                    INSERT INTO customers (id, phone, name)
                    VALUES (:id, '+5491100000013', 'Out-of-range customer')
                    """
                ),
                {"id": INTEGER_MAX + 1},
            )
    finally:
        engine.dispose()

    with pytest.raises(
        RuntimeError,
        match=r"customers\.id contains an out-of-range value",
    ):
        command.downgrade(config, INITIAL_REVISION)

    engine = sa.create_engine(migration_database_url)
    try:
        assert _current_revision(engine) == BIGINT_COLUMN_REVISION
        assert set(_column_types(engine).values()) == {"BIGINT"}
        with engine.connect() as connection:
            assert connection.execute(
                sa.text("SELECT id FROM customers")
            ).scalar_one() == (INTEGER_MAX + 1)
    finally:
        engine.dispose()


def test_sequence_downgrade_rejects_an_out_of_range_value_atomically(
    migration_database_url: URL,
) -> None:
    config = _alembic_config()
    command.upgrade(config, BIGINT_SEQUENCE_REVISION)

    engine = sa.create_engine(migration_database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                sa.text("SELECT setval('customers_id_seq', :value, TRUE)"),
                {"value": INTEGER_MAX + 1},
            )
    finally:
        engine.dispose()

    with pytest.raises(
        RuntimeError,
        match=r"customers_id_seq has an out-of-range current value",
    ):
        command.downgrade(config, "57f88cf9ee63")

    engine = sa.create_engine(migration_database_url)
    try:
        assert _current_revision(engine) == BIGINT_SEQUENCE_REVISION
        assert _sequence_types(engine) == {
            sequence_name: "bigint" for sequence_name in IDENTIFIER_SEQUENCES
        }
    finally:
        engine.dispose()
