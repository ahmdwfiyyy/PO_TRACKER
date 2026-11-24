"""Database tables (see PO_TRACKER_SPEC.md section 6).

Additions to the spec's starting model:
- purchase_orders.acknowledged_at / acknowledged_by: when the vendor confirmed the PO (drives PREPARING)
- receipt_items.quantity_accepted: only accepted qty counts toward the PO (damaged units stay outstanding)
- discrepancies.receipt_id / created_at, notifications/email_log as in the spec
"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, utcnow
from app.models.enums import DiscrepancyStatus, POStatus, ShipmentStatus

# Quantities may be fractional (kg, metres), so they are stored as exact decimals
Qty = Numeric(14, 3)


def _ts(**kw) -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), default=utcnow, **kw)


# --------------------------------------------------------------------------- people
class Vendor(Base):
    __tablename__ = "vendors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    contact_person: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(254))
    phone: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = _ts()

    users: Mapped[list["User"]] = relationship(back_populates="vendor")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(254), unique=True)  # always stored lower-case
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))
    vendor_id: Mapped[int | None] = mapped_column(ForeignKey("vendors.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = _ts()

    vendor: Mapped[Vendor | None] = relationship(back_populates="users")


# --------------------------------------------------------------------------- purchase orders
class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    po_number: Mapped[str] = mapped_column(String(50), unique=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default=POStatus.ISSUED, index=True)
    issue_date: Mapped[date] = mapped_column(Date)
    required_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    external_ref: Mapped[str | None] = mapped_column(String(100), unique=True)  # ERP id, for future import
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = _ts(onupdate=utcnow)

    vendor: Mapped[Vendor] = relationship()
    creator: Mapped[User | None] = relationship(foreign_keys=[created_by])
    items: Mapped[list["POItem"]] = relationship(
        back_populates="po", cascade="all, delete-orphan", order_by="POItem.line_no"
    )
    shipments: Mapped[list["Shipment"]] = relationship(back_populates="po", order_by="Shipment.id")


class POItem(Base):
    __tablename__ = "po_items"
    __table_args__ = (UniqueConstraint("po_id", "line_no", name="uq_po_items_po_line"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    po_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id", ondelete="CASCADE"), index=True)
    line_no: Mapped[int] = mapped_column(Integer)
    item_name: Mapped[str] = mapped_column(String(300))
    item_code: Mapped[str | None] = mapped_column(String(100))
    quantity_ordered: Mapped[Decimal] = mapped_column(Qty)
    unit: Mapped[str] = mapped_column(String(20))
    vendor_confirmed_name: Mapped[str | None] = mapped_column(String(300))
    vendor_confirmed_qty: Mapped[Decimal | None] = mapped_column(Qty)

    po: Mapped[PurchaseOrder] = relationship(back_populates="items")


# --------------------------------------------------------------------------- shipments and receiving
class Shipment(Base):
    __tablename__ = "shipments"

    id: Mapped[int] = mapped_column(primary_key=True)
    po_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"), index=True)
    shipment_no: Mapped[str] = mapped_column(String(60), unique=True)
    is_partial: Mapped[bool] = mapped_column(Boolean, default=False)
    courier: Mapped[str | None] = mapped_column(String(100))
    tracking_number: Mapped[str | None] = mapped_column(String(100))
    expected_delivery_date: Mapped[date | None] = mapped_column(Date)
    dispatched_at: Mapped[datetime] = _ts()
    status: Mapped[str] = mapped_column(String(20), default=ShipmentStatus.ON_THE_WAY, index=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    po: Mapped[PurchaseOrder] = relationship(back_populates="shipments")
    items: Mapped[list["ShipmentItem"]] = relationship(back_populates="shipment", cascade="all, delete-orphan")
    receipts: Mapped[list["Receipt"]] = relationship(back_populates="shipment", order_by="Receipt.id")
    discrepancies: Mapped[list["Discrepancy"]] = relationship(back_populates="shipment", order_by="Discrepancy.id")


class ShipmentItem(Base):
    __tablename__ = "shipment_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipments.id", ondelete="CASCADE"), index=True)
    po_item_id: Mapped[int] = mapped_column(ForeignKey("po_items.id"))
    quantity_shipped: Mapped[Decimal] = mapped_column(Qty)

    shipment: Mapped[Shipment] = relationship(back_populates="items")
    po_item: Mapped[POItem] = relationship()


class Receipt(Base):
    __tablename__ = "receipts"

    id: Mapped[int] = mapped_column(primary_key=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipments.id"), index=True)
    received_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    received_at: Mapped[datetime] = _ts()
    notes: Mapped[str | None] = mapped_column(Text)

    shipment: Mapped[Shipment] = relationship(back_populates="receipts")
    items: Mapped[list["ReceiptItem"]] = relationship(back_populates="receipt", cascade="all, delete-orphan")


class ReceiptItem(Base):
    __tablename__ = "receipt_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    receipt_id: Mapped[int] = mapped_column(ForeignKey("receipts.id", ondelete="CASCADE"), index=True)
    po_item_id: Mapped[int] = mapped_column(ForeignKey("po_items.id"), index=True)
    item_name_entered: Mapped[str] = mapped_column(String(300))
    quantity_received: Mapped[Decimal] = mapped_column(Qty)
    quantity_accepted: Mapped[Decimal] = mapped_column(Qty)

    receipt: Mapped[Receipt] = relationship(back_populates="items")
    po_item: Mapped[POItem] = relationship()


class Discrepancy(Base):
    __tablename__ = "discrepancies"

    id: Mapped[int] = mapped_column(primary_key=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipments.id"), index=True)
    receipt_id: Mapped[int | None] = mapped_column(ForeignKey("receipts.id"))
    po_item_id: Mapped[int | None] = mapped_column(ForeignKey("po_items.id"))
    type: Mapped[str] = mapped_column(String(20))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default=DiscrepancyStatus.OPEN, index=True)
    reported_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = _ts()
    resolution_note: Mapped[str | None] = mapped_column(Text)
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    shipment: Mapped[Shipment] = relationship(back_populates="discrepancies")
    po_item: Mapped[POItem | None] = relationship()


# --------------------------------------------------------------------------- files, audit, notifications
class Attachment(Base):
    __tablename__ = "attachments"
    __table_args__ = (Index("ix_attachments_entity", "entity_type", "entity_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(20))
    entity_id: Mapped[int] = mapped_column(Integer)
    filename: Mapped[str] = mapped_column(String(255))  # original name, for display only
    stored_path: Mapped[str] = mapped_column(String(255))  # generated name, never from the user
    mime_type: Mapped[str] = mapped_column(String(100))
    size: Mapped[int] = mapped_column(Integer)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    uploaded_at: Mapped[datetime] = _ts()


class StatusHistory(Base):
    __tablename__ = "status_history"
    __table_args__ = (Index("ix_status_history_entity", "entity_type", "entity_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(20))
    entity_id: Mapped[int] = mapped_column(Integer)
    old_status: Mapped[str | None] = mapped_column(String(30))
    new_status: Mapped[str] = mapped_column(String(30))
    changed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    changed_at: Mapped[datetime] = _ts()
    note: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User | None] = relationship()


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_unread", "user_id", "is_read"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    type: Mapped[str] = mapped_column(String(50))
    message: Mapped[str] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(String(255))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = _ts()


class EmailLog(Base):
    __tablename__ = "email_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    to_address: Mapped[str] = mapped_column(String(254))
    subject: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = _ts()
