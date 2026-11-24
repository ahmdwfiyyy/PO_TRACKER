"""Create demo accounts, vendors and POs.

    docker compose exec backend python seed.py

Safe to run more than once: it does nothing if the demo purchasing account already exists.
Every demo account uses the password in SEED_PASSWORD (default: Password123!).
"""
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.config import get_settings, today
from app.db import SessionLocal
from app.models import Role, User, Vendor
from app.services.po import create_po
from app.services.users import create_user


@dataclass
class Line:
    item_name: str
    quantity_ordered: Decimal
    unit: str
    item_code: str | None = None


def main() -> None:
    password = get_settings().seed_password
    db = SessionLocal()
    try:
        if db.scalar(select(User).where(User.email == "purchasing@carsem.com")):
            print("Demo data already exists - nothing to do.")
            return

        purchasing = create_user(
            db, name="Nurul Purchasing", email="purchasing@carsem.com", password=password, role=Role.PURCHASING
        )
        create_user(db, name="Hafiz Receiving", email="receiving@carsem.com", password=password, role=Role.RECEIVING)

        apex = Vendor(
            name="Apex Industrial Supplies Sdn Bhd",
            contact_person="Lim Wei Ming",
            email="sales@apex.example.com",
            phone="+60 5-555 0101",
        )
        borneo = Vendor(
            name="Borneo Precision Parts Sdn Bhd",
            contact_person="Siti Aminah",
            email="orders@borneo.example.com",
            phone="+60 82-555 0202",
        )
        db.add_all([apex, borneo])
        db.flush()
        create_user(db, name="Lim Wei Ming", email="vendor@apex.example.com", password=password, role=Role.VENDOR, vendor_id=apex.id)
        create_user(db, name="Siti Aminah", email="vendor@borneo.example.com", password=password, role=Role.VENDOR, vendor_id=borneo.id)

        d = today()
        demo_pos = [
            ("PO-2026-0001", apex, d - timedelta(days=10), d + timedelta(days=7), [
                Line("Anti-static ESD gloves (M)", Decimal(500), "pair", "ESD-GLV-M"),
                Line("Isopropyl alcohol 99% 4L", Decimal(20), "bottle", "IPA-4L"),
            ]),
            ("PO-2026-0002", apex, d - timedelta(days=20), d - timedelta(days=2), [
                Line("Cleanroom wipes 9x9", Decimal(40), "pack", "CRW-99"),
            ]),
            ("PO-2026-0003", borneo, d - timedelta(days=5), d + timedelta(days=14), [
                Line("Stainless steel tweezers", Decimal(50), "pcs", "TWZ-SS"),
                Line("Copper lead frame strip", Decimal(12.5), "kg", "CU-LF-01"),
                Line("Kapton tape 25mm", Decimal(30), "roll"),
            ]),
        ]
        for number, vendor, issued, required, lines in demo_pos:
            create_po(
                db,
                po_number=number,
                vendor_id=vendor.id,
                issue_date=issued,
                required_date=required,
                items=lines,
                notes="Demo purchase order",
                created_by=purchasing,
            )

        db.commit()
        print("Demo data created. Sign in with any of these (password: SEED_PASSWORD):")
        for email in ("purchasing@carsem.com", "receiving@carsem.com", "vendor@apex.example.com", "vendor@borneo.example.com"):
            print(f"  {email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
