"""Turn shipments (with their receipt, discrepancies and files) into API responses."""
from collections import defaultdict
from collections.abc import Sequence
from datetime import date

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Attachment, Receipt, Shipment, ShipmentItem, User
from app.schemas.common import VendorRef
from app.schemas.shipments import (
    AttachmentOut,
    DiscrepancyOut,
    ReceiptItemOut,
    ReceiptOut,
    ShipmentDetail,
    ShipmentItemOut,
)
from app.services.status import is_shipment_overdue

# Load everything a shipment view needs in a few queries
SHIPMENT_LOAD = (
    selectinload(Shipment.items).selectinload(ShipmentItem.po_item),
    selectinload(Shipment.receipts).selectinload(Receipt.items),
    selectinload(Shipment.discrepancies),
    selectinload(Shipment.po),
)


def _attachments(db: Session, targets: dict[str, set[int]]) -> dict[tuple[str, int], list[Attachment]]:
    conditions = [
        and_(Attachment.entity_type == kind, Attachment.entity_id.in_(ids)) for kind, ids in targets.items() if ids
    ]
    result: dict[tuple[str, int], list[Attachment]] = defaultdict(list)
    if conditions:
        for a in db.scalars(select(Attachment).where(or_(*conditions)).order_by(Attachment.id)):
            result[(a.entity_type, a.entity_id)].append(a)
    return result


def build_shipments(db: Session, shipments: Sequence[Shipment], today: date) -> list[ShipmentDetail]:
    receipts = [r for s in shipments for r in s.receipts]
    discrepancies = [d for s in shipments for d in s.discrepancies]
    files = _attachments(
        db,
        {
            "shipment": {s.id for s in shipments},
            "receipt": {r.id for r in receipts},
            "discrepancy": {d.id for d in discrepancies},
        },
    )

    user_ids = {s.created_by for s in shipments} | {r.received_by for r in receipts}
    user_ids |= {d.reported_by for d in discrepancies} | {d.resolved_by for d in discrepancies}
    user_ids |= {a.uploaded_by for group in files.values() for a in group}
    user_ids.discard(None)
    names = dict(db.execute(select(User.id, User.name).where(User.id.in_(user_ids))).all()) if user_ids else {}

    def files_for(kind: str, entity_id: int) -> list[AttachmentOut]:
        out = []
        for a in files.get((kind, entity_id), []):
            item = AttachmentOut.model_validate(a)
            item.uploaded_by_name = names.get(a.uploaded_by)
            out.append(item)
        return out

    result = []
    for s in shipments:
        item_names = {si.po_item_id: si.po_item.item_name for si in s.items}
        receipt = s.receipts[-1] if s.receipts else None
        result.append(
            ShipmentDetail(
                id=s.id,
                shipment_no=s.shipment_no,
                po_id=s.po_id,
                po_number=s.po.po_number,
                vendor=VendorRef.model_validate(s.po.vendor),
                is_partial=s.is_partial,
                courier=s.courier,
                tracking_number=s.tracking_number,
                expected_delivery_date=s.expected_delivery_date,
                dispatched_at=s.dispatched_at,
                created_by_name=names.get(s.created_by),
                status=s.status,
                overdue=is_shipment_overdue(s.status, s.expected_delivery_date, today),
                items=[
                    ShipmentItemOut(
                        po_item_id=si.po_item_id,
                        line_no=si.po_item.line_no,
                        item_name=si.po_item.item_name,
                        item_code=si.po_item.item_code,
                        vendor_confirmed_name=si.po_item.vendor_confirmed_name,
                        unit=si.po_item.unit,
                        quantity_shipped=si.quantity_shipped,
                    )
                    for si in sorted(s.items, key=lambda x: x.po_item.line_no)
                ],
                receipt=(
                    ReceiptOut(
                        id=receipt.id,
                        received_by_name=names.get(receipt.received_by),
                        received_at=receipt.received_at,
                        notes=receipt.notes,
                        items=[
                            ReceiptItemOut(
                                po_item_id=ri.po_item_id,
                                item_name_entered=ri.item_name_entered,
                                quantity_received=ri.quantity_received,
                                quantity_accepted=ri.quantity_accepted,
                            )
                            for ri in receipt.items
                        ],
                        attachments=files_for("receipt", receipt.id),
                    )
                    if receipt
                    else None
                ),
                discrepancies=[
                    DiscrepancyOut(
                        id=d.id,
                        shipment_id=d.shipment_id,
                        po_item_id=d.po_item_id,
                        item_name=item_names.get(d.po_item_id) if d.po_item_id else None,
                        type=d.type,
                        description=d.description,
                        status=d.status,
                        reported_by_name=names.get(d.reported_by),
                        created_at=d.created_at,
                        resolution_note=d.resolution_note,
                        resolved_by_name=names.get(d.resolved_by),
                        resolved_at=d.resolved_at,
                        attachments=files_for("discrepancy", d.id),
                    )
                    for d in s.discrepancies
                ],
                attachments=files_for("shipment", s.id),
            )
        )
    return result


def load_shipments(db: Session, *conditions) -> list[Shipment]:
    return list(db.scalars(select(Shipment).where(*conditions).options(*SHIPMENT_LOAD).order_by(Shipment.id)))
