"""Add conversation threads and message thread pointers.

Revision ID: 015_conversation_threads
Revises: 014
"""

from alembic import op
import sqlalchemy as sa

revision = "015_conversation_threads"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversation_threads",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scope_type", sa.String(length=20), nullable=False),
        sa.Column("scope_ref_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_conversation_threads_conversation_id", "conversation_threads", ["conversation_id"])
    op.create_index("ix_conversation_threads_scope_type", "conversation_threads", ["scope_type"])
    op.create_index("ix_conversation_threads_scope_ref_id", "conversation_threads", ["scope_ref_id"])
    op.create_index("ix_conversation_threads_status", "conversation_threads", ["status"])
    op.create_index(
        "ux_conversation_threads_scope",
        "conversation_threads",
        ["conversation_id", "scope_type", "scope_ref_id"],
        unique=True,
    )

    op.add_column("messages", sa.Column("thread_id", sa.Uuid(), nullable=True))
    op.create_index("ix_messages_thread_id", "messages", ["thread_id"])
    op.create_foreign_key(
        "fk_messages_thread_id",
        "messages",
        "conversation_threads",
        ["thread_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_messages_thread_id", "messages", type_="foreignkey")
    op.drop_index("ix_messages_thread_id", table_name="messages")
    op.drop_column("messages", "thread_id")

    op.drop_index("ux_conversation_threads_scope", table_name="conversation_threads")
    op.drop_index("ix_conversation_threads_status", table_name="conversation_threads")
    op.drop_index("ix_conversation_threads_scope_ref_id", table_name="conversation_threads")
    op.drop_index("ix_conversation_threads_scope_type", table_name="conversation_threads")
    op.drop_index("ix_conversation_threads_conversation_id", table_name="conversation_threads")
    op.drop_table("conversation_threads")
