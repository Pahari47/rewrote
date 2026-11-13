import uuid
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import UPLOAD_URL_EXPIRY, generate_upload_url
from app.models.media import Media
from app.schemas.media import UploadRequest, UploadResponse


async def create_media_upload(db: AsyncSession, payload: UploadRequest):
    extension = Path(payload.filename).suffix.lower()

    file_id = uuid.uuid4()
    object_key = f"uploads/{file_id}{extension}"

    try:
        upload_url = generate_upload_url(object_key, payload.content_type)
    except Exception:
        raise HTTPException(status_code=503, detail="Storage service unavailable")

    media = Media(
        id=file_id,
        original_filename=payload.filename,
        object_key=object_key,
        content_type=payload.content_type,
        file_size=payload.file_size,
        status="pending",
    )

    db.add(media)

    try:
        await db.commit()
        await db.refresh(media)
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to save upload metadata")

    return UploadResponse(
        file_id=media.id,
        upload_url=upload_url,
        object_key=media.object_key,
        expires_in=UPLOAD_URL_EXPIRY,
    )