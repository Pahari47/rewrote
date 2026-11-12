import datetime
from sqlalchemy import DateTime, Integer, Enum as SQLAlchemyEnum, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from enum import Enum

class JobStatus(str,Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEAD = "dead"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    state: Mapped[JobStatus] = mapped_column(SQLAlchemyEnum(JobStatus, name="job_status", values_callable=lambda enum_cls: [e.value for e in enum_cls]), default=JobStatus.QUEUED, nullable=False)

    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    next_attempt_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    request_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    lease_owner: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lease_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    lease_expires_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
