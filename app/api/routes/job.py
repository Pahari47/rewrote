
from fastapi import APIRouter, Depends, Header, Query, Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_redis
from app.database import get_db
from app.schemas.job import JobCreate, JobResponse
from app.services.job import create_job_service, list_dead_jobs_service, requeue_dead_job_service


router = APIRouter(
    prefix="/jobs",
    tags=["jobs"],
)

@router.post("/", response_model=JobResponse, status_code=201)
async def create_job(
    job_data: JobCreate,
    response: Response,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=255),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    job, created = await create_job_service(db, redis, job_data, idempotency_key)

    response.status_code = 201 if created else 200
    return job

@router.get("/dead", response_model=list[JobResponse])
async def list_dead_jobs(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await list_dead_jobs_service(db, limit, offset)

@router.post("/{job_id}/requeue", response_model=JobResponse)
async def requeue_dead_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    return await requeue_dead_job_service(db, redis, job_id)
