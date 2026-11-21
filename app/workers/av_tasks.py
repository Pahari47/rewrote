from datetime import datetime, timezone
from uuid import UUID
from celery import Task
from sqlalchemy import select
from app.celery_app import celery_app
from app.models.media import Media
from app.models.transform import TransFormMedia
from app.services.av_processor import transcode_media
from app.services.ffmpeg_runner import FFmpegFailed, FFmpegTimeout
from app.services.progress import publish_progress_sync
from app.workers.transform_tasks import RETRYABLE_ERRORS, SessionLocal


@celery_app.task(
    bind=True,
    name="media.transcode",
    acks_late=True,
    reject_on_worker_lost=True,
    autoretry_for=RETRYABLE_ERRORS,
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=3,
    time_limit=660,
    soft_time_limit=630,
    queue="video",
)

def process_av(self: Task, job_id: str, timeout_seconds: int = 120):
    job_uuid = UUID(job_id)

    with SessionLocal() as db:
        job = db.execute(
            select(TransFormMedia).where(TransFormMedia.id == job_uuid)
        ).scalar_one_or_none()

        if job is None:
            publish_progress_sync(job_id, "failed", 0, "transform job not found")
            return {"status": "not_found"}

        if job.status == "completed":
            publish_progress_sync(job_id, "completed", 100, "transform job already completed")
            return {"status": "already completed"}
        
        media = db.execute(
            select(Media).where(Media.id == job.media_id)
        ).scalar_one()

        job.status = "processing"
        job.error_message = None
        db.commit()

        try:
            result = transcode_media(
                input_key=media.object_key,
                output_key=job.output_key,
                output_format=job.output_format,
                width=job.width,
                height=job.height,
                timeout=timeout_seconds,
                on_progress=lambda status, progress, message: publish_progress_sync(
                    job_id, status, progress, message
                ),
            )
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            job.error_message = None
            db.commit()
            publish_progress_sync(job_id, "done", 100, "transform job completed")
            return {"status": "completed", "job_id": str(job.id), **result}

        except Exception as exc:
            db.rollback()
            permanent = isinstance(exc, (FFmpegTimeout, FFmpegFailed)) or not isinstance(exc, RETRYABLE_ERRORS)
            if permanent or self.request.retries >= self.max_retries:
                failed_job = db.get(TransFormMedia, job.id)
                if failed_job:
                    failed_job.status = "failed"
                    failed_job.error_message = str(exc)[:2000]
                    db.commit()
                publish_progress_sync(job_id, "failed", 0, str(exc)[:2000])
            raise
    