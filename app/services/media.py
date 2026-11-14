import uuid
from pathlib import Path
from starlette.concurrency import run_in_threadpool

from fastapi import HTTPException
from sqlalchemy import UUID, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import MAX_UPLOAD_SIZE, MIN_UPLOAD_SIZE, UPLOAD_URL_EXPIRY, delete_object, generate_upload_url, get_object_metada, read_object_header
from app.models.media import Media
from app.schemas.media import CompleteUploadResponse, UploadRequest, UploadResponse
from app.validation.file_validation import detect_file_type


async def create_media_upload(db: AsyncSession, payload: UploadRequest):

    file_id = uuid.uuid4()
    object_key = f"uploads/{file_id}"

    try:
        presigned = generate_upload_url(object_key)
    except Exception:
        raise HTTPException(status_code=503, detail="Storage service unavailable")

    media = Media(
        id=file_id,
        original_filename=payload.filename,
        object_key=object_key,
        content_type="application/octet-stream",
        file_size=None,
        status="pending",
    )

    db.add(media)

    try:
        await db.commit()
        await db.refresh(media)
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to save upload metadata")

    fields = {
        key: value.decode() if isinstance(value, bytes) else str(value)
        for key, value in presigned["fields"].items()
    }

    return UploadResponse(
        file_id=file_id,
        upload_url=presigned["url"],
        fields=fields,
        object_key=object_key,
        file_size=None,
        expires_in=UPLOAD_URL_EXPIRY,
    )

async def complete_upload(file_id: UUID, db: AsyncSession):
    result = await db.execute(select(Media).where(Media.id == file_id))

    media = result.scalar_one_or_none()

    if media is None:
        raise HTTPException(status_code=404, detail="Media not found")

    if media.status == "uploaded":
        return CompleteUploadResponse(
            file_id=media.id,
            status=media.status,
            content_type=media.content_type,
            file_size=media.file_size,
        )

    if media.status != "pending":
        raise HTTPException(status_code=409, detail="Upload cannot be completed")
    
    try:
        metadata = await run_in_threadpool(
            get_object_metada,
            media.object_key
        )
    except Exception:
        raise HTTPException(
            status_code=409,
            detail="File has not been uploaded to storage",
        )

    actual_size = metadata["ContentLength"]

    if actual_size < MIN_UPLOAD_SIZE or actual_size > MAX_UPLOAD_SIZE:
        await run_in_threadpool(
            delete_object,
            media.object_key
        )

        media.status = "rejected"
        await db.commit()

        raise HTTPException(
            status_code=400,
            detail="File size is not within the allowed range",
        )

    try:
        header = await run_in_threadpool(
            read_object_header,
            media.object_key
        )
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Could not inspect uploaded file",
        )
    
    detected = detect_file_type(header)

    if detected is None:
        await run_in_threadpool(
            delete_object,
            media.object_key
        )

        media.status = "rejected"
        await db.commit()

        raise HTTPException(
            status_code=415,
            detail="Unsupported or invalid file format",
        )
    
    media.content_type = detected.content_type
    media.file_size = actual_size
    media.status = "uploaded"

    await db.commit()

    await db.refresh(media)

    return CompleteUploadResponse(
        file_id=media.id,
        status=media.status,
        content_type=media.content_type,
        file_size=media.file_size,
    )