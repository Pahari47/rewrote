import asyncio
import os
import socket

from redis.asyncio import Redis

from app.core.redis import redis_client
from app.database import AsyncSessionLocal
from app.services.job import (
    claim_job,
    complete_job_service,
    execute_job_simulation_service,
    handle_job_failure_service,
)

MAX_CONCURRENT_JOBS = 10
semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)
WORKER_ID = os.getenv("WORKER_ID", f"{socket.gethostname()}-{os.getpid()}")

async def process_job(job_id: int, redis: Redis) -> None:
    async with semaphore:
        async with AsyncSessionLocal() as db:
            lease_token = await claim_job(db, job_id, WORKER_ID)
            if lease_token is None:
                return
            try:
                await execute_job_simulation_service(db, WORKER_ID, job_id, lease_token)
                await complete_job_service(db, WORKER_ID, job_id, lease_token)
            except Exception as e:
                await handle_job_failure_service(
                    db, redis, job_id, WORKER_ID, lease_token, str(e)
                )


async def job_worker(redis: Redis) -> None:
    print("Job worker started; blocking on Redis list 'jobs:queue'")

    while True:
        result = await redis.blpop("jobs:queue", timeout=0)

        if result is None:
            continue

        _, job_id_raw = result
        job_id = int(job_id_raw)

        asyncio.create_task(process_job(job_id, redis))


async def main() -> None:
    await redis_client.ping()
    try:
        await job_worker(redis_client)
    finally:
        await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
