from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Conversation(Base):
    __tablename__ = "conversations"

    __table_args__ = (
        CheckConstraint(
            """
            active_flow IS NULL
            OR active_flow IN ('ORDER', 'RESERVATION')
            """,
            name="chk_conversation_active_flow",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    customer_id: Mapped[int] = mapped_column(
        ForeignKey(
            "customers.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
    )

    state: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="MAIN_MENU",
    )

    active_flow: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    current_order_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "orders.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    handoff_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    last_interaction: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    customer = relationship(
        "Customer",
        back_populates="conversation",
    )

    current_order = relationship(
        "Order",
    )