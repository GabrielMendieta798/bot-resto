from datetime import datetime

from sqlalchemy import DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ProcessedWhatsAppMessage(Base):
    __tablename__ = "processed_whatsapp_messages"

    message_id: Mapped[str] = mapped_column(
        Text,
        primary_key=True,
    )

    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
