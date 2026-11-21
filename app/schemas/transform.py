from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field, model_validator


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


class AVTransformRequest(BaseModel):
    file_id: UUID
    output_format: Literal["mp4", "webm", "mp3", "aac", "wav"] = "mp4"
    width: int | None = Field(default=None, gt=0, le=3840)
    height: int | None = Field(default=None, gt=0, le=2160)
    timeout_seconds: int = Field(default=120, gt=0, le=600)

    @model_validator(mode="after")
    def scale_is_a_pair(self):
        if (self.width is None) != (self.height is None):
            raise ValueError("width and height must both be set or both omitted")
        return self