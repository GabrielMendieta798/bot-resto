from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Order(Base):
    __tablename__ = "orders"

    __table_args__ = (
        CheckConstraint(
            """
            status IN (
                'RECEIVED',
                'PREPARING',
                'READY',
                'ON_THE_WAY',
                'DELIVERED',
                'CANCELLED'
            )
            """,
            name="chk_order_status",
        ),
        CheckConstraint(
            "delivery_type IN ('DELIVERY', 'PICKUP')",
            name="chk_order_delivery_type",
        ),
        CheckConstraint(
            "total >= 0",
            name="chk_order_total",
        ),
        CheckConstraint(
            """
            delivery_type <> 'DELIVERY'
            OR delivery_address IS NOT NULL
            """,
            name="chk_order_delivery_address",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id"),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="RECEIVED",
    )

    delivery_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    delivery_address: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    customer = relationship(
        "Customer",
        back_populates="orders",
    )

    items = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
    )

    customer = relationship(
    "Customer",
    back_populates="orders",
    )