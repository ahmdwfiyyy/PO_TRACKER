from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.models import POStatus
from app.schemas.common import OptText, QtyIn, QtyOut, VendorRef
from app.schemas.shipments import ShipmentDetail


# --------------------------------------------------------------------------- input
class POItemIn(BaseModel):
    item_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
    item_code: Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=100)] = None
    quantity_ordered: QtyIn
    unit: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]


class POCreate(BaseModel):
    po_number: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
    vendor_id: int
    issue_date: date
    required_date: date | None = None
    notes: OptText = None
    items: Annotated[list[POItemIn], Field(min_length=1, max_length=200)]


class POUpdate(BaseModel):
    """Send only the fields to change. After the vendor acknowledges, only notes and required_date."""

    po_number: Annotated[str | None, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)] = None
    vendor_id: int | None = None
    issue_date: date | None = None
    required_date: date | None = None
    notes: OptText = None
    items: Annotated[list[POItemIn] | None, Field(min_length=1, max_length=200)] = None


class POCancel(BaseModel):
    reason: OptText = None


# --------------------------------------------------------------------------- output
class POListItem(BaseModel):
    id: int
    po_number: str
    vendor: VendorRef
    status: POStatus
    issue_date: date
    required_date: date | None
    item_count: int
    item_summary: str
    overdue: bool
    has_open_discrepancy: bool
    created_at: datetime
    updated_at: datetime


class POItemOut(BaseModel):
    id: int
    line_no: int
    item_name: str
    item_code: str | None
    quantity_ordered: QtyOut
    unit: str
    vendor_confirmed_name: str | None
    vendor_confirmed_qty: QtyOut | None
    quantity_shipped: QtyOut
    quantity_in_transit: QtyOut
    quantity_received: QtyOut
    quantity_accepted: QtyOut
    quantity_outstanding: QtyOut


class HistoryOut(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    old_status: str | None
    new_status: str
    changed_by_name: str | None
    changed_at: datetime
    note: str | None


class PODetail(BaseModel):
    id: int
    po_number: str
    vendor: VendorRef
    status: POStatus
    issue_date: date
    required_date: date | None
    notes: str | None
    external_ref: str | None
    acknowledged_at: datetime | None
    created_by_name: str | None
    created_at: datetime
    updated_at: datetime
    overdue: bool
    has_open_discrepancy: bool
    locked: bool  # vendor has acknowledged/shipped: only notes and required date are editable
    can_ship: bool  # vendor may dispatch: acknowledged, open, and something left to ship
    items: list[POItemOut]
    shipments: list[ShipmentDetail]
    history: list[HistoryOut]
