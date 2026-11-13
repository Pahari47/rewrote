"""create media table and restore job indexes

Revision ID: c4a8f1e2b3d0
Revises: b7c72d19ea33
Create Date: 2026-11-13 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4a8f1e2b3d0"
down_revision: Union[str, Sequence[str], None] = "b7c72d19ea33"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "media",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_media_object_key"), "media", ["object_key"], unique=True)

    op.create_index(
        "ix_jobs_state_next_attempt_at",
        "jobs",
        ["state", "next_attempt_at"],
        unique=False,
    )
    op.create_index(
        "ix_jobs_state_lease_expires_at",
        "jobs",
        ["state", "lease_expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_jobs_state_lease_expires_at", table_name="jobs")
    op.drop_index("ix_jobs_state_next_attempt_at", table_name="jobs")
    op.drop_index(op.f("ix_media_object_key"), table_name="media")
    op.drop_table("media")
