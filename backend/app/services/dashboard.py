"""Purchasing dashboard (spec section 9): counts by status, overdue, open discrepancies, recent activity."""
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Discrepancy,
    DiscrepancyStatus,
    POStatus,
    PurchaseOrder,
    Shipment,
    ShipmentStatus,
    StatusHistory,
    User,
    Vendor,
)
from app.schemas.dashboard import Activity, DashboardSummary, OverduePO, OverdueShipment
from app.services.discrepancies import list_discrepancies
from app.services.status import CLOSED_PO_STATUSES

ACTIVITY_LIMIT = 15
LIST_LIMIT = 10


def build_summary(db: Session, user: User, today: date) -> DashboardSummary:
    counts = dict(db.execute(select(PurchaseOrder.status, func.count()).group_by(PurchaseOrder.status)).all())
    status_counts = {s.value: counts.get(s.value, 0) for s in POStatus}

    overdue_rows = db.execute(
        select(PurchaseOrder.id, PurchaseOrder.po_number, Vendor.name, PurchaseOrder.status, PurchaseOrder.required_date)
        .join(Vendor, Vendor.id == PurchaseOrder.vendor_id)
        .where(PurchaseOrder.required_date < today, PurchaseOrder.status.not_in(CLOSED_PO_STATUSES))
        .order_by(PurchaseOrder.required_date)
    ).all()
    late_shipments = db.execute(
        select(Shipment.id, Shipment.shipment_no, Shipment.po_id, PurchaseOrder.po_number, Vendor.name, Shipment.expected_delivery_date)
        .join(PurchaseOrder, PurchaseOrder.id == Shipment.po_id)
        .join(Vendor, Vendor.id == PurchaseOrder.vendor_id)
        .where(Shipment.status == ShipmentStatus.ON_THE_WAY, Shipment.expected_delivery_date < today)
        .order_by(Shipment.expected_delivery_date)
    ).all()

    in_transit = db.scalar(select(func.count()).select_from(Shipment).where(Shipment.status == ShipmentStatus.ON_THE_WAY)) or 0
    open_disc = db.scalar(select(func.count()).select_from(Discrepancy).where(Discrepancy.status == DiscrepancyStatus.OPEN)) or 0

    return DashboardSummary(
        status_counts=status_counts,
        open_pos=sum(n for s, n in status_counts.items() if s not in CLOSED_PO_STATUSES),
        overdue_pos=len(overdue_rows),
        in_transit=in_transit,
        open_discrepancies=open_disc,
        overdue=[
            OverduePO(id=r[0], po_number=r[1], vendor_name=r[2], status=r[3], required_date=r[4], days_late=(today - r[4]).days)
            for r in overdue_rows[:LIST_LIMIT]
        ],
        overdue_shipments=[
            OverdueShipment(id=r[0], shipment_no=r[1], po_id=r[2], po_number=r[3], vendor_name=r[4],
                            expected_delivery_date=r[5], days_late=(today - r[5]).days)
            for r in late_shipments[:LIST_LIMIT]
        ],
        discrepancies=list_discrepancies(db, user, status=DiscrepancyStatus.OPEN, today=today, limit=LIST_LIMIT),
        activity=_activity(db),
    )


def _activity(db: Session) -> list[Activity]:
    rows = db.execute(
        select(StatusHistory, User.name)
        .outerjoin(User, User.id == StatusHistory.changed_by)
        .order_by(StatusHistory.changed_at.desc(), StatusHistory.id.desc())
        .limit(ACTIVITY_LIMIT)
    ).all()
    po_ids = {h.entity_id for h, _ in rows if h.entity_type == "po"}
    shipment_ids = {h.entity_id for h, _ in rows if h.entity_type == "shipment"}
    shipments = {
        sid: (no, po_id)
        for sid, no, po_id in db.execute(
            select(Shipment.id, Shipment.shipment_no, Shipment.po_id).where(Shipment.id.in_(shipment_ids))
        )
    } if shipment_ids else {}
    po_ids |= {po_id for _, po_id in shipments.values()}
    numbers = dict(db.execute(select(PurchaseOrder.id, PurchaseOrder.po_number).where(PurchaseOrder.id.in_(po_ids))).all()) if po_ids else {}

    result = []
    for h, name in rows:
        if h.entity_type == "shipment":
            if h.entity_id not in shipments:
                continue
            subject, po_id = shipments[h.entity_id]
        else:
            subject, po_id = "PO", h.entity_id
        if po_id not in numbers:
            continue
        result.append(
            Activity(
                id=h.id, changed_at=h.changed_at, po_id=po_id, po_number=numbers[po_id], subject=subject,
                old_status=h.old_status, new_status=h.new_status, changed_by_name=name, note=h.note,
            )
        )
    return result
