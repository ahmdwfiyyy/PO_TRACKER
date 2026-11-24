"""Which purchase orders a user may see. Every PO query goes through po_visibility().

- Purchasing: all POs
- Vendor: only POs of their own vendor (history included; it never disappears)
- Receiving: POs that have at least one shipment (incoming or already received)

A PO the user may not see is reported as "not found" (404), so its existence is not leaked.
"""
from sqlalchemy import ColumnElement, false, select, true
from sqlalchemy.orm import Session

from app.models import PurchaseOrder, Role, Shipment, User
from app.services.errors import ServiceError


def po_visibility(user: User) -> ColumnElement[bool]:
    if user.role == Role.PURCHASING:
        return true()
    if user.role == Role.VENDOR:
        return PurchaseOrder.vendor_id == user.vendor_id if user.vendor_id else false()
    if user.role == Role.RECEIVING:
        return select(Shipment.id).where(Shipment.po_id == PurchaseOrder.id).exists()
    return false()


def get_visible_po(db: Session, po_id: int, user: User) -> PurchaseOrder:
    po = db.scalar(select(PurchaseOrder).where(PurchaseOrder.id == po_id, po_visibility(user)))
    if po is None:
        raise ServiceError("Purchase order not found", 404)
    return po
