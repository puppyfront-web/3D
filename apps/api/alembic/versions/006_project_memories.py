"""Create project_memories + conversation_states (presale memory layer).

Revision ID: 006
Revises: 005

Implements PRESALE_DELIVERY_SPEC §7.2 memory layer:
- project_memories: per-project, per-type digest (canvas_digest, confirmed_facts)
- conversation_states: per-conversation/thread ephemeral state (last_web_hits)

Both UNIQUE on their natural key so the service layer can upsert without
read-then-write races.
"""

from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_memories",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(32),
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
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.String(32),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "thread_id",
            sa.String(32),
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


def downgrade() -> None:
    op.drop_index("ix_conversation_states_conversation_id", table_name="conversation_states")
    op.drop_table("conversation_states")
    op.drop_index("ix_project_memories_project_id", table_name="project_memories")
    op.drop_table("project_memories")
