"""Presale memory layer + operation_runs observability.

Revision ID: 020_presale_memory
Revises: 019_knowledge_asset_revisions

Consolidates previously conflicting 006/007 revisions that could not run
alongside company_profile / visual_style migrations. Requires
conversation_threads (015) for conversation_states.thread_id FK.
"""

from alembic import op
import sqlalchemy as sa

revision = "020_presale_memory"
down_revision = "019_knowledge_asset_revisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_memories",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("memory_type", sa.String(64), nullable=False),
        sa.Column("memory_json", sa.JSON, nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "project_id", "memory_type", name="uq_project_memory_type"
        ),
    )
    op.create_index(
        "ix_project_memories_project_id",
        "project_memories",
        ["project_id"],
    )

    op.create_table(
        "conversation_states",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "thread_id",
            sa.Uuid(),
            sa.ForeignKey("conversation_threads.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("state_key", sa.String(64), nullable=False),
        sa.Column("state_json", sa.JSON, nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "conversation_id",
            "thread_id",
            "state_key",
            name="uq_conversation_state_key",
        ),
    )
    op.create_index(
        "ix_conversation_states_conversation_id",
        "conversation_states",
        ["conversation_id"],
    )

    op.create_table(
        "operation_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
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
    op.drop_index("ix_conversation_states_conversation_id", table_name="conversation_states")
    op.drop_table("conversation_states")
    op.drop_index("ix_project_memories_project_id", table_name="project_memories")
    op.drop_table("project_memories")
