from datetime import datetime, timezone
from uuid import UUID
import os
from botocore.exceptions import ConnectionClosedError, EndpointConnectionError, ReadTimeoutError, ConnectTimeoutError
from celery import Task
from sqlalchemy import create_engine, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.celery_app import celery_app
from app.models.media import Media
from app.models.transform import TransFormMedia
from app.services.image_processor import transform_image
from app.services.progress import publish_progress_sync


engine = create_engine(
    os.environ["DATABASE_SYNC_URL"],
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    expire_on_commit=False,
)

RETRYABLE_ERRORS = (
    OperationalError,
    EndpointConnectionError,
    ConnectionClosedError,
    ReadTimeoutError,
    ConnectTimeoutError,
)

@celery_app.task(
    bind=True,
    name="media.transform",
    acks_late=True,
    reject_on_worker_lost=True,
    autoretry_for=RETRYABLE_ERRORS,
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=3,
    time_limit=300,
    soft_time_limit=270,
)

def process_transform(self: Task, job_id: str):
    job_uuid = UUID(job_id)

    with SessionLocal() as db:
        job = db.execute(
            select(TransFormMedia)
            .where(TransFormMedia.id == job_uuid)
        ).scalar_one_or_none()

        if job is None:
            publish_progress_sync(job_id, "failed", 0, "transform job not found")
            return {"status": "not_found"}

        # duplicate delivery after successfull processing
        if job.status == "completed":
            publish_progress_sync(job_id, "done", 100, "already completed")
            return {"status": "already_completed"}

        media = db.execute(
            select(Media).where(Media.id == job.media_id)
        ).scalar_one()

        job.status = "processing"
        job.error_message = None
        db.commit()

        try:
            result = transform_image(
                input_key=media.object_key,
                output_key=job.output_key,
                width=job.width,
                height=job.height,
                output_format=job.output_format,
                on_progress=lambda status, progress, message: publish_progress_sync(
                    job_id, status, progress, message
                ),
            )

            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            job.error_message = None

            db.commit()

            publish_progress_sync(job_id, "done", 100, "Transform complete")

            return {
                "status": "completed",
                "job_id": str(job.id),
                **result
            }

        except Exception as exc:
            db.rollback()

            # Mark permanently failed after retries are exhausted.
            if not isinstance(exc, RETRYABLE_ERRORS) or self.request.retries >= self.max_retries:
                failed_job = db.get(TransFormMedia, job.id)

                if failed_job:
                    failed_job.status = "failed"
                    failed_job.error_message = str(exc)[:2000]
                    db.commit()

                publish_progress_sync(job_id, "failed", 0, str(exc)[:2000])

            raise
