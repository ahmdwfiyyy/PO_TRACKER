"""The core delivery flow (spec section 4):

vendor acknowledges -> vendor dispatches shipments (full or partial) -> Receiving records what arrived
-> matches: shipment DELIVERED / doesn't match: shipment DISCREPANCY, Purchasing alerted.

PO status is never set here: every step ends with status.refresh_po_status().
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.models import (
    Discrepancy,
    DiscrepancyType,
    POStatus,
    PurchaseOrder,
    Receipt,
    ReceiptItem,
    Shipment,
    ShipmentItem,
    ShipmentStatus,
    User,
)
from app.schemas.shipments import AcknowledgeRequest, DiscrepancyIn, ReceiveRequest, ShipmentCreate
from app.services.errors import ServiceError
from app.services.notify import notify_purchasing, notify_vendor
from app.services.status import (
    ZERO,
    ItemTotals,
    can_change_shipment_status,
    item_totals,
    outstanding_qty,
    record_status,
    refresh_po_status,
)


def norm(text: str | None) -> str:
    """Compare names ignoring case and extra spaces."""
    return " ".join((text or "").lower().split())


def _fmt(q: Decimal) -> str:
    return f"{q.normalize():f}"


def _po_link(po: PurchaseOrder) -> str:
    return f"/pos/{po.id}"


# --------------------------------------------------------------------------- vendor: acknowledge
def acknowledge_po(db: Session, po: PurchaseOrder, user: User, body: AcknowledgeRequest) -> int:
    """Vendor confirms item names/quantities. Returns how many lines differ from the PO."""
    if po.status == POStatus.CANCELLED:
        raise ServiceError("This PO has been cancelled", 409)
    if po.acknowledged_at is not None:
        raise ServiceError("This PO has already been acknowledged", 409)

    items = {i.id: i for i in po.items}
    confirmations = {}
    for c in body.items:
        if c.po_item_id not in items:
            raise ServiceError("One of the items does not belong to this PO")
        confirmations[c.po_item_id] = c

    differences = 0
    for item in po.items:
        c = confirmations.get(item.id)
        name = (c.confirmed_name if c and c.confirmed_name else item.item_name).strip()
        qty = c.confirmed_qty if c and c.confirmed_qty is not None else item.quantity_ordered
        item.vendor_confirmed_name = name
        item.vendor_confirmed_qty = qty
        if norm(name) != norm(item.item_name) or qty != item.quantity_ordered:
            differences += 1

    po.acknowledged_at = utcnow()
    po.acknowledged_by = user.id
    note = "Vendor acknowledged the PO"
    if differences:
        note += f" with {differences} difference(s) from the PO"
    if body.note:
        note += f": {body.note}"
    refresh_po_status(db, po, user, note=note)

    if differences:
        notify_purchasing(
            db,
            type="po_acknowledged_with_changes",
            message=f"{po.po_number}: {po.vendor.name} confirmed with {differences} difference(s) in item names or quantities. Please review.",
            link=_po_link(po),
        )
    else:
        notify_purchasing(
            db,
            type="po_acknowledged",
            message=f"{po.po_number}: {po.vendor.name} acknowledged the PO and is preparing it.",
            link=_po_link(po),
        )
    db.flush()
    return differences


# --------------------------------------------------------------------------- vendor: dispatch
def create_shipment(db: Session, po: PurchaseOrder, user: User, body: ShipmentCreate, today: date) -> Shipment:
    if po.status in (POStatus.CANCELLED, POStatus.DELIVERED):
        raise ServiceError(f"A {po.status.lower()} PO cannot be shipped", 409)
    if po.acknowledged_at is None:
        raise ServiceError("Acknowledge the PO before dispatching goods", 409)
    if body.expected_delivery_date < today:
        raise ServiceError("The expected delivery date cannot be in the past")

    items = {i.id: i for i in po.items}
    ids = [line.po_item_id for line in body.items]
    if len(ids) != len(set(ids)):
        raise ServiceError("Each item can only appear once in a shipment")
    totals = item_totals(db, po.id)

    shipping: dict[int, Decimal] = {}
    for line in body.items:
        item = items.get(line.po_item_id)
        if item is None:
            raise ServiceError("One of the items does not belong to this PO")
        left = outstanding_qty(item, totals.get(item.id, ItemTotals()))
        if line.quantity > left:
            raise ServiceError(
                f"Line {item.line_no} ({item.item_name}): only {_fmt(left)} {item.unit} left to ship"
            )
        shipping[item.id] = line.quantity

    # Partial when something is still left to ship after this one
    is_partial = any(
        outstanding_qty(item, totals.get(item.id, ItemTotals())) - shipping.get(item.id, ZERO) > 0
        for item in po.items
    )
    count = db.scalar(select(func.count()).select_from(Shipment).where(Shipment.po_id == po.id)) or 0
    shipment = Shipment(
        po_id=po.id,
        shipment_no=f"{po.po_number}-S{count + 1}",
        is_partial=is_partial,
        courier=body.courier,
        tracking_number=body.tracking_number or None,
        expected_delivery_date=body.expected_delivery_date,
        status=ShipmentStatus.ON_THE_WAY,
        created_by=user.id,
        items=[ShipmentItem(po_item_id=i, quantity_shipped=q) for i, q in shipping.items()],
    )
    db.add(shipment)
    db.flush()
    record_status(
        db, entity_type="shipment", entity_id=shipment.id, old=None, new=ShipmentStatus.ON_THE_WAY, user=user,
        note=f"{shipment.shipment_no} dispatched{' (partial delivery)' if is_partial else ''} via {body.courier}",
    )
    refresh_po_status(db, po, user, note=f"Shipment {shipment.shipment_no} dispatched")
    notify_purchasing(
        db,
        type="shipment_dispatched",
        message=(
            f"{po.po_number}: {po.vendor.name} dispatched {shipment.shipment_no}"
            f"{' (partial)' if is_partial else ''}, expected {body.expected_delivery_date:%d %b %Y}."
        ),
        link=_po_link(po),
    )
    db.flush()
    return shipment


# --------------------------------------------------------------------------- receiving
@dataclass
class Line:
    """One shipment line as keyed in by Receiving, ready to compare."""

    po_item_id: int
    label: str  # "Line 1 (Gloves)"
    unit: str
    shipped: Decimal
    received: Decimal
    accepted: Decimal
    entered_name: str
    expected_names: tuple[str, ...]  # PO name and the vendor's confirmed name


def find_mismatches(lines: list[Line]) -> list[tuple[int, DiscrepancyType, str]]:
    """Compare what arrived with what was shipped. Pure function (unit tested)."""
    found: list[tuple[int, DiscrepancyType, str]] = []
    for line in lines:
        if norm(line.entered_name) not in {norm(n) for n in line.expected_names if n}:
            found.append((line.po_item_id, DiscrepancyType.WRONG_ITEM, f"{line.label}: received \"{line.entered_name}\""))
        if line.received < line.shipped:
            found.append((line.po_item_id, DiscrepancyType.SHORT, f"{line.label}: {_fmt(line.shipped - line.received)} {line.unit} short"))
        elif line.received > line.shipped:
            found.append((line.po_item_id, DiscrepancyType.EXCESS, f"{line.label}: {_fmt(line.received - line.shipped)} {line.unit} extra"))
        if line.accepted < line.received:
            found.append((line.po_item_id, DiscrepancyType.DAMAGED, f"{line.label}: {_fmt(line.received - line.accepted)} {line.unit} not accepted"))
    return found


def _check_transition(shipment: Shipment, new: ShipmentStatus) -> None:
    if not can_change_shipment_status(shipment.status, new):
        raise ServiceError(f"This shipment is already {shipment.status.lower().replace('_', ' ')}", 409)


def _add_discrepancies(
    db: Session, shipment: Shipment, user: User, items: dict[int, object], body: list[DiscrepancyIn], receipt_id: int | None
) -> list[Discrepancy]:
    created = []
    for d in body:
        if d.po_item_id is not None and d.po_item_id not in items:
            raise ServiceError("A discrepancy refers to an item that is not in this shipment")
        discrepancy = Discrepancy(
            shipment_id=shipment.id,
            receipt_id=receipt_id,
            po_item_id=d.po_item_id,
            type=d.type,
            description=d.description,
            reported_by=user.id,
        )
        db.add(discrepancy)
        created.append(discrepancy)
    db.flush()
    return created


def receive_shipment(db: Session, shipment: Shipment, user: User, body: ReceiveRequest) -> Shipment:
    _check_transition(shipment, ShipmentStatus.DELIVERED)
    po = shipment.po
    if po.status == POStatus.CANCELLED:
        raise ServiceError("This PO has been cancelled; contact Purchasing before receiving", 409)

    shipped = {si.po_item_id: si for si in shipment.items}
    entered = {}
    for line in body.items:
        if line.po_item_id not in shipped:
            raise ServiceError("One of the items is not part of this shipment")
        if line.po_item_id in entered:
            raise ServiceError("Each shipment line can only be entered once")
        if line.quantity_accepted > line.quantity_received:
            raise ServiceError("Accepted quantity cannot be more than the quantity received")
        entered[line.po_item_id] = line
    missing = set(shipped) - set(entered)
    if missing:
        raise ServiceError("Enter the received quantity for every line in the shipment (use 0 if it did not arrive)")

    lines = []
    for item_id, si in shipped.items():
        e, item = entered[item_id], si.po_item
        lines.append(
            Line(
                po_item_id=item_id,
                label=f"Line {item.line_no} ({item.item_name})",
                unit=item.unit,
                shipped=si.quantity_shipped,
                received=e.quantity_received,
                accepted=e.quantity_accepted,
                entered_name=e.item_name_entered,
                expected_names=(item.item_name, item.vendor_confirmed_name or ""),
            )
        )
    mismatches = find_mismatches(lines)
    if mismatches and not body.discrepancies:
        details = "; ".join(m[2] for m in mismatches)
        raise ServiceError(f"The goods do not match the shipment ({details}). Declare a discrepancy to continue.", 422)

    receipt = Receipt(
        shipment_id=shipment.id,
        received_by=user.id,
        notes=body.notes,
        items=[
            ReceiptItem(
                po_item_id=e.po_item_id,
                item_name_entered=e.item_name_entered,
                quantity_received=e.quantity_received,
                quantity_accepted=e.quantity_accepted,
            )
            for e in entered.values()
        ],
    )
    db.add(receipt)
    db.flush()
    created = _add_discrepancies(db, shipment, user, shipped, body.discrepancies, receipt.id)

    new_status = ShipmentStatus.DISCREPANCY if created else ShipmentStatus.DELIVERED
    record_status(
        db, entity_type="shipment", entity_id=shipment.id, old=shipment.status, new=new_status, user=user,
        note=(
            f"Received with {len(created)} discrepancy(ies): " + ", ".join(d.type.replace("_", " ").lower() for d in created)
            if created else "Received in full, matches the shipment"
        ),
    )
    shipment.status = new_status
    refresh_po_status(db, po, user, note=f"Shipment {shipment.shipment_no} received")

    link = _po_link(po)
    if created:
        message = f"{po.po_number}: discrepancy declared on {shipment.shipment_no} ({', '.join(d.type for d in created)})."
        notify_purchasing(db, type="discrepancy_declared", message=message, link=link)
        notify_vendor(db, po.vendor_id, type="discrepancy_declared", message=message, link=link)
    if po.status == POStatus.DELIVERED:
        message = f"{po.po_number}: all items received. The PO is now fully delivered."
        notify_purchasing(db, type="po_delivered", message=message, link=link)
        notify_vendor(db, po.vendor_id, type="po_delivered", message=message, link=link)
    elif not created:
        kind = "partial delivery" if po.status == POStatus.PARTIALLY_DELIVERED else "delivery"
        message = f"{po.po_number}: {kind} {shipment.shipment_no} received in full."
        notify_purchasing(db, type="shipment_delivered", message=message, link=link)
        notify_vendor(db, po.vendor_id, type="shipment_delivered", message=message, link=link)
    db.flush()
    return shipment


def declare_discrepancy(db: Session, shipment: Shipment, user: User, body: DiscrepancyIn) -> Discrepancy:
    """Report a problem on a shipment that was already received (e.g. damage found after unpacking)."""
    if shipment.status == ShipmentStatus.ON_THE_WAY:
        raise ServiceError("Receive the shipment first; discrepancies are declared on the receive form", 409)
    shipped = {si.po_item_id: si for si in shipment.items}
    (discrepancy,) = _add_discrepancies(db, shipment, user, shipped, [body], None)
    if shipment.status != ShipmentStatus.DISCREPANCY:
        _check_transition(shipment, ShipmentStatus.DISCREPANCY)
        record_status(
            db, entity_type="shipment", entity_id=shipment.id, old=shipment.status, new=ShipmentStatus.DISCREPANCY,
            user=user, note=f"Discrepancy reported: {body.type.replace('_', ' ').lower()}",
        )
        shipment.status = ShipmentStatus.DISCREPANCY
    po = shipment.po
    message = f"{po.po_number}: discrepancy declared on {shipment.shipment_no} ({body.type})."
    notify_purchasing(db, type="discrepancy_declared", message=message, link=_po_link(po))
    notify_vendor(db, po.vendor_id, type="discrepancy_declared", message=message, link=_po_link(po))
    db.flush()
    return discrepancy
