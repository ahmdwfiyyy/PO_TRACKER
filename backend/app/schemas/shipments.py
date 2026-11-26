from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.models import DiscrepancyType
from app.schemas.common import ORM, OptText, QtyIn, QtyNonNeg, QtyOut, VendorRef

ShortText = Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=100)]


# --------------------------------------------------------------------------- input: vendor
class AcknowledgeItem(BaseModel):
    po_item_id: int
    confirmed_name: Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=300)] = None
    confirmed_qty: QtyIn | None = None


class AcknowledgeRequest(BaseModel):
    """Items left out are confirmed exactly as ordered."""

    items: list[AcknowledgeItem] = []
    note: OptText = None


class ShipmentItemIn(BaseModel):
    po_item_id: int
    quantity: QtyIn


class ShipmentCreate(BaseModel):
    courier: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    tracking_number: ShortText = None
    expected_delivery_date: date
    items: Annotated[list[ShipmentItemIn], Field(min_length=1)]


# --------------------------------------------------------------------------- input: receiving
class DiscrepancyIn(BaseModel):
    po_item_id: int | None = None
    type: DiscrepancyType
    description: OptText = None


class ReceiveItemIn(BaseModel):
    po_item_id: int
    item_name_entered: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
    quantity_received: QtyNonNeg
    quantity_accepted: QtyNonNeg


class ReceiveRequest(BaseModel):
    items: Annotated[list[ReceiveItemIn], Field(min_length=1)]
    notes: OptText = None
    # Required when the goods do not match the shipment
    discrepancies: list[DiscrepancyIn] = []


# --------------------------------------------------------------------------- output
class AttachmentOut(ORM):
    id: int
    entity_type: str
    entity_id: int
    filename: str
    mime_type: str
    size: int
    uploaded_by_name: str | None = None
    uploaded_at: datetime


class ReceiptItemOut(BaseModel):
    po_item_id: int
    item_name_entered: str
    quantity_received: QtyOut
    quantity_accepted: QtyOut


class ReceiptOut(BaseModel):
    id: int
    received_by_name: str | None
    received_at: datetime
    notes: str | None
    items: list[ReceiptItemOut]
    attachments: list[AttachmentOut]


class DiscrepancyOut(BaseModel):
    id: int
    shipment_id: int
    po_item_id: int | None
    item_name: str | None
    type: DiscrepancyType
    description: str | None
    status: str
    reported_by_name: str | None
    created_at: datetime
    resolution_note: str | None
    resolved_by_name: str | None
    resolved_at: datetime | None
    attachments: list[AttachmentOut]


class ShipmentItemOut(BaseModel):
    po_item_id: int
    line_no: int
    item_name: str
    item_code: str | None
    vendor_confirmed_name: str | None
    unit: str
    quantity_shipped: QtyOut


class Mismatch(BaseModel):
    po_item_id: int
    kind: DiscrepancyType
    message: str


class ShipmentDetail(BaseModel):
    id: int
    shipment_no: str
    po_id: int
    po_number: str
    vendor: VendorRef
    is_partial: bool
    courier: str | None
    tracking_number: str | None
    expected_delivery_date: date | None
    dispatched_at: datetime
    created_by_name: str | None
    status: str
    overdue: bool
    items: list[ShipmentItemOut]
    receipt: ReceiptOut | None
    discrepancies: list[DiscrepancyOut]
    attachments: list[AttachmentOut]
