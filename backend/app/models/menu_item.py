from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MenuItem(Base):
    __tablename__ = "menu_items"

    __table_args__ = (
        CheckConstraint(
            "price >= 0",
            name="chk_menu_item_price",
        ),
        CheckConstraint(
            "estimated_time_min IS NULL OR estimated_time_min >= 0",
            name="chk_menu_item_estimated_time",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    estimated_time_min: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    available: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )