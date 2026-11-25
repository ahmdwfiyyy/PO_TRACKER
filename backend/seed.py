"""Create demo accounts, vendors and POs in every stage of the delivery flow.

    docker compose exec backend python seed.py           # only if the database is empty
    docker compose exec backend python seed.py --reset   # wipe ALL data first, then seed
    docker compose exec backend python seed.py --clear-pos   # delete all POs, keep users and vendors

Every demo account uses the password in SEED_PASSWORD (default: Password123!).
"""
import sys
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.config import get_settings, today
from app.db import Base, SessionLocal, engine
from app.models import PurchaseOrder, Role, Shipment, User, Vendor
from app.schemas.shipments import AcknowledgeRequest, DiscrepancyIn, ReceiveItemIn, ReceiveRequest, ShipmentCreate, ShipmentItemIn
from app.services.po import create_po
from app.services.shipments import acknowledge_po, create_shipment, receive_shipment
from app.services.users import create_user


@dataclass
class Line:
    item_name: str
    quantity_ordered: Decimal
    unit: str
    item_code: str | None = None


def wipe() -> None:
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    print("All data deleted.")


def clear_pos() -> None:
    """Delete every PO and everything hanging off it. Users and vendors are kept."""
    from app.models import (
        Attachment, Discrepancy, EmailLog, Notification, POItem, Receipt, ReceiptItem, ShipmentItem, StatusHistory,
    )
    from app.services.storage import get_storage

    db = SessionLocal()
    try:
        storage = get_storage()
        files = 0
        for stored in db.scalars(select(Attachment.stored_path)):
            path = storage.path(stored)
            if path.is_file():
                path.unlink()
                files += 1
        for model in (Discrepancy, ReceiptItem, Receipt, ShipmentItem, Shipment, POItem, PurchaseOrder,
                      Attachment, StatusHistory, Notification, EmailLog):
            db.query(model).delete()
        db.commit()
        print(f"All POs, shipments, receipts, discrepancies, notifications and {files} uploaded file(s) deleted.")
        print("Users and vendors were kept.")
    finally:
        db.close()


def ship(db, po: PurchaseOrder, user: User, quantities: dict[int, Decimal], courier: str, days: int) -> Shipment:
    items = {i.line_no: i.id for i in po.items}
    body = ShipmentCreate(
        courier=courier,
        tracking_number=f"{courier[:3].upper()}{po.id:04d}{len(po.shipments) + 1}",
        expected_delivery_date=today() + timedelta(days=days),
        items=[ShipmentItemIn(po_item_id=items[n], quantity=q) for n, q in quantities.items()],
    )
    shipment = create_shipment(db, po, user, body, today())
    db.refresh(po)
    return shipment


def receive(db, shipment: Shipment, user: User, accepted: dict[int, Decimal] | None = None, discrepancies=()) -> None:
    accepted = accepted or {}
    body = ReceiveRequest(
        items=[
            ReceiveItemIn(
                po_item_id=si.po_item_id,
                item_name_entered=si.po_item.item_name,
                quantity_received=si.quantity_shipped,
                quantity_accepted=accepted.get(si.po_item.line_no, si.quantity_shipped),
            )
            for si in shipment.items
        ],
        discrepancies=list(discrepancies),
    )
    receive_shipment(db, shipment, user, body)


