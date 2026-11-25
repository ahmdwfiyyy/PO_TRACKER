from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, nulls_last, select

from app.core.config import today
from app.core.deps import DB, CurrentUser, ReceivingUser, require_roles
from app.models import PurchaseOrder, Role, Shipment, ShipmentStatus, User
from app.schemas.common import Page
from app.schemas.shipments import DiscrepancyIn, ReceiveRequest, ShipmentDetail
from app.services.access import get_visible_shipment, po_visibility
from app.services.shipment_views import SHIPMENT_LOAD, build_shipments
from app.services.shipments import declare_discrepancy, receive_shipment

router = APIRouter(prefix="/shipments", tags=["shipments"])

ReceivingOrPurchasing = Annotated[User, Depends(require_roles(Role.RECEIVING, Role.PURCHASING))]


def _detail(db, shipment: Shipment) -> ShipmentDetail:
    db.expire_all()
    fresh = db.scalar(select(Shipment).where(Shipment.id == shipment.id).options(*SHIPMENT_LOAD))
    return build_shipments(db, [fresh], today())[0]


@router.get("", response_model=Page[ShipmentDetail])
def list_shipments(
    db: DB,
    user: CurrentUser,
    status: ShipmentStatus | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
):
    """Scoped like POs. Receiving uses ?status=ON_THE_WAY; soonest expected delivery first."""
    query = select(Shipment).join(PurchaseOrder, PurchaseOrder.id == Shipment.po_id).where(po_visibility(user))
    if status:
        query = query.where(Shipment.status == status)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(
        query.options(*SHIPMENT_LOAD)
        .order_by(nulls_last(Shipment.expected_delivery_date.asc()), Shipment.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return Page(items=build_shipments(db, rows, today()), total=total, page=page, pages=max(1, -(-total // page_size)))


@router.get("/{shipment_id}", response_model=ShipmentDetail)
def get_shipment(shipment_id: int, db: DB, user: CurrentUser):
    return _detail(db, get_visible_shipment(db, shipment_id, user))


@router.post("/{shipment_id}/receive", response_model=ShipmentDetail)
def post_receive(shipment_id: int, body: ReceiveRequest, db: DB, user: ReceivingUser):
    """Record what arrived. If it does not match the shipment, `discrepancies` must be filled in."""
    shipment = get_visible_shipment(db, shipment_id, user)
    receive_shipment(db, shipment, user, body)
    db.commit()
    return _detail(db, shipment)


@router.post("/{shipment_id}/discrepancies", response_model=ShipmentDetail, status_code=201)
def post_discrepancy(shipment_id: int, body: DiscrepancyIn, db: DB, user: ReceivingOrPurchasing):
    """Report a problem found after the shipment was received."""
    shipment = get_visible_shipment(db, shipment_id, user)
    declare_discrepancy(db, shipment, user, body)
    db.commit()
    return _detail(db, shipment)
