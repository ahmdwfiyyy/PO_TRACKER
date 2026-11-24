"""All status and type values. Stored in the database as plain strings."""
from enum import StrEnum


class Role(StrEnum):
    PURCHASING = "purchasing"
    RECEIVING = "receiving"
    VENDOR = "vendor"


class POStatus(StrEnum):
    ISSUED = "ISSUED"
    PREPARING = "PREPARING"
    ON_THE_WAY = "ON_THE_WAY"
    PARTIALLY_DELIVERED = "PARTIALLY_DELIVERED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


class ShipmentStatus(StrEnum):
    ON_THE_WAY = "ON_THE_WAY"
    DELIVERED = "DELIVERED"
    DISCREPANCY = "DISCREPANCY"
    RESOLVED = "RESOLVED"


class DiscrepancyType(StrEnum):
    SHORT = "SHORT"
    EXCESS = "EXCESS"
    WRONG_ITEM = "WRONG_ITEM"
    DAMAGED = "DAMAGED"
    OTHER = "OTHER"


class DiscrepancyStatus(StrEnum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"


class EntityType(StrEnum):
    PO = "po"
    SHIPMENT = "shipment"
    RECEIPT = "receipt"
    DISCREPANCY = "discrepancy"
