from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.core.config import today
from app.core.deps import DB, CurrentUser, PurchasingUser
from app.models import POStatus
from app.schemas.common import Page
from app.schemas.pos import POCancel, POCreate, PODetail, POListItem, POUpdate
from app.services.access import get_visible_po
from app.services.po import cancel_po, create_po, list_pos, update_po
from app.services.po_views import build_po_detail, to_list_item

router = APIRouter(prefix="/pos", tags=["purchase orders"])


@router.get("", response_model=Page[POListItem])
def get_pos(
    db: DB,
    user: CurrentUser,
    q: str | None = None,
    status: POStatus | None = None,
    vendor_id: int | None = None,
    overdue: bool | None = None,
    has_discrepancy: bool | None = None,
    state: Literal["open", "closed"] | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    """Role-scoped: Purchasing sees all POs, a vendor only its own, Receiving only POs with shipments."""
    rows, total, pages = list_pos(
        db,
        user,
        today=today(),
        q=q,
        status=status,
        vendor_id=vendor_id,
        overdue=overdue,
        has_discrepancy=has_discrepancy,
        state=state,
        page=page,
        page_size=page_size,
    )
    return Page(items=[to_list_item(*r) for r in rows], total=total, page=page, pages=pages)


@router.post("", response_model=PODetail, status_code=201)
def post_po(body: POCreate, db: DB, user: PurchasingUser):
    po = create_po(
        db,
        po_number=body.po_number,
        vendor_id=body.vendor_id,
        issue_date=body.issue_date,
        required_date=body.required_date,
        notes=body.notes,
        items=body.items,
        created_by=user,
    )
    db.commit()
    return build_po_detail(db, po, today())


@router.get("/{po_id}", response_model=PODetail)
def get_po(po_id: int, db: DB, user: CurrentUser):
    return build_po_detail(db, get_visible_po(db, po_id, user), today())


@router.put("/{po_id}", response_model=PODetail)
def put_po(po_id: int, body: POUpdate, db: DB, user: PurchasingUser):
    po = get_visible_po(db, po_id, user)
    nullable = {"required_date", "notes"}
    changes = {
        k: getattr(body, k) for k in body.model_fields_set if getattr(body, k) is not None or k in nullable
    }
    update_po(db, po, changes, user)
    db.commit()
    return build_po_detail(db, po, today())


@router.post("/{po_id}/cancel", response_model=PODetail)
def post_cancel(po_id: int, body: POCancel, db: DB, user: PurchasingUser):
    po = get_visible_po(db, po_id, user)
    cancel_po(db, po, user, body.reason)
    db.commit()
    return build_po_detail(db, po, today())
