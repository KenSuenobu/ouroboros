"""add run snapshot json column

Revision ID: 0005_run_snapshot_and_interrupted_status
Revises: 0004_seed_agent_router_language_hints
Create Date: 2026-04-20

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_run_snapshot_and_interrupted_status"
down_revision = "0004_seed_agent_router_language_hints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("runs") as batch_op:
        batch_op.add_column(
            sa.Column("snapshot_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'"))
        )


def downgrade() -> None:
    with op.batch_alter_table("runs") as batch_op:
        batch_op.drop_column("snapshot_json")
