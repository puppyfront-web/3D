"""Add reference_images to cases.

Revision ID: 009
Revises: 008
"""
from alembic import op
import sqlalchemy as sa

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "cases",
        sa.Column("reference_images", sa.JSON(), nullable=True, comment="参考图片列表"),
    )


def downgrade() -> None:
    op.drop_column("cases", "reference_images")
