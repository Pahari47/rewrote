
import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import uuid
from fastapi import HTTPException
from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import Job, JobStatus
from app.schemas.job import JobCreate, JobResponse
from app.utils.retry import calaculate_retry_delay

logger = get_logger(__name__)

JOBS_QUEUE = "jobs:queue"
JOBS_DELAYED = "jobs:delayed"
JOBS_DEAD = "jobs:dead"

IDEMPOTENCY_TTL = 86400  # 24 hours

LEASE_TTL = 30
LEASE_RENEW_INTERVAL = 10

RELEASE_LOCK_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
"""

async def claim_job(db: AsyncSession, job_id: int, worker_id: str) -> str | None:
    lease_token = str(uuid.uuid4())

    now = datetime.now(timezone.utc)
    lease_expiry = now + timedelta(seconds=LEASE_TTL)

    statement = (
        update(Job).where(
            Job.id == job_id,
            Job.state == JobStatus.QUEUED,
            Job.attempts < Job.max_attempts,
        ).values(
            state=JobStatus.RUNNING,
            attempts=Job.attempts + 1,
            lease_owner=worker_id,
            lease_token=lease_token,
            lease_expires_at=lease_expiry,
            next_attempt_at=None,
        ).returning(Job.id)
    )

    result = await db.execute(statement)
    claimed_job_id = result.scalar_one_or_none()

    await db.commit()

    if claimed_job_id is None:
        return None

    print(
        f"Worker {worker_id} claimed job {job_id}. "
        f"Lease expires at {lease_expiry}"
    )

    return lease_token

async def renew_lease(db: AsyncSession, job_id: int, worker_id: str, lease_token: str) -> bool:
    now = datetime.now(timezone.utc)
    lease_expiry = now + timedelta(seconds=LEASE_TTL)

    statement = (
        update(Job).where(
            Job.id == job_id,
            Job.lease_owner == worker_id,
            Job.lease_token == lease_token,
            Job.state == JobStatus.RUNNING,
            Job.lease_expires_at > now,
        ).values(
            lease_expires_at=lease_expiry,
        ).returning(Job.id)
    )

    result = await db.execute(statement)
    renewed_job_id = result.scalar_one_or_none()

    await db.commit()

    if renewed_job_id is None:
        return False

    print(f"Worker {worker_id} renewed lease for job {job_id}")
    return True


async def reap_expired_leases(db: AsyncSession, redis: Redis) -> int:
    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(Job).where(
            Job.state == JobStatus.RUNNING,
            Job.lease_expires_at.isnot(None),
            Job.lease_expires_at < now,
        )
    )
    jobs = result.scalars().all()
    count = 0

    for job in jobs:
        job.lease_owner = None
        job.lease_token = None
        job.lease_expires_at = None
        job.last_error = job.last_error or "Lease expired"
        
        if job.attempts >= job.max_attempts:
            job.state = JobStatus.DEAD
            job.next_attempt_at = None
            await redis.rpush(JOBS_DEAD, str(job.id))
        else:
            delay = calaculate_retry_delay(job.attempts)
            retry_at = now + timedelta(seconds=delay)
            job.state = JobStatus.QUEUED
            job.next_attempt_at = retry_at
            await redis.zadd(JOBS_DELAYED, {str(job.id): retry_at.timestamp()})
            print(f"Job with id {job.id} will be retried at {retry_at}")

        count += 1

    if count:
        await db.commit()

    return count

def get_request_hash(job_data: JobCreate) -> str:
    payload = json.dumps(
        job_data.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(payload.encode()).hexdigest()

async def find_job_by_idempotency_key(db: AsyncSession, idempotency_key: str):
    result = await db.execute(
        select(Job).where(Job.idempotency_key == idempotency_key)
    )

    return result.scalar_one_or_none()

def validate_job_idempotency(job: Job, request_hash: str):
    if job.request_hash != request_hash:
        raise HTTPException(status_code=400, detail="Idempotency key mismatch")

async def create_job_service(
    db: AsyncSession,
    redis: Redis,
    job_data: JobCreate,
    idempotency_key: str
) -> tuple[Job, bool]:

    request_hash = get_request_hash(job_data)

    key_hash = hashlib.sha256(idempotency_key.encode()).hexdigest()

    cache_key = f"job:idempotency:{key_hash}"
    lock_key = f"{cache_key}:lock"

    # check redis cache for job
    cached_job_id = await redis.get(cache_key)

    if cached_job_id:
        cached_job = await db.get(Job, int(cached_job_id))

        if cached_job:
            validate_job_idempotency(cached_job, request_hash)
            return cached_job, False

    # remove stale cache entry
    await redis.delete(cache_key)

    # acquire lock
    lock_token = str(uuid.uuid4())

    lock_acquired = await redis.set(lock_key, lock_token, nx=True, ex=30)

    if not lock_acquired:
        for _ in range(20):
            await asyncio.sleep(0.1)

            existing_job = await find_job_by_idempotency_key(db, idempotency_key)
            if existing_job:
                validate_job_idempotency(existing_job, request_hash)

                await redis.set(cache_key, str(existing_job.id), ex=IDEMPOTENCY_TTL)
                return existing_job, False
        
        raise HTTPException(status_code=409, detail="Request is already being processed, retry shortly")
    
    try:
        # check db
        existing_job = await find_job_by_idempotency_key(db, idempotency_key)
        if existing_job:
            validate_job_idempotency(existing_job, request_hash)

            await redis.set(cache_key, str(existing_job.id), ex=IDEMPOTENCY_TTL)
            return existing_job, False
        
        # create new job
        new_job = Job(
            state=job_data.state,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
        )
        db.add(new_job)

        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()

            existing_job = await find_job_by_idempotency_key(db, idempotency_key)

            if existing_job is None:
                raise

            validate_job_idempotency(existing_job, request_hash)

            await redis.set(cache_key, str(existing_job.id), ex=IDEMPOTENCY_TTL)
            return existing_job, False

        await db.refresh(new_job)

        await redis.rpush(JOBS_QUEUE, str(new_job.id))

        await redis.set(cache_key, str(new_job.id), ex=IDEMPOTENCY_TTL)
        return new_job, True

    finally:
        # release lock
        await redis.eval(RELEASE_LOCK_SCRIPT, 1, lock_key, lock_token)
    

async def mark_job_as_running_service(
    db: AsyncSession,
    job_id: int,
):
    job = await db.get(Job, job_id)

    if job is None:
        print(f"Job with id {job_id} not found")
        return

    job.state = JobStatus.RUNNING
    await db.commit()

    print(f"Job with id {job_id} marked as running")

async def handle_job_failure_service(
    db: AsyncSession,
    redis: Redis,
    job_id: int,
    worker_id: str,
    lease_token: str,
    error: str,
) -> bool:
    job = await db.get(Job, job_id)

    if job is None:
        print(f"Job with id {job_id} not found")
        return False

    if job.state != JobStatus.RUNNING:
        print(f"Worker {worker_id} lost lease failing job {job_id} (state is {job.state})")
        return False

    if job.lease_owner != worker_id or job.lease_token != lease_token:
        print(f"Worker {worker_id} lost lease failing job {job_id}")
        return False

    job.last_error = error
    job.lease_owner = None
    job.lease_token = None
    job.lease_expires_at = None

    # Out of retries
    if job.attempts >= job.max_attempts:
        job.last_error = error
        await move_job_to_dead_queue(db, redis, job)
        print(f"Job with id {job_id} dead after {job.attempts} attempts")
        return True

    delay = calaculate_retry_delay(job.attempts)
    retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)

    job.state = JobStatus.QUEUED
    job.next_attempt_at = retry_at

    await db.commit()
    await redis.zadd(JOBS_DELAYED, {str(job_id): retry_at.timestamp()})
    print(f"Job with id {job_id} will be retried at {retry_at}")
    return True


async def execute_job_simulation_service(db: AsyncSession, worker_id: str, job_id: int, lease_token: str) -> None:
    total = float(os.getenv("JOB_SIMULATION_DELAY", "3"))
    elapsed = 0.0
    while elapsed < total:
        chunk = min(LEASE_RENEW_INTERVAL, total - elapsed)
        await asyncio.sleep(chunk)
        elapsed += chunk
        if elapsed < total or total > LEASE_TTL:
            await renew_lease(db, job_id, worker_id, lease_token)
    if os.getenv("SIMULATE_JOB_FAILURE") == "1":
        raise RuntimeError("simulated failure for testing")


async def complete_job_service(
    db: AsyncSession,
    worker_id: str,
    job_id: int,
    lease_token: str,
) -> bool:
    statement = (
        update(Job)
        .where(
            Job.id == job_id,
            Job.lease_owner == worker_id,
            Job.lease_token == lease_token,
            Job.state == JobStatus.RUNNING,
        )
        .values(
            state=JobStatus.SUCCEEDED,
            lease_owner=None,
            lease_token=None,
            lease_expires_at=None,
        )
        .returning(Job.id)
    )
    result = await db.execute(statement)
    completed_id = result.scalar_one_or_none()
    await db.commit()

    if completed_id is None:
        print(f"Worker {worker_id} lost lease completing job {job_id}")
        return False

    print(f"Job with id {job_id} completed by worker {worker_id}")
    return True


async def move_job_to_dead_queue(db: AsyncSession, redis: Redis, job: Job) -> None:
    job.state = JobStatus.DEAD
    job.next_attempt_at = None
    job.lease_owner = None
    job.lease_token = None
    job.lease_expires_at = None
    await db.commit()
    await redis.rpush(JOBS_DEAD, str(job.id))
    print(f"Job with id {job.id} moved to dead-letter queue")

async def list_dead_jobs_service(db: AsyncSession, limit: int = 50, offset: int = 0) -> list[Job]:
    result = await db.execute(
        select(Job).where(Job.state == JobStatus.DEAD)
        .order_by(Job.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())

async def requeue_dead_job_service(db: AsyncSession, redis: Redis, job_id: int) -> Job:
    job = await db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.state != JobStatus.DEAD:
        raise HTTPException(status_code=409, detail=f"Job is not dead (state={job.state.value})")

    job.state = JobStatus.QUEUED
    job.attempts = 0
    job.last_error = None
    job.next_attempt_at = None
    job.lease_owner = None
    job.lease_token = None
    job.lease_expires_at = None

    await db.commit()
    await db.refresh(job)

    await redis.lrem(JOBS_DEAD, 0, str(job_id))
    await redis.zrem(JOBS_DELAYED, str(job_id))
    await redis.rpush(JOBS_QUEUE, str(job_id))
    print(f"Job with id {job_id} requeued from dead-letter queue")
    return job