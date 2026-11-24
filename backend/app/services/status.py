"""Status rules, kept in one place (spec section 5).

PO status is *derived* from the vendor acknowledgement, shipments and accepted quantities.
Nothing sets it by hand except cancelling. Every change is written to status_history.
"""
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    POItem,
    POStatus,
    PurchaseOrder,
    Receipt,
    ReceiptItem,
    Shipment,
    ShipmentItem,
    ShipmentStatus,
    StatusHistory,
    User,
)

ZERO = Decimal(0)
CLOSED_PO_STATUSES = (POStatus.DELIVERED, POStatus.CANCELLED)


# --------------------------------------------------------------------------- pure rules (unit tested)
@dataclass(frozen=True)
class ItemProgress:
    ordered: Decimal
    accepted: Decimal


def derive_po_status(
    *,
    cancelled: bool,
    acknowledged: bool,
    items: list[ItemProgress],
    has_shipment_on_the_way: bool,
) -> POStatus:
    """The PO status table agreed in planning:

    Cancelled                                   -> CANCELLED
    every item accepted >= ordered              -> DELIVERED
    some quantity accepted                      -> PARTIALLY_DELIVERED
    a shipment on the way, nothing accepted     -> ON_THE_WAY
    vendor acknowledged                         -> PREPARING
    otherwise                                   -> ISSUED
    """
    if cancelled:
        return POStatus.CANCELLED
    if items and all(i.accepted >= i.ordered for i in items):
        return POStatus.DELIVERED
    if any(i.accepted > 0 for i in items):
        return POStatus.PARTIALLY_DELIVERED
    if has_shipment_on_the_way:
        return POStatus.ON_THE_WAY
    if acknowledged:
        return POStatus.PREPARING
    return POStatus.ISSUED


SHIPMENT_TRANSITIONS: dict[ShipmentStatus, set[ShipmentStatus]] = {
    ShipmentStatus.ON_THE_WAY: {ShipmentStatus.DELIVERED, ShipmentStatus.DISCREPANCY},
    ShipmentStatus.DISCREPANCY: {ShipmentStatus.RESOLVED},
    ShipmentStatus.DELIVERED: set(),
    ShipmentStatus.RESOLVED: set(),
}


def can_change_shipment_status(old: str, new: str) -> bool:
    return ShipmentStatus(new) in SHIPMENT_TRANSITIONS[ShipmentStatus(old)]


def is_po_overdue(status: str, required_date: date | None, today: date) -> bool:
    """PO-level rule: required date has passed and the PO is still open."""
    return required_date is not None and required_date < today and status not in CLOSED_PO_STATUSES


def is_shipment_overdue(status: str, expected_delivery_date: date | None, today: date) -> bool:
    """Shipment-level rule: expected delivery date has passed and it has not been received."""
    return (
        expected_delivery_date is not None
        and expected_delivery_date < today
        and status == ShipmentStatus.ON_THE_WAY
    )


# --------------------------------------------------------------------------- quantities per PO item
@dataclass
class ItemTotals:
    shipped: Decimal = ZERO  # all shipments ever dispatched
    in_transit: Decimal = ZERO  # shipments still ON_THE_WAY
    received: Decimal = ZERO  # physically arrived
    accepted: Decimal = ZERO  # counted toward the PO


def item_totals(db: Session, po_id: int) -> dict[int, ItemTotals]:
    """Shipped / in-transit / received / accepted quantity for every item of a PO."""
    totals: dict[int, ItemTotals] = defaultdict(ItemTotals)

    shipped_rows = db.execute(
        select(ShipmentItem.po_item_id, Shipment.status, func.sum(ShipmentItem.quantity_shipped))
        .join(Shipment, Shipment.id == ShipmentItem.shipment_id)
        .where(Shipment.po_id == po_id)
        .group_by(ShipmentItem.po_item_id, Shipment.status)
    )
    for item_id, status, qty in shipped_rows:
        totals[item_id].shipped += qty
        if status == ShipmentStatus.ON_THE_WAY:
            totals[item_id].in_transit += qty

    received_rows = db.execute(
        select(ReceiptItem.po_item_id, func.sum(ReceiptItem.quantity_received), func.sum(ReceiptItem.quantity_accepted))
        .join(Receipt, Receipt.id == ReceiptItem.receipt_id)
        .join(Shipment, Shipment.id == Receipt.shipment_id)
        .where(Shipment.po_id == po_id)
        .group_by(ReceiptItem.po_item_id)
    )
    for item_id, received, accepted in received_rows:
        totals[item_id].received += received
        totals[item_id].accepted += accepted
    return totals


def outstanding_qty(item: POItem, totals: ItemTotals) -> Decimal:
    """What the vendor may still ship: ordered - accepted - in transit (never below zero)."""
    return max(ZERO, item.quantity_ordered - totals.accepted - totals.in_transit)


# --------------------------------------------------------------------------- writing changes
def record_status(
    db: Session,
    *,
    entity_type: str,
    entity_id: int,
    old: str | None,
    new: str,
    user: User | None,
    note: str | None = None,
) -> None:
    db.add(
        StatusHistory(
            entity_type=entity_type,
            entity_id=entity_id,
            old_status=old,
            new_status=new,
            changed_by=user.id if user else None,
            note=note,
        )
    )


def refresh_po_status(db: Session, po: PurchaseOrder, user: User | None, note: str | None = None) -> bool:
    """Re-derive the PO status from the database and record it if it changed. Returns True on change."""
    db.flush()
    totals = item_totals(db, po.id)
    on_the_way = db.scalar(
        select(func.count()).select_from(Shipment).where(
            Shipment.po_id == po.id, Shipment.status == ShipmentStatus.ON_THE_WAY
        )
    )
    new = derive_po_status(
        cancelled=po.status == POStatus.CANCELLED,
        acknowledged=po.acknowledged_at is not None,
        items=[
            ItemProgress(ordered=i.quantity_ordered, accepted=totals[i.id].accepted if i.id in totals else ZERO)
            for i in po.items
        ],
        has_shipment_on_the_way=bool(on_the_way),
    )
    if new == po.status:
        return False
    record_status(db, entity_type="po", entity_id=po.id, old=po.status, new=new, user=user, note=note)
    po.status = new
    return True
