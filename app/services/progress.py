from datetime import datetime, timezone
import json
import os

from redis import Redis as SyncRedis

from app.core.redis import redis_client

sync_redis = SyncRedis.from_url(
    os.getenv("REDIS_URL"),
    decode_responses=True,
)


async def subscribe_progress(job_id: str):
    channel = f"job:{job_id}:progress"

    pubsub = redis_client.pubsub()

    await pubsub.subscribe(channel)

    try:
        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=1.0
            )

            if not message:
                continue

            event = json.loads(message["data"])

            yield event

            if event.get("status") in ("done", "failed"):
                break

    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()


async def publish_progress(
    job_id: str,
    status: str,
    progress: int,
    message: str
):
    event = {
        "job_id": str(job_id),
        "status": status,
        "progress": progress,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    payload = json.dumps(event)

    await redis_client.set(f"job:{job_id}:progress:latest", payload, ex=3600)
    await redis_client.publish(f"job:{job_id}:progress", payload)


def publish_progress_sync(
    job_id: str,
    status: str,
    progress: int,
    message: str,
) -> None:
    event = {
        "job_id": str(job_id),
        "status": status,
        "progress": progress,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    payload = json.dumps(event)

    try:
        sync_redis.set(f"job:{job_id}:progress:latest", payload, ex=3600)
        sync_redis.publish(f"job:{job_id}:progress", payload)
    except Exception:
        return
