from datetime import datetime, timezone
import json

from app.core.redis import redis_client

async def subscribe_progress(job_id: int):
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

            if event.get("status") == "done":
                break
    
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()


async def publish_progress(
    job_id: int,
    status: str,
    progress: int,
    message: str
):
    event = {
        "job_id": job_id,
        "status": status,
        "progress": progress,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    channel = f"job:{job_id}:progress"

    await redis_client.publish(channel, json.dumps(event))