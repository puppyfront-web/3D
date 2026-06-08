"""Add pipeline_stages to sop_workflows.

Revision ID: 008
Revises: 007
"""
from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sop_workflows",
        sa.Column("pipeline_stages", sa.JSON(), nullable=True, comment="Pipeline 阶段定义"),
    )


def downgrade() -> None:
    op.drop_column("sop_workflows", "pipeline_stages")
