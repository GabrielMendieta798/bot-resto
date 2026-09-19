from datetime import date, datetime, time

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Time,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Reservation(Base):
    __tablename__ = "reservations"

    __table_args__ = (
        CheckConstraint(
            "people > 0",
            name="chk_reservation_people",
        ),
        CheckConstraint(
            """
            status IN (
                'REQUESTED',
                'CONFIRMED',
                'REJECTED',
                'CANCELLED'
            )
            """,
            name="chk_reservation_status",
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

    reservation_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    reservation_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
    )

    people: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="REQUESTED",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    customer = relationship(
        "Customer",
        back_populates="reservations",
    )