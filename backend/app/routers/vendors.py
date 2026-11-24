"""Vendor companies (Purchasing only). Vendors are never deleted: their PO history is evidence of delivery."""
from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.deps import DB, PurchasingUser
from app.models import PurchaseOrder, User, Vendor
from app.schemas.users import VendorIn, VendorOut, VendorUpdate
from app.services.status import CLOSED_PO_STATUSES

router = APIRouter(prefix="/vendors", tags=["vendors"])


def _name_taken(db, name: str, exclude_id: int | None = None) -> bool:
    query = select(Vendor.id).where(func.lower(Vendor.name) == name.lower())
    if exclude_id:
        query = query.where(Vendor.id != exclude_id)
    return db.scalar(query) is not None


@router.get("", response_model=list[VendorOut])
def list_vendors(db: DB, _: PurchasingUser):
    users = select(func.count(User.id)).where(User.vendor_id == Vendor.id).scalar_subquery()
    pos = select(func.count(PurchaseOrder.id)).where(PurchaseOrder.vendor_id == Vendor.id).scalar_subquery()
    open_pos = (
        select(func.count(PurchaseOrder.id))
        .where(PurchaseOrder.vendor_id == Vendor.id, PurchaseOrder.status.not_in(CLOSED_PO_STATUSES))
        .scalar_subquery()
    )
    rows = db.execute(select(Vendor, users, pos, open_pos).order_by(Vendor.name))
    result = []
    for vendor, user_count, po_count, open_count in rows:
        out = VendorOut.model_validate(vendor)
        out.user_count, out.po_count, out.open_po_count = user_count, po_count, open_count
        result.append(out)
    return result


@router.post("", response_model=VendorOut, status_code=201)
def create_vendor(body: VendorIn, db: DB, _: PurchasingUser):
    if _name_taken(db, body.name):
        raise HTTPException(status_code=409, detail=f"A vendor named {body.name} already exists")
    vendor = Vendor(**body.model_dump())
    db.add(vendor)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"A vendor named {body.name} already exists")
    return VendorOut.model_validate(vendor)


@router.patch("/{vendor_id}", response_model=VendorOut)
def update_vendor(vendor_id: int, body: VendorUpdate, db: DB, _: PurchasingUser):
    vendor = db.get(Vendor, vendor_id)
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")
    changes = body.model_dump(exclude_unset=True)
    if changes.get("name") and _name_taken(db, changes["name"], exclude_id=vendor.id):
        raise HTTPException(status_code=409, detail=f"A vendor named {changes['name']} already exists")
    if "name" in changes and not changes["name"]:
        changes.pop("name")
    for key, value in changes.items():
        setattr(vendor, key, value)
    db.commit()
    return VendorOut.model_validate(vendor)
