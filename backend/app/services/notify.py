"""In-app notifications plus a (mocked) email for each, sent to Purchasing and/or the PO's vendor."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Notification, Role, User
from app.services.email import get_email_service


def _send(db: Session, users: list[User], *, type: str, message: str, link: str | None) -> None:
    email = get_email_service()
    url = f"{get_settings().app_url}{link}" if link else get_settings().app_url
    for user in users:
        db.add(Notification(user_id=user.id, type=type, message=message, link=link))
        email.send(
            db,
            to=user.email,
            subject=f"[Carsem PO Tracker] {message}",
            body=f"Hello {user.name},\n\n{message}\n\nOpen: {url}\n\nThis is an automated message from the Carsem PO Tracker.",
        )


def notify_purchasing(db: Session, *, type: str, message: str, link: str | None = None) -> None:
    users = db.scalars(select(User).where(User.role == Role.PURCHASING, User.is_active.is_(True))).all()
    _send(db, list(users), type=type, message=message, link=link)


def notify_vendor(db: Session, vendor_id: int, *, type: str, message: str, link: str | None = None) -> None:
    users = db.scalars(
        select(User).where(User.role == Role.VENDOR, User.vendor_id == vendor_id, User.is_active.is_(True))
    ).all()
    _send(db, list(users), type=type, message=message, link=link)
