"""Purchase order logic: create, edit, cancel, list.

create_po() is the single entry point for new POs, so the future ERP importer can call the
same validation and audit logic as the manual form (pass external_ref with the ERP id).
"""
import math
from collections.abc import Sequence
from datetime import date
from typing import Protocol

from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Discrepancy,
    DiscrepancyStatus,
    POItem,
    POStatus,
    PurchaseOrder,
    Shipment,
    ShipmentStatus,
    User,
    Vendor,
)
from app.services.access import po_visibility
from app.services.errors import ServiceError
from app.services.status import CLOSED_PO_STATUSES, record_status


class ItemData(Protocol):
    """Anything with these attributes can become a PO line (the API schema, or an ERP row)."""

    item_name: str
    item_code: str | None
    quantity_ordered: object
    unit: str


# --------------------------------------------------------------------------- create / edit / cancel
def _check_dates(issue_date: date, required_date: date | None) -> None:
    if required_date is not None and required_date < issue_date:
        raise ServiceError("Required date cannot be before the issue date")


def _check_po_number_free(db: Session, po_number: str, exclude_id: int | None = None) -> None:
    query = select(PurchaseOrder.id).where(func.lower(PurchaseOrder.po_number) == po_number.lower())
    if exclude_id is not None:
        query = query.where(PurchaseOrder.id != exclude_id)
    if db.scalar(query) is not None:
        raise ServiceError(f"PO number {po_number} already exists", 409)


def _check_vendor(db: Session, vendor_id: int) -> None:
    if db.get(Vendor, vendor_id) is None:
        raise ServiceError("Vendor not found", 404)


def create_po(
    db: Session,
    *,
    po_number: str,
    vendor_id: int,
    issue_date: date,
    items: Sequence[ItemData],
    required_date: date | None = None,
    notes: str | None = None,
    created_by: User | None = None,
    external_ref: str | None = None,
) -> PurchaseOrder:
    po_number = po_number.strip()
    if not po_number:
        raise ServiceError("PO number is required")
    if not items:
        raise ServiceError("A PO needs at least one line item")
    _check_po_number_free(db, po_number)
    _check_vendor(db, vendor_id)
    _check_dates(issue_date, required_date)
    if external_ref and db.scalar(select(PurchaseOrder.id).where(PurchaseOrder.external_ref == external_ref)):
        raise ServiceError(f"A PO with ERP reference {external_ref} already exists", 409)

    po = PurchaseOrder(
        po_number=po_number,
        vendor_id=vendor_id,
        status=POStatus.ISSUED,
        issue_date=issue_date,
        required_date=required_date,
        notes=notes,
        external_ref=external_ref,
        created_by=created_by.id if created_by else None,
        items=[
            POItem(
                line_no=n,
                item_name=i.item_name.strip(),
                item_code=(i.item_code or "").strip() or None,
                quantity_ordered=i.quantity_ordered,
                unit=i.unit.strip(),
            )
            for n, i in enumerate(items, start=1)
        ],
    )
    db.add(po)
    db.flush()
    record_status(db, entity_type="po", entity_id=po.id, old=None, new=POStatus.ISSUED, user=created_by, note="PO created")
    return po


def is_locked(po: PurchaseOrder) -> bool:
    """Once the vendor has acknowledged or shipped, only notes and dates may change."""
    return po.acknowledged_at is not None or bool(po.shipments)


LOCKED_FIELDS = {"po_number", "vendor_id", "issue_date", "items"}


def update_po(db: Session, po: PurchaseOrder, changes: dict, user: User) -> PurchaseOrder:
    """`changes` holds only the fields the caller sent (e.g. model_dump(exclude_unset=True))."""
    if po.status in CLOSED_PO_STATUSES:
        raise ServiceError(f"A {po.status.lower()} PO can no longer be edited", 409)
    if is_locked(po) and LOCKED_FIELDS & changes.keys():
        raise ServiceError(
            "The vendor has already acknowledged this PO, so only the notes and required date can be changed", 409
        )

    if "po_number" in changes:
        number = changes["po_number"].strip()
        if not number:
            raise ServiceError("PO number is required")
        _check_po_number_free(db, number, exclude_id=po.id)
        po.po_number = number
    if "vendor_id" in changes:
        _check_vendor(db, changes["vendor_id"])
        po.vendor_id = changes["vendor_id"]
    if "issue_date" in changes:
        po.issue_date = changes["issue_date"]
    if "required_date" in changes:
        po.required_date = changes["required_date"]
    if "notes" in changes:
        po.notes = changes["notes"]
    _check_dates(po.issue_date, po.required_date)

    if "items" in changes:
        new_items = changes["items"]
        if not new_items:
            raise ServiceError("A PO needs at least one line item")
        existing = list(po.items)
        # Update in place by position (keeps line numbers stable), then add or remove the rest
        for n, data in enumerate(new_items, start=1):
            item = existing[n - 1] if n <= len(existing) else POItem(line_no=n)
            item.item_name = data.item_name.strip()
            item.item_code = (data.item_code or "").strip() or None
            item.quantity_ordered = data.quantity_ordered
            item.unit = data.unit.strip()
            if n > len(existing):
                po.items.append(item)
        for extra in existing[len(new_items):]:
            po.items.remove(extra)

    db.flush()
    return po


