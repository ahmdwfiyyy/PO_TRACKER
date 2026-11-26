from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse

from app.core.config import get_settings
from app.core.deps import DB, CurrentUser
from app.models import EntityType
from app.schemas.shipments import AttachmentOut
from app.services.attachments import get_attachment_for_user, save_attachment
from app.services.errors import ServiceError
from app.services.storage import get_storage

router = APIRouter(prefix="/attachments", tags=["attachments"])


@router.post("", response_model=AttachmentOut, status_code=201)
async def upload(
    db: DB,
    user: CurrentUser,
    entity_type: Annotated[EntityType, Form()],
    entity_id: Annotated[int, Form()],
    file: Annotated[UploadFile, File()],
):
    """Attach a PDF/JPG/PNG to a PO, shipment (DO/invoice), receipt or discrepancy (photos)."""
    limit = get_settings().max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)  # one byte over the limit is enough to reject it
    attachment = save_attachment(
        db, user, entity_type=entity_type, entity_id=entity_id, filename=file.filename, data=data
    )
    db.commit()
    out = AttachmentOut.model_validate(attachment)
    out.uploaded_by_name = user.name
    return out


@router.get("/{attachment_id}")
def download(attachment_id: int, db: DB, user: CurrentUser):
    """Only users who can see the attachment's PO can download it."""
    attachment = get_attachment_for_user(db, attachment_id, user)
    path = get_storage().path(attachment.stored_path)
    if not path.is_file():
        raise ServiceError("File is missing from storage", 404)
    return FileResponse(path, media_type=attachment.mime_type, filename=attachment.filename)
