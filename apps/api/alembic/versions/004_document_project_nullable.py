"""Make documents.project_id nullable for global knowledge base uploads.

Revision ID: 004
Revises: 003
"""
from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"  # conversations
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "documents",
        "project_id",
        existing_type=sa.UUID(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "documents",
        "project_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
