"""SQLAlchemy models. Importing this package registers every table on Base.metadata (needed by Alembic)."""
from app.models.enums import DiscrepancyStatus, DiscrepancyType, EntityType, POStatus, Role, ShipmentStatus
from app.models.tables import (
    Attachment,
    Discrepancy,
    EmailLog,
    Notification,
    POItem,
    PurchaseOrder,
    Receipt,
    ReceiptItem,
    Shipment,
    ShipmentItem,
    StatusHistory,
    User,
    Vendor,
)

__all__ = [
    "Attachment",
    "Discrepancy",
    "DiscrepancyStatus",
    "DiscrepancyType",
    "EmailLog",
    "EntityType",
    "Notification",
    "POItem",
    "POStatus",
    "PurchaseOrder",
    "Receipt",
    "ReceiptItem",
    "Role",
    "Shipment",
    "ShipmentItem",
    "ShipmentStatus",
    "StatusHistory",
    "User",
    "Vendor",
]
