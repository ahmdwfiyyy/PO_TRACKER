from fastapi import APIRouter
from sqlalchemy import select

from app.core.config import today
from app.core.deps import DB, CurrentUser, PurchasingUser
from app.models import Discrepancy, DiscrepancyStatus, PurchaseOrder, Shipment
from app.schemas.dashboard import DiscrepancyListItem, ResolveRequest
from app.services.access import po_visibility
from app.services.discrepancies import list_discrepancies, resolve_discrepancy
from app.services.errors import ServiceError

router = APIRouter(prefix="/discrepancies", tags=["discrepancies"])


@router.get("", response_model=list[DiscrepancyListItem])
def get_discrepancies(db: DB, user: CurrentUser, status: DiscrepancyStatus | None = None):
    """Newest first. Scoped like POs (a vendor sees only discrepancies on its own POs)."""
    return list_discrepancies(db, user, status=status, today=today())


@router.post("/{discrepancy_id}/resolve", response_model=DiscrepancyListItem)
def post_resolve(discrepancy_id: int, body: ResolveRequest, db: DB, user: PurchasingUser):
    discrepancy = db.scalar(
        select(Discrepancy)
        .join(Shipment, Shipment.id == Discrepancy.shipment_id)
        .join(PurchaseOrder, PurchaseOrder.id == Shipment.po_id)
        .where(Discrepancy.id == discrepancy_id, po_visibility(user))
    )
    if discrepancy is None:
        raise ServiceError("Discrepancy not found", 404)
    resolve_discrepancy(db, discrepancy, user, body.resolution_note)
    db.commit()
    return list_discrepancies(db, user, status=None, today=today(), only_id=discrepancy_id)[0]
