from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field


class TransformRequest(BaseModel):
    file_id: UUID
    width: int = Field(
        default=1024,
        gt=0,
        le=4096
    )
    height: int = Field(
        default=1024,
        gt=0,
        le=4096
    )

    output_format: Literal[
        "jpeg",
        "png",
        "webp"
    ] = "webp"

class TransformResponse(BaseModel):
    job_id: UUID
    status: str

class TransformStatusResponse(BaseModel):
    job_id: UUID
    file_id: UUID
    status: str
    output_key: str | None
    error_message: str | None