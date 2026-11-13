import uuid
from sqlalchemy import DateTime, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import BigInteger, String
from app.database import Base


class Media(Base):
    __tablename__ = "media"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    object_key: Mapped[str] = mapped_column(String(512), unique=True, nullable=False, index=True)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