def cancel_po(db: Session, po: PurchaseOrder, user: User, reason: str | None) -> PurchaseOrder:
    if po.status == POStatus.CANCELLED:
        raise ServiceError("This PO is already cancelled", 409)
    if po.status == POStatus.DELIVERED:
        raise ServiceError("A delivered PO cannot be cancelled", 409)
    record_status(db, entity_type="po", entity_id=po.id, old=po.status, new=POStatus.CANCELLED, user=user, note=reason)
    po.status = POStatus.CANCELLED
    db.flush()
    return po


# --------------------------------------------------------------------------- flags (as SQL, so they can be filtered)
def overdue_expr(today: date) -> ColumnElement[bool]:
    """Open PO whose required date has passed, or with a shipment past its expected delivery date."""
    late_shipment = (
        select(Shipment.id)
        .where(
            Shipment.po_id == PurchaseOrder.id,
            Shipment.status == ShipmentStatus.ON_THE_WAY,
            Shipment.expected_delivery_date < today,
        )
        .exists()
    )
    return and_(
        PurchaseOrder.status.not_in(CLOSED_PO_STATUSES),
        or_(PurchaseOrder.required_date < today, late_shipment),
    )


def open_discrepancy_expr() -> ColumnElement[bool]:
    return (
        select(Discrepancy.id)
        .join(Shipment, Shipment.id == Discrepancy.shipment_id)
        .where(Shipment.po_id == PurchaseOrder.id, Discrepancy.status == DiscrepancyStatus.OPEN)
        .exists()
    )


# --------------------------------------------------------------------------- list / search
def list_pos(
    db: Session,
    user: User,
    *,
    today: date,
    q: str | None = None,
    status: str | None = None,
    vendor_id: int | None = None,
    overdue: bool | None = None,
    has_discrepancy: bool | None = None,
    state: str | None = None,  # "open" or "closed" (delivered/cancelled)
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[tuple[PurchaseOrder, bool, bool]], int, int]:
    """Returns ([(po, is_overdue, has_open_discrepancy)], total, pages)."""
    is_overdue = overdue_expr(today)
    has_disc = open_discrepancy_expr()
    conditions: list[ColumnElement[bool]] = [po_visibility(user)]

    if q and q.strip():
        term = f"%{q.strip()}%"
        item_match = (
            select(POItem.id)
            .where(POItem.po_id == PurchaseOrder.id, or_(POItem.item_name.ilike(term), POItem.item_code.ilike(term)))
            .exists()
        )
        conditions.append(or_(PurchaseOrder.po_number.ilike(term), Vendor.name.ilike(term), item_match))
    if status:
        conditions.append(PurchaseOrder.status == status)
    if vendor_id:
        conditions.append(PurchaseOrder.vendor_id == vendor_id)
    if overdue is not None:
        conditions.append(is_overdue if overdue else ~is_overdue)
    if has_discrepancy is not None:
        conditions.append(has_disc if has_discrepancy else ~has_disc)
    if state == "open":
        conditions.append(PurchaseOrder.status.not_in(CLOSED_PO_STATUSES))
    elif state == "closed":
        conditions.append(PurchaseOrder.status.in_(CLOSED_PO_STATUSES))

    base = select(PurchaseOrder).join(Vendor, Vendor.id == PurchaseOrder.vendor_id).where(*conditions)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    pages = max(1, math.ceil(total / page_size))

    rows = db.execute(
        base.add_columns(is_overdue.label("overdue"), has_disc.label("has_disc"))
        .options(selectinload(PurchaseOrder.vendor), selectinload(PurchaseOrder.items))
        .order_by(PurchaseOrder.created_at.desc(), PurchaseOrder.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return [(po, bool(o), bool(d)) for po, o, d in rows], total, pages
