"""Each user's own in-app notifications (the bell)."""
from fastapi import APIRouter
from sqlalchemy import func, select, update

from app.core.deps import DB, CurrentUser
from app.models import Notification
from app.schemas.dashboard import NotificationList, NotificationOut
from app.services.errors import ServiceError

router = APIRouter(prefix="/notifications", tags=["notifications"])

LIMIT = 30


@router.get("", response_model=NotificationList)
def list_notifications(db: DB, user: CurrentUser):
    rows = db.scalars(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(LIMIT)
    ).all()
    unread = db.scalar(
        select(func.count()).select_from(Notification).where(Notification.user_id == user.id, Notification.is_read.is_(False))
    )
    return NotificationList(items=[NotificationOut.model_validate(n) for n in rows], unread=unread or 0)


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(notification_id: int, db: DB, user: CurrentUser):
    notification = db.get(Notification, notification_id)
    if notification is None or notification.user_id != user.id:
        raise ServiceError("Notification not found", 404)
    notification.is_read = True
    db.commit()
    return NotificationOut.model_validate(notification)


@router.post("/read-all", status_code=204)
def mark_all_read(db: DB, user: CurrentUser):
    db.execute(
        update(Notification).where(Notification.user_id == user.id, Notification.is_read.is_(False)).values(is_read=True)
    )
    db.commit()