def main() -> None:
    if "--clear-pos" in sys.argv:
        clear_pos()
        return
    if "--reset" in sys.argv:
        wipe()
    password = get_settings().seed_password
    db = SessionLocal()
    try:
        if db.scalar(select(User).where(User.email == "purchasing@carsem.com")):
            print("Demo data already exists - nothing to do. Use --reset to start over.")
            return

        purchasing = create_user(db, name="Nurul Purchasing", email="purchasing@carsem.com", password=password, role=Role.PURCHASING)
        receiving = create_user(db, name="Hafiz Receiving", email="receiving@carsem.com", password=password, role=Role.RECEIVING)

        apex = Vendor(name="Apex Industrial Supplies Sdn Bhd", contact_person="Lim Wei Ming", email="sales@apex.example.com", phone="+60 5-555 0101")
        borneo = Vendor(name="Borneo Precision Parts Sdn Bhd", contact_person="Siti Aminah", email="orders@borneo.example.com", phone="+60 82-555 0202")
        db.add_all([apex, borneo])
        db.flush()
        apex_user = create_user(db, name="Lim Wei Ming", email="vendor@apex.example.com", password=password, role=Role.VENDOR, vendor_id=apex.id)
        borneo_user = create_user(db, name="Siti Aminah", email="vendor@borneo.example.com", password=password, role=Role.VENDOR, vendor_id=borneo.id)

        d = today()

        def po(number, vendor, issued_days_ago, required_in_days, lines):
            return create_po(
                db,
                po_number=number,
                vendor_id=vendor.id,
                issue_date=d - timedelta(days=issued_days_ago),
                required_date=d + timedelta(days=required_in_days),
                items=lines,
                notes="Demo purchase order",
                created_by=purchasing,
            )

        # 1. Apex: acknowledged, partial shipment on the way -> Receiving sees it under Incoming
        po1 = po("PO-2026-0001", apex, 10, 7, [
            Line("Anti-static ESD gloves (M)", Decimal(500), "pair", "ESD-GLV-M"),
            Line("Isopropyl alcohol 99% 4L", Decimal(20), "bottle", "IPA-4L"),
        ])
        acknowledge_po(db, po1, apex_user, AcknowledgeRequest())
        ship(db, po1, apex_user, {1: Decimal(300), 2: Decimal(20)}, "DHL", 1)

        # 2. Apex: overdue and not yet acknowledged
        po("PO-2026-0002", apex, 20, -2, [Line("Cleanroom wipes 9x9", Decimal(40), "pack", "CRW-99")])

        # 3. Borneo: partially delivered (lead frame still to come)
        po3 = po("PO-2026-0003", borneo, 5, 14, [
            Line("Stainless steel tweezers", Decimal(50), "pcs", "TWZ-SS"),
            Line("Copper lead frame strip", Decimal("12.5"), "kg", "CU-LF-01"),
            Line("Kapton tape 25mm", Decimal(30), "roll"),
        ])
        acknowledge_po(db, po3, borneo_user, AcknowledgeRequest())
        receive(db, ship(db, po3, borneo_user, {1: Decimal(50), 3: Decimal(30)}, "GDEX", 2), receiving)

        # 4. Apex: received with damaged goods -> open discrepancy (red badge)
        po4 = po("PO-2026-0004", apex, 15, 3, [Line("Wafer carrier box 8in", Decimal(24), "pcs", "WCB-8")])
        acknowledge_po(db, po4, apex_user, AcknowledgeRequest())
        receive(
            db, ship(db, po4, apex_user, {1: Decimal(24)}, "Pos Laju", 1), receiving, {1: Decimal(20)},
            [DiscrepancyIn(po_item_id=po4.items[0].id, type="DAMAGED", description="4 boxes cracked in transit")],
        )

        # 5. Borneo: fully delivered -> stays in the vendor's History
        po5 = po("PO-2026-0005", borneo, 30, 10, [Line("Solder paste SAC305 500g", Decimal(10), "jar", "SP-305")])
        acknowledge_po(db, po5, borneo_user, AcknowledgeRequest())
        receive(db, ship(db, po5, borneo_user, {1: Decimal(10)}, "City-Link", 1), receiving)

        # 6. Borneo: new PO waiting for acknowledgement
        po("PO-2026-0006", borneo, 1, 21, [Line("Nitrile finger cots", Decimal(2000), "pcs", "NFC-01")])

        db.commit()
        print("Demo data created. Sign in with any of these (password: SEED_PASSWORD):")
        for email in ("purchasing@carsem.com", "receiving@carsem.com", "vendor@apex.example.com", "vendor@borneo.example.com"):
            print(f"  {email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
