"""Listing and resolving discrepancies (spec section 4.6).

Resolving one records a note. When every discrepancy on a shipment is resolved, the shipment
moves DISCREPANCY -> RESOLVED. Quantities are not touched: damaged/short quantity stays
outstanding on the PO, so a replacement is simply a new shipment from the vendor.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.models import Discrepancy, DiscrepancyStatus, PurchaseOrder, Shipment, ShipmentStatus, User
from app.schemas.common import VendorRef
from app.schemas.dashboard import DiscrepancyListItem
from app.services.access import po_visibility
from app.services.errors import ServiceError
from app.services.notify import notify_vendor
from app.services.shipment_views import build_shipments, load_shipments
from app.services.status import can_change_shipment_status, record_status, refresh_po_status


def list_discrepancies(
    db: Session, user: User, *, status: str | None, today, limit: int = 200, only_id: int | None = None
) -> list[DiscrepancyListItem]:
    """Newest first, scoped by PO visibility."""
    query = (
        select(Discrepancy.id, Discrepancy.shipment_id)
        .join(Shipment, Shipment.id == Discrepancy.shipment_id)
        .join(PurchaseOrder, PurchaseOrder.id == Shipment.po_id)
        .where(po_visibility(user))
        .order_by(Discrepancy.created_at.desc(), Discrepancy.id.desc())
        .limit(limit)
    )
    if status:
        query = query.where(Discrepancy.status == status)
    if only_id is not None:
        query = query.where(Discrepancy.id == only_id)
    rows = db.execute(query).all()
    if not rows:
        return []
    shipments = load_shipments(db, Shipment.id.in_({r.shipment_id for r in rows}))
    by_id = {}
    for raw, view in zip(shipments, build_shipments(db, shipments, today)):
        for d in view.discrepancies:
            by_id[d.id] = DiscrepancyListItem(
                **d.model_dump(),
                shipment_no=view.shipment_no,
                shipment_status=view.status,
                po_id=view.po_id,
                po_number=view.po_number,
                vendor=VendorRef(id=raw.po.vendor.id, name=raw.po.vendor.name),
            )
    return [by_id[r.id] for r in rows if r.id in by_id]


def resolve_discrepancy(db: Session, discrepancy: Discrepancy, user: User, note: str) -> Discrepancy:
    if discrepancy.status == DiscrepancyStatus.RESOLVED:
        raise ServiceError("This discrepancy is already resolved", 409)
    discrepancy.status = DiscrepancyStatus.RESOLVED
    discrepancy.resolution_note = note
    discrepancy.resolved_by = user.id
    discrepancy.resolved_at = utcnow()
    db.flush()

    shipment = discrepancy.shipment
    still_open = any(d.status == DiscrepancyStatus.OPEN for d in shipment.discrepancies)
    if not still_open and can_change_shipment_status(shipment.status, ShipmentStatus.RESOLVED):
        record_status(
            db, entity_type="shipment", entity_id=shipment.id, old=shipment.status, new=ShipmentStatus.RESOLVED,
            user=user, note=f"All discrepancies resolved: {note}",
        )
        shipment.status = ShipmentStatus.RESOLVED
    po = shipment.po
    refresh_po_status(db, po, user)

    notify_vendor(
        db, po.vendor_id, type="discrepancy_resolved",
        message=f"{po.po_number}: discrepancy on {shipment.shipment_no} resolved by Carsem. {note}",
        link=f"/pos/{po.id}",
    )
    db.flush()
    return discrepancy
