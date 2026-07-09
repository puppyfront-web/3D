"""Add pipeline_stages to sop_workflows.

Revision ID: 008_sop_stages
Revises: 008_retrieval_log_prd_fields
"""
from alembic import op
import sqlalchemy as sa

revision = "008_sop_stages"
down_revision = "008_retrieval_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sop_workflows",
        sa.Column("pipeline_stages", sa.JSON(), nullable=True, comment="Pipeline 阶段定义"),
    )


def downgrade() -> None:
    op.drop_column("sop_workflows", "pipeline_stages")
