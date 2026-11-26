"""Uploading and downloading attachments (DO/invoice, receiving and discrepancy photos).

Rules (spec section 8):
- PDF, JPG or PNG only, checked from the file's content (not its name), max MAX_UPLOAD_MB.
- Who may upload depends on what the file is attached to (UPLOAD_ROLES).
- Anyone downloading must be able to see the PO the file belongs to (vendors only their own).
"""
import os

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Attachment, Discrepancy, EntityType, PurchaseOrder, Receipt, Role, Shipment, User
from app.services.access import get_visible_po
from app.services.errors import ServiceError
from app.services.storage import get_storage

EXTENSIONS = {"application/pdf": ".pdf", "image/jpeg": ".jpg", "image/png": ".png"}

UPLOAD_ROLES: dict[EntityType, set[Role]] = {
    EntityType.PO: {Role.PURCHASING},
    EntityType.SHIPMENT: {Role.VENDOR, Role.PURCHASING},  # DO, invoice
    EntityType.RECEIPT: {Role.RECEIVING, Role.PURCHASING},  # photos of received goods
    EntityType.DISCREPANCY: {Role.RECEIVING, Role.PURCHASING},  # photos of the problem
}


def sniff_mime(data: bytes) -> str | None:
    """Identify the file type from its first bytes."""
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    return None


def po_id_for(db: Session, entity_type: EntityType, entity_id: int) -> int:
    """The PO an attachment target belongs to (404 if the target does not exist)."""
    po_id: int | None = None
    if entity_type == EntityType.PO:
        po = db.get(PurchaseOrder, entity_id)
        po_id = po.id if po else None
    elif entity_type == EntityType.SHIPMENT:
        shipment = db.get(Shipment, entity_id)
        po_id = shipment.po_id if shipment else None
    elif entity_type == EntityType.RECEIPT:
        receipt = db.get(Receipt, entity_id)
        po_id = receipt.shipment.po_id if receipt else None
    elif entity_type == EntityType.DISCREPANCY:
        discrepancy = db.get(Discrepancy, entity_id)
        po_id = discrepancy.shipment.po_id if discrepancy else None
    if po_id is None:
        raise ServiceError(f"{entity_type.value.capitalize()} not found", 404)
    return po_id


def _display_name(filename: str | None, extension: str) -> str:
    name = os.path.basename((filename or "").replace("\\", "/")).strip()
    name = "".join(c for c in name if c.isprintable() and c not in '"<>|:*?')[:200]
    return name or f"file{extension}"


def save_attachment(
    db: Session, user: User, *, entity_type: EntityType, entity_id: int, filename: str | None, data: bytes
) -> Attachment:
    if Role(user.role) not in UPLOAD_ROLES[entity_type]:
        raise ServiceError("You cannot attach files here", 403)
    get_visible_po(db, po_id_for(db, entity_type, entity_id), user)  # 404 if not theirs

    limit = get_settings().max_upload_mb * 1024 * 1024
    if len(data) > limit:
        raise ServiceError(f"The file is larger than {get_settings().max_upload_mb} MB")
    if not data:
        raise ServiceError("The file is empty")
    mime = sniff_mime(data)
    if mime is None:
        raise ServiceError("Only PDF, JPG and PNG files can be uploaded")

    extension = EXTENSIONS[mime]
    stored = get_storage().save(data, extension)
    attachment = Attachment(
        entity_type=entity_type,
        entity_id=entity_id,
        filename=_display_name(filename, extension),
        stored_path=stored,
        mime_type=mime,
        size=len(data),
        uploaded_by=user.id,
    )
    db.add(attachment)
    db.flush()
    return attachment


def get_attachment_for_user(db: Session, attachment_id: int, user: User) -> Attachment:
    attachment = db.get(Attachment, attachment_id)
    if attachment is None:
        raise ServiceError("File not found", 404)
    try:
        get_visible_po(db, po_id_for(db, EntityType(attachment.entity_type), attachment.entity_id), user)
    except ServiceError:
        raise ServiceError("File not found", 404)
    return attachment
