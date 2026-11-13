from uuid import UUID
from pydantic import BaseModel, Field


class UploadRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=100)
    file_size: int | None = Field(default=None, gt=0)

class UploadResponse(BaseModel):
    file_id: UUID
    upload_url: str
    object_key: str
    method: str = "PUT"
    expires_in: int