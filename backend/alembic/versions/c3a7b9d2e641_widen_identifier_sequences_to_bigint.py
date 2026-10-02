"""widen identifier sequences to bigint

Revision ID: c3a7b9d2e641
Revises: 57f88cf9ee63
Create Date: 2026-10-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3a7b9d2e641"
down_revision: Union[str, Sequence[str], None] = "57f88cf9ee63"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


INTEGER_MIN = -(2**31)
INTEGER_MAX = 2**31 - 1

PRIMARY_KEY_COLUMNS = (
    ("customers", "id"),
    ("menu_items", "id"),
    ("orders", "id"),
    ("order_items", "id"),
    ("reservations", "id"),
    ("conversations", "id"),
)

SEQUENCE_NAMES = (
    "customers_id_seq",
    "menu_items_id_seq",
    "orders_id_seq",
    "order_items_id_seq",
    "reservations_id_seq",
    "conversations_id_seq",
)

BIGINT_SEQUENCE_STATEMENTS = (
    "ALTER SEQUENCE public.customers_id_seq AS BIGINT NO MINVALUE NO MAXVALUE",
    "ALTER SEQUENCE public.menu_items_id_seq AS BIGINT NO MINVALUE NO MAXVALUE",
    "ALTER SEQUENCE public.orders_id_seq AS BIGINT NO MINVALUE NO MAXVALUE",
    "ALTER SEQUENCE public.order_items_id_seq AS BIGINT NO MINVALUE NO MAXVALUE",
    "ALTER SEQUENCE public.reservations_id_seq AS BIGINT NO MINVALUE NO MAXVALUE",
    "ALTER SEQUENCE public.conversations_id_seq AS BIGINT NO MINVALUE NO MAXVALUE",
)

INTEGER_SEQUENCE_STATEMENTS = (
    "ALTER SEQUENCE public.customers_id_seq AS INTEGER NO MINVALUE NO MAXVALUE",
    "ALTER SEQUENCE public.menu_items_id_seq AS INTEGER NO MINVALUE NO MAXVALUE",
    "ALTER SEQUENCE public.orders_id_seq AS INTEGER NO MINVALUE NO MAXVALUE",
    "ALTER SEQUENCE public.order_items_id_seq AS INTEGER NO MINVALUE NO MAXVALUE",
    "ALTER SEQUENCE public.reservations_id_seq AS INTEGER NO MINVALUE NO MAXVALUE",
    "ALTER SEQUENCE public.conversations_id_seq AS INTEGER NO MINVALUE NO MAXVALUE",
)


def _assert_primary_keys_fit_integer() -> None:
    connection = op.get_bind()

    for table_name, column_name in PRIMARY_KEY_COLUMNS:
        identifier_table = sa.table(
            table_name,
            sa.column(column_name, sa.BigInteger()),
        )
        identifier_column = identifier_table.c[column_name]
        minimum, maximum = connection.execute(
            sa.select(
                sa.func.min(identifier_column),
                sa.func.max(identifier_column),
            )
        ).one()

        if (
            (minimum is not None and minimum < INTEGER_MIN)
            or (maximum is not None and maximum > INTEGER_MAX)
        ):
            raise RuntimeError(
                "Cannot downgrade identifier sequences to INTEGER: "
                f"{table_name}.{column_name} contains an out-of-range value."
            )


def _assert_sequences_fit_integer() -> None:
    connection = op.get_bind()

    for sequence_name in SEQUENCE_NAMES:
        sequence_table = sa.table(
            sequence_name,
            sa.column("last_value", sa.BigInteger()),
            schema="public",
        )
        last_value = connection.scalar(sa.select(sequence_table.c.last_value))

        if (
            last_value is not None
            and not INTEGER_MIN <= last_value <= INTEGER_MAX
        ):
            raise RuntimeError(
                "Cannot downgrade identifier sequences to INTEGER: "
                f"{sequence_name} has an out-of-range current value."
            )


def upgrade() -> None:
    """Widen identifier-generating sequences to PostgreSQL BIGINT."""
    for statement in BIGINT_SEQUENCE_STATEMENTS:
        op.execute(sa.text(statement))


def downgrade() -> None:
    """Restore INTEGER sequences only when doing so cannot lose range."""
    _assert_primary_keys_fit_integer()
    _assert_sequences_fit_integer()

    for statement in INTEGER_SEQUENCE_STATEMENTS:
        op.execute(sa.text(statement))
