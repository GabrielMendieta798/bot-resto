from enum import StrEnum

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.processed_whatsapp_message import ProcessedWhatsAppMessage


class MessageClaimResult(StrEnum):
    CLAIMED = "claimed"
    DUPLICATE = "duplicate"


class WhatsAppMessageIdempotencyRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def claim(self, message_id: str) -> MessageClaimResult:
        statement = (
            insert(ProcessedWhatsAppMessage)
            .values(message_id=message_id)
            .on_conflict_do_nothing(
                index_elements=[ProcessedWhatsAppMessage.message_id]
            )
            .returning(ProcessedWhatsAppMessage.message_id)
        )

        claimed_message_id = self._session.scalar(statement)

        if claimed_message_id is None:
            return MessageClaimResult.DUPLICATE

        return MessageClaimResult.CLAIMED
