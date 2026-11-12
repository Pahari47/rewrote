
from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_redis
from app.database import get_db
from app.services.metrics import collect_matrics


router = APIRouter(tags=["metrics"])

@router.get("/metrics")
async def metrics(db: AsyncSession = Depends(get_db), redis: Redis = Depends(get_redis)):
    return await collect_matrics(db, redis)