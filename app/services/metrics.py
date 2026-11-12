from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Job, JobStatus
from app.services.job import JOBS_DEAD, JOBS_DELAYED, JOBS_QUEUE


async def collect_matrics(db: AsyncSession, redis: Redis) -> dict:
    queue_depth = await redis.llen(JOBS_QUEUE)
    delayed_depth = await redis.zcard(JOBS_DELAYED)
    dead_depth = await redis.llen(JOBS_DEAD)

    result = await db.execute(
        select(Job.state, func.count()).group_by(Job.state)
    )
    by_state = {row[0]: row[1] for row in result}

    failures = by_state.get(JobStatus.DEAD.value, 0) + by_state.get(JobStatus.FAILED.value, 0)
    return {
        "queue_depth": queue_depth,
        "delayed_depth": delayed_depth,
        "dead_depth": dead_depth,
        "jobs_by_state": by_state,
        "failures": failures,
    }