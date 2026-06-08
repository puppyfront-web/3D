"""Add material_spec, lighting_spec to visual_styles.

Revision ID: 007
Revises: 006
"""
from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "visual_styles",
        sa.Column("material_spec", sa.JSON(), nullable=True, comment="材质规范参数"),
    )
    op.add_column(
        "visual_styles",
        sa.Column("lighting_spec", sa.JSON(), nullable=True, comment="灯光规范参数"),
    )


def downgrade() -> None:
    op.drop_column("visual_styles", "lighting_spec")
    op.drop_column("visual_styles", "material_spec")
