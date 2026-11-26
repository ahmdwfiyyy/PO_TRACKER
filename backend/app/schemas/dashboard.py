from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints

from app.models import POStatus
from app.schemas.common import ORM, VendorRef
from app.schemas.shipments import DiscrepancyOut


# --------------------------------------------------------------------------- notifications
class NotificationOut(ORM):
    id: int
    type: str
    message: str
    link: str | None
    is_read: bool
    created_at: datetime


class NotificationList(BaseModel):
    items: list[NotificationOut]
    unread: int


# --------------------------------------------------------------------------- discrepancies
class ResolveRequest(BaseModel):
    resolution_note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class DiscrepancyListItem(DiscrepancyOut):
    shipment_no: str
    shipment_status: str
    po_id: int
    po_number: str
    vendor: VendorRef


# --------------------------------------------------------------------------- dashboard
class OverduePO(BaseModel):
    id: int
    po_number: str
    vendor_name: str
    status: POStatus
    required_date: date
    days_late: int


class OverdueShipment(BaseModel):
    id: int
    shipment_no: str
    po_id: int
    po_number: str
    vendor_name: str
    expected_delivery_date: date
    days_late: int


class Activity(BaseModel):
    id: int
    changed_at: datetime
    po_id: int
    po_number: str
    subject: str  # "PO" or the shipment number
    old_status: str | None
    new_status: str
    changed_by_name: str | None
    note: str | None


class DashboardSummary(BaseModel):
    status_counts: dict[str, int]
    open_pos: int
    overdue_pos: int
    in_transit: int
    open_discrepancies: int
    overdue: list[OverduePO]
    overdue_shipments: list[OverdueShipment]
    discrepancies: list[DiscrepancyListItem]
    activity: list[Activity]
