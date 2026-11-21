from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.transform import (
    AVTransformRequest,
    TransformRequest,
    TransformResponse,
    TransformStatusResponse,
)
from app.services.transform import (
    create_av_transform as create_av_transform_service,
    create_transform as create_transform_service,
    get_transform_status as get_transform_status_service,
)


router = APIRouter(
    prefix="/transform",
    tags=["transform"],
)

@router.post("/", response_model=TransformResponse)
async def create_transform(
    payload: TransformRequest,
    db: AsyncSession = Depends(get_db)
):
    return await create_transform_service(payload, db)

@router.post("/av", response_model=TransformResponse)
async def create_av_transform(
    payload: AVTransformRequest,
    db: AsyncSession = Depends(get_db),
):
    return await create_av_transform_service(payload, db)

@router.get("/{job_id}", response_model=TransformStatusResponse)
async def get_transform_status(
    job_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    return await get_transform_status_service(job_id, db)