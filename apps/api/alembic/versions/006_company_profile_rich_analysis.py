"""Add six_views, technology_arch, project_background to company_profiles.

Revision ID: 006
Revises: 005
"""
from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "company_profiles",
        sa.Column("six_views", sa.JSON(), nullable=True, comment="企业六看结构化分析"),
    )
    op.add_column(
        "company_profiles",
        sa.Column("technology_arch", sa.JSON(), nullable=True, comment="技术一张图（分层架构）"),
    )
    op.add_column(
        "company_profiles",
        sa.Column("project_background", sa.JSON(), nullable=True, comment="项目背景（宏观→中观→微观）"),
    )


def downgrade() -> None:
    op.drop_column("company_profiles", "project_background")
    op.drop_column("company_profiles", "technology_arch")
    op.drop_column("company_profiles", "six_views")
