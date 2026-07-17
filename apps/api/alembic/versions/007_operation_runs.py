"""Create operation_runs (presale observability parent).

Revision ID: 007
Revises: 006

PRESALE_DELIVERY_SPEC §11.2 — minimal P2 parent record for the chat auto-fill
turn. Carries a denormalised ``steps`` JSON list (web_search / canvas_fill /
skill_execute / persist / memory_write) so a single row indexes a whole turn
without joining 4 child tables.
"""

from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operation_runs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(32),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            sa.String(32),
            sa.ForeignKey("conversations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("operation_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), server_default="running", nullable=False),
        sa.Column("steps", sa.JSON, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_operation_runs_project_id", "operation_runs", ["project_id"]
    )
    op.create_index(
        "ix_operation_runs_conversation_id", "operation_runs", ["conversation_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_operation_runs_conversation_id", table_name="operation_runs")
    op.drop_index("ix_operation_runs_project_id", table_name="operation_runs")
    op.drop_table("operation_runs")
