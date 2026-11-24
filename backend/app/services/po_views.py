"""Turn PO rows into API responses (list rows and the full detail page)."""
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import PurchaseOrder, Shipment, ShipmentItem, StatusHistory
from app.schemas.pos import (
    HistoryOut,
    PODetail,
    POItemOut,
    POListItem,
    ShipmentItemOut,
    ShipmentOut,
    VendorRef,
)
from app.services.po import is_locked, open_discrepancy_expr, overdue_expr
from app.services.status import ZERO, ItemTotals, is_shipment_overdue, item_totals


def to_list_item(po: PurchaseOrder, overdue: bool, has_disc: bool) -> POListItem:
    names = [i.item_name for i in po.items]
    summary = ", ".join(names[:2]) + (f" +{len(names) - 2} more" if len(names) > 2 else "")
    return POListItem(
        id=po.id,
        po_number=po.po_number,
        vendor=VendorRef.model_validate(po.vendor),
        status=po.status,
        issue_date=po.issue_date,
        required_date=po.required_date,
        item_count=len(names),
        item_summary=summary,
        overdue=overdue,
        has_open_discrepancy=has_disc,
        created_at=po.created_at,
        updated_at=po.updated_at,
    )


def build_po_detail(db: Session, po: PurchaseOrder, today: date) -> PODetail:
    overdue, has_disc = db.execute(
        select(overdue_expr(today), open_discrepancy_expr()).where(PurchaseOrder.id == po.id)
    ).one()
    totals = item_totals(db, po.id)

    items = []
    for item in po.items:
        t = totals.get(item.id, ItemTotals())
        items.append(
            POItemOut(
                id=item.id,
                line_no=item.line_no,
                item_name=item.item_name,
                item_code=item.item_code,
                quantity_ordered=item.quantity_ordered,
                unit=item.unit,
                vendor_confirmed_name=item.vendor_confirmed_name,
                vendor_confirmed_qty=item.vendor_confirmed_qty,
                quantity_shipped=t.shipped,
                quantity_in_transit=t.in_transit,
                quantity_received=t.received,
                quantity_accepted=t.accepted,
                quantity_outstanding=max(ZERO, item.quantity_ordered - t.accepted),
            )
        )

    shipments = db.scalars(
        select(Shipment)
        .where(Shipment.po_id == po.id)
        .options(selectinload(Shipment.items).selectinload(ShipmentItem.po_item))
        .order_by(Shipment.id)
    ).all()
    shipment_out = [
        ShipmentOut(
            id=s.id,
            shipment_no=s.shipment_no,
            is_partial=s.is_partial,
            courier=s.courier,
            tracking_number=s.tracking_number,
            expected_delivery_date=s.expected_delivery_date,
            dispatched_at=s.dispatched_at,
            status=s.status,
            overdue=is_shipment_overdue(s.status, s.expected_delivery_date, today),
            items=[
                ShipmentItemOut(
                    po_item_id=si.po_item_id,
                    line_no=si.po_item.line_no,
                    item_name=si.po_item.item_name,
                    unit=si.po_item.unit,
                    quantity_shipped=si.quantity_shipped,
                )
                for si in sorted(s.items, key=lambda x: x.po_item.line_no)
            ],
        )
        for s in shipments
    ]

    # Timeline: the PO's own status changes plus those of its shipments
    shipment_ids = [s.id for s in shipments]
    history_rows = db.scalars(
        select(StatusHistory)
        .options(selectinload(StatusHistory.user))
        .where(
            or_(
                (StatusHistory.entity_type == "po") & (StatusHistory.entity_id == po.id),
                (StatusHistory.entity_type == "shipment") & StatusHistory.entity_id.in_(shipment_ids or [-1]),
            )
        )
        .order_by(StatusHistory.changed_at, StatusHistory.id)
    ).all()

    return PODetail(
        id=po.id,
        po_number=po.po_number,
        vendor=VendorRef.model_validate(po.vendor),
        status=po.status,
        issue_date=po.issue_date,
        required_date=po.required_date,
        notes=po.notes,
        external_ref=po.external_ref,
        acknowledged_at=po.acknowledged_at,
        created_by_name=po.creator.name if po.creator else None,
        created_at=po.created_at,
        updated_at=po.updated_at,
        overdue=bool(overdue),
        has_open_discrepancy=bool(has_disc),
        locked=is_locked(po),
        items=items,
        shipments=shipment_out,
        history=[
            HistoryOut(
                id=h.id,
                entity_type=h.entity_type,
                entity_id=h.entity_id,
                old_status=h.old_status,
                new_status=h.new_status,
                changed_by_name=h.user.name if h.user else None,
                changed_at=h.changed_at,
                note=h.note,
            )
            for h in history_rows
        ],
    )
