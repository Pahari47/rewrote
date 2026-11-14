import os
from celery import Celery
from dotenv import load_dotenv
from kombu import Queue

load_dotenv()

celery_app = Celery(
    "media_api",
    broker=os.getenv(
        "CELERY_BROKER_URL"
    ),
    include=["app.workers.transform_tasks"]
)

celery_app.conf.update(
    # Dedicated queue
    task_default_queue="media_transform",

    task_queues=(
        Queue("media_transform"),
    ),

    # Reliability
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    # Performance : avoid reserving too many tasks
    worker_prefetch_multiplier=1,

    # Execution limits
    task_time_limit=300,
    task_soft_time_limit=270,

    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Trak result in database
    task_ignore_result=True,

    # UTC timestamps
    timezone="UTC",
    enable_utc=True,
)