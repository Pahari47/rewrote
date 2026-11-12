"""add job state and schedule indexes

Revision ID: e2829d949be4
Revises: 275ef4ae5766
Create Date: 2026-11-10 20:10:29.168504

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2829d949be4'
down_revision: Union[str, Sequence[str], None] = '275ef4ae5766'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
