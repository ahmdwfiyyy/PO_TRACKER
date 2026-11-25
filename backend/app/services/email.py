"""Outgoing email. Mocked for now: each message is written to the email_log table and the console.

To send real email later, add an SmtpEmailService with the same send() method and return it
from get_email_service(). Nothing else needs to change.
"""
import logging
from typing import Protocol

from sqlalchemy.orm import Session

from app.models import EmailLog

log = logging.getLogger("po_tracker.email")


class EmailService(Protocol):
    def send(self, db: Session, *, to: str, subject: str, body: str) -> None: ...


class MockEmailService:
    def send(self, db: Session, *, to: str, subject: str, body: str) -> None:
        db.add(EmailLog(to_address=to, subject=subject[:300], body=body))
        log.warning("[mock email] to=%s subject=%s", to, subject)


def get_email_service() -> EmailService:
    return MockEmailService()
