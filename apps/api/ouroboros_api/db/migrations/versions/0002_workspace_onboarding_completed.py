"""add workspace onboarding completion timestamp

Revision ID: 0002_workspace_onboarding_completed
Revises: 0001_initial
Create Date: 2026-04-19

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_workspace_onboarding_completed"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("workspaces", sa.Column("onboarding_completed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("workspaces", "onboarding_completed_at")
