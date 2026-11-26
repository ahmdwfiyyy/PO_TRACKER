from fastapi import APIRouter

from app.core.config import today
from app.core.deps import DB, PurchasingUser
from app.schemas.dashboard import DashboardSummary
from app.services.dashboard import build_summary
from app.services.overdue import check_overdue

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def summary(db: DB, user: PurchasingUser):
    """Also runs the overdue check, so alerts go out even if the background loop is off."""
    check_overdue(db, today())
    db.commit()
    return build_summary(db, user, today())
