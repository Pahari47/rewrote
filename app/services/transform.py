from uuid import UUID, uuid4
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.media import Media
from app.models.transform import TransFormMedia
from app.schemas.transform import AVTransformRequest, TransformRequest, TransformResponse, TransformStatusResponse
from app.workers.av_tasks import process_av
from app.workers.transform_tasks import process_transform

VIDEO_OUTPUTS = {"mp4", "webm"}
AUDIO_OUTPUTS = {"mp3", "aac", "wav"}

async def create_transform(payload: TransformRequest, db: AsyncSession):
    result = await db.execute(
        select(Media).where(Media.id == payload.file_id)
    )

    media = result.scalar_one_or_none()

    if media is None:
        raise HTTPException(404, "media not found")
    
    if media.status != "uploaded":
        raise HTTPException(409, "Media is not been uploaded or verified")
    
    if not media.content_type.startswith("image/"):
        raise HTTPException(415, "Media is not an image")
    
    job_id = uuid4()

    extension = payload.output_format

    # determine output key
    output_key = (f"transforms/{job_id}/output.{extension}")

    job = TransFormMedia(
        id=job_id,
        media_id=media.id,
        output_key=output_key,
        output_format=payload.output_format,
        width=payload.width,
        height=payload.height,
        status="queued"
    )

    db.add(job)

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(500, "Failed to create transform job")
    
    try:
        process_transform.apply_async(
            args=[str(job.id)],
            task_id=str(job.id),
            queue="image",
        )
    except Exception:
        job.status = "failed"
        job.error_message = "could not enqueu task"
        await db.commit()
        raise HTTPException(503, "Failed to enqueue transform task")
    
    return TransformResponse(
        job_id=job_id,
        status="queued",
    )

async def get_transform_status(job_id: UUID, db: AsyncSession):
    result = await db.execute(
        select(TransFormMedia).where(
            TransFormMedia.id == job_id
        )
    )

    job = result.scalar_one_or_none()

    if job is None:
        raise HTTPException(404, "transform job not found")

    return TransformStatusResponse(
        job_id=job.id,
        file_id=job.media_id,
        status=job.status,
        output_key=(
            job.output_key
            if job.status == "completed"
            else None
        ),
        error_message=job.error_message,
    )

async def create_av_transform(payload: AVTransformRequest, db: AsyncSession):
    result = await db.execute(
        select(Media).where(Media.id == payload.file_id)
    )

    media = result.scalar_one_or_none()

    if media is None:
        raise HTTPException(404, "media not found")
    
    if media.status != "uploaded":
        raise HTTPException(409, "Media is not been uploaded or verified")
    
    if payload.output_format in VIDEO_OUTPUTS and not media.content_type.startswith("video/"):
        raise HTTPException(415, "Media is not a video")

    if payload.output_format in AUDIO_OUTPUTS and not media.content_type.startswith("audio/"):
        raise HTTPException(415, "Media is not a audio")
    
    job_id = uuid4()
    output_key = (f"transforms/{job_id}/output.{payload.output_format}")

    job = TransFormMedia(
        id=job_id,
        media_id=media.id,
        output_key=output_key,
        output_format=payload.output_format,
        width=payload.width or 0,
        height=payload.height or 0,
        status="queued"
    )

    db.add(job)

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(500, "Failed to create transform job")
    
    try:
        process_av.apply_async(
            args=[str(job.id)],
            kwargs={"timeout_seconds": payload.timeout_seconds},
            task_id=str(job.id),
            queue="video",
        )
    except Exception:
        job.status = "failed"
        job.error_message = "could not enqueu task"
        await db.commit()
        raise HTTPException(503, "Failed to enqueue transform task")
    
    return TransformResponse(
        job_id=job.id,
        status="queued",
    )
    