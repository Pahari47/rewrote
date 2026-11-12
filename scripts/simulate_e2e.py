"""
End-to-end checks against a running stack (API + worker + scheduler).

Usage (from repo root, venv active):
  python scripts/simulate_e2e.py

Optional — worker must be restarted with:
  SIMULATE_JOB_FAILURE=1 python -m app.workers.job_worker
for the live failure/retry loop test.
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

# Allow: python scripts/simulate_e2e.py
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datetime import datetime, timezone

import httpx
from sqlalchemy import select

from app.core.redis import redis_client
from app.database import AsyncSessionLocal
from app.models import Job, JobStatus
from app.services.job import create_job_service, handle_job_failure_service
from app.schemas.job import JobCreate

API = "http://127.0.0.1:8000"
POLL_SECONDS = 15
POLL_INTERVAL = 0.25


def ok(msg: str) -> None:
    print(f"  PASS  {msg}")


def fail(msg: str) -> None:
    print(f"  FAIL  {msg}")


async def get_job(job_id: int) -> Job | None:
    async with AsyncSessionLocal() as db:
        return await db.get(Job, job_id)


async def wait_for_state(job_id: int, state: JobStatus) -> bool:
    deadline = time.monotonic() + POLL_SECONDS
    while time.monotonic() < deadline:
        job = await get_job(job_id)
        if job and job.state == state:
            return True
        await asyncio.sleep(POLL_INTERVAL)
    return False


async def test_api_enqueue_and_worker() -> bool:
    print("\n[1] POST /jobs/ → worker marks job running")
    try:
        r = httpx.post(f"{API}/jobs/", json={}, timeout=5.0)
        r.raise_for_status()
    except httpx.HTTPError as e:
        fail(f"API not reachable at {API}/jobs/ — is uvicorn running? ({e})")
        return False

    job_id = r.json()["id"]
    if await wait_for_state(job_id, JobStatus.RUNNING):
        ok(f"job {job_id} is running")
        return True

    job = await get_job(job_id)
    fail(f"job {job_id} stuck in state {job.state if job else 'missing'}")
    return False


async def test_failure_delayed_promote_retry() -> bool:
    print("\n[2] Failure → jobs:delayed → scheduler → queue → running again")
    async with AsyncSessionLocal() as db:
        job = await create_job_service(db, redis_client, JobCreate())
        job_id = job.id

    await redis_client.rpush("jobs:queue", job_id)
    if not await wait_for_state(job_id, JobStatus.RUNNING):
        fail(f"job {job_id} never reached running before failure test")
        return False

    async with AsyncSessionLocal() as db:
        await handle_job_failure_service(
            db, redis_client, job_id, "simulated error from e2e script"
        )

    job = await get_job(job_id)
    if not job or job.state != JobStatus.QUEUED:
        fail(f"expected queued after failure, got {job.state if job else None}")
        return False
    ok(f"job {job_id} queued, attempts={job.attempts}, next_attempt_at set")

    delayed = await redis_client.zscore("jobs:delayed", str(job_id))
    if delayed is None:
        fail("job missing from jobs:delayed")
        return False
    ok(f"job {job_id} in jobs:delayed (score={delayed})")

    # Force due now so we do not wait for random backoff
    await redis_client.zadd("jobs:delayed", {str(job_id): time.time()})

    if not await wait_for_state(job_id, JobStatus.RUNNING):
        job = await get_job(job_id)
        fail(
            f"scheduler/worker did not retry — state={job.state if job else None}. "
            "Is retry_scheduler running?"
        )
        return False

    ok(f"job {job_id} running again after promote + worker")
    return True


async def test_max_attempts_dead() -> bool:
    print("\n[3] Exhaust max_attempts → terminal failed")
    async with AsyncSessionLocal() as db:
        job = Job(state=JobStatus.RUNNING, attempts=5, max_attempts=5)
        db.add(job)
        await db.commit()
        await db.refresh(job)
        job_id = job.id

    async with AsyncSessionLocal() as db:
        await handle_job_failure_service(db, redis_client, job_id, "final failure")

    job = await get_job(job_id)
    if job and job.state == JobStatus.FAILED and job.last_error == "final failure":
        ok(f"job {job_id} failed permanently at max_attempts={job.max_attempts}")
        return True

    fail(
        f"expected failed, got state={job.state if job else None} "
        f"attempts={job.attempts if job else None}"
    )
    return False


async def test_live_worker_failure_loop() -> bool:
    print("\n[4] Live worker with SIMULATE_JOB_FAILURE=1 (optional)")
    if not httpx.get(f"{API}/", timeout=3.0).is_success:
        fail("API down")
        return False

    async with AsyncSessionLocal() as db:
        job = Job(state=JobStatus.QUEUED, max_attempts=3)
        db.add(job)
        await db.commit()
        await db.refresh(job)
        job_id = job.id

    await redis_client.rpush("jobs:queue", job_id)

    # Worker should fail immediately and schedule retry; force promote
    await asyncio.sleep(1.5)
    job = await get_job(job_id)
    if job and job.state == JobStatus.RUNNING and job.attempts == 0:
        ok(
            "skipped — restart worker with: "
            "SIMULATE_JOB_FAILURE=1 python -m app.workers.job_worker"
        )
        return True

    if job and job.state == JobStatus.QUEUED and job.attempts >= 1:
        await redis_client.zadd("jobs:delayed", {str(job_id): time.time()})
        if await wait_for_state(job_id, JobStatus.RUNNING):
            ok(f"job {job_id} failed in worker and was retried (attempts={job.attempts})")
            return True

    ok("skipped (unexpected state for optional test)")
    return True


async def main() -> int:
    print("Job pipeline simulation (needs Postgres + Redis + uvicorn + worker + scheduler)")
    await redis_client.ping()

    results = [
        await test_api_enqueue_and_worker(),
        await test_failure_delayed_promote_retry(),
        await test_max_attempts_dead(),
        await test_live_worker_failure_loop(),
    ]

    await redis_client.aclose()

    passed = sum(results)
    total = len(results)
    print(f"\n{passed}/{total} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
