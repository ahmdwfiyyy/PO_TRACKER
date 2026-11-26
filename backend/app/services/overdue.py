"""Overdue alerts (spec section 7.3, rules in CLAUDE.md decision 5).

check_overdue() is cheap and safe to call often: it runs on dashboard load and from a background
loop (app.main). Each PO/shipment is alerted once; the mark is cleared when it stops being overdue
(e.g. Purchasing moves the required date), so it can alert again if it becomes late again.
"""
import logging
from datetime import date

from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session, selectinload

from app.db import SessionLocal, utcnow
from app.models import PurchaseOrder, Shipment, ShipmentStatus
from app.services.notify import notify_purchasing, notify_vendor
from app.services.status import CLOSED_PO_STATUSES

log = logging.getLogger("po_tracker.overdue")


def check_overdue(db: Session, today: date) -> tuple[int, int]:
    """Send any new overdue alerts. Returns (PO alerts sent, shipment alerts sent). Caller commits."""
    po_late = and_(PurchaseOrder.required_date < today, PurchaseOrder.status.not_in(CLOSED_PO_STATUSES))
    shipment_late = and_(Shipment.expected_delivery_date < today, Shipment.status == ShipmentStatus.ON_THE_WAY)

    # Re-arm anything that is no longer overdue
    db.execute(
        update(PurchaseOrder)
        # (a NULL required date never compares, so it is checked explicitly)
        .where(PurchaseOrder.overdue_notified_at.is_not(None), or_(PurchaseOrder.required_date.is_(None), ~po_late))
        .values(overdue_notified_at=None)
        .execution_options(synchronize_session=False)
    )
    db.execute(
        update(Shipment)
        .where(Shipment.overdue_notified_at.is_not(None), Shipment.status == ShipmentStatus.ON_THE_WAY, ~shipment_late)
        .values(overdue_notified_at=None)
        .execution_options(synchronize_session=False)
    )

    pos = db.scalars(
        select(PurchaseOrder)
        .where(po_late, PurchaseOrder.overdue_notified_at.is_(None))
        .options(selectinload(PurchaseOrder.vendor))
        .with_for_update(skip_locked=True)
    ).all()
    for po in pos:
        days = (today - po.required_date).days
        message = (
            f"{po.po_number} is overdue: required by {po.required_date:%d %b %Y} "
            f"({days} day{'s' if days != 1 else ''} late), still {po.status.replace('_', ' ').lower()}."
        )
        link = f"/pos/{po.id}"
        notify_purchasing(db, type="po_overdue", message=message, link=link)
        notify_vendor(db, po.vendor_id, type="po_overdue", message=message, link=link)
        po.overdue_notified_at = utcnow()

    shipments = db.scalars(
        select(Shipment)
        .where(shipment_late, Shipment.overdue_notified_at.is_(None))
        .options(selectinload(Shipment.po).selectinload(PurchaseOrder.vendor))
        .with_for_update(of=Shipment, skip_locked=True)
    ).all()
    for s in shipments:
        days = (today - s.expected_delivery_date).days
        message = (
            f"{s.po.po_number}: shipment {s.shipment_no} was expected {s.expected_delivery_date:%d %b %Y} "
            f"and has not been received ({days} day{'s' if days != 1 else ''} late)."
        )
        link = f"/pos/{s.po_id}"
        notify_purchasing(db, type="shipment_overdue", message=message, link=link)
        notify_vendor(db, s.po.vendor_id, type="shipment_overdue", message=message, link=link)
        s.overdue_notified_at = utcnow()

    db.flush()
    return len(pos), len(shipments)


def run_overdue_check(today: date) -> None:
    """Entry point for the background loop: own session, own commit, never raises."""
    db = SessionLocal()
    try:
        sent = check_overdue(db, today)
        db.commit()
        if any(sent):
            log.warning("Overdue check: %s PO alert(s), %s shipment alert(s)", *sent)
    except Exception:  # keep the loop alive; the next run tries again
        db.rollback()
        log.exception("Overdue check failed")
    finally:
        db.close()
