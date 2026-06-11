"""Add screen_info and preferences to projects.

screen_info holds the venue & screen parameters (size/type/pitch/install
environment/viewing distance) that are domain-critical inputs for 3D-wall
generation. preferences captures wizard step3/4/5 project-level config.

Revision ID: 011
Revises: 010
"""
from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("screen_info", sa.JSON(), nullable=True, comment="场地与屏幕结构化参数"),
    )
    op.add_column(
        "projects",
        sa.Column("preferences", sa.JSON(), nullable=True, comment="向导 step3/4/5 项目级配置"),
    )


def downgrade() -> None:
    op.drop_column("projects", "preferences")
    op.drop_column("projects", "screen_info")
