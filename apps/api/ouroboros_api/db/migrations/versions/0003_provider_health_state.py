"""add provider health status columns

Revision ID: 0003_provider_health_state
Revises: 0002_workspace_onboarding_completed
Create Date: 2026-04-19

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_provider_health_state"
down_revision = "0002_workspace_onboarding_completed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("providers", sa.Column("last_health_status", sa.String(length=32), nullable=True))
    op.add_column("providers", sa.Column("last_health_error", sa.Text(), nullable=True))
    op.add_column("providers", sa.Column("last_health_checked_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("providers", "last_health_checked_at")
    op.drop_column("providers", "last_health_error")
    op.drop_column("providers", "last_health_status")
