from uuid import UUID
from pydantic import BaseModel, Field


class UploadRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)

class UploadResponse(BaseModel):
    file_id: UUID
    upload_url: str
    fields: dict[str, str]
    object_key: str
    file_size: int | None = None
    expires_in: int

class CompleteUploadResponse(BaseModel):
    file_id: UUID
    status: str
    content_type: str
    file_size: int | None = None