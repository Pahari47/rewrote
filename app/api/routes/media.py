from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.media import UploadRequest, UploadResponse
from app.services.media import create_media_upload

router = APIRouter(
    prefix="/media",
    tags=["media"],
)


@router.post("/upload", response_model=UploadResponse)
async def upload_media(
    payload: UploadRequest,
    db: AsyncSession = Depends(get_db),
):
    return await create_media_upload(db, payload)
