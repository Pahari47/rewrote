import datetime
from pydantic import BaseModel, ConfigDict

from app.models import JobStatus

class JobCreate(BaseModel):
    state: JobStatus = JobStatus.QUEUED

class JobResponse(BaseModel):
    id: int
    state: JobStatus
    attempts: int
    max_attempts: int
    last_error: str | None
    next_attempt_at: datetime.datetime | None

    model_config = ConfigDict(from_attributes=True)