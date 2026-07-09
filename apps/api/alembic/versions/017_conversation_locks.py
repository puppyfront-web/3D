"""Add conversation_locks table for per-conversation chat serialization.

Revision ID: 017_conversation_locks
Revises: 016_admin_kb_expansion
"""

from alembic import op
import sqlalchemy as sa

revision = "017_conversation_locks"
down_revision = "016_admin_kb_expansion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversation_locks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("holder", sa.String(length=64), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    # One active lock per conversation — the unique index is the mutual-exclusion
    # mechanism (INSERT ... ON CONFLICT DO NOTHING).
    op.create_index(
        "ux_conversation_locks_conversation_id",
        "conversation_locks",
        ["conversation_id"],
        unique=True,
    )
    op.create_index("ix_conversation_locks_expires_at", "conversation_locks", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_conversation_locks_expires_at", table_name="conversation_locks")
    op.drop_index("ux_conversation_locks_conversation_id", table_name="conversation_locks")
    op.drop_table("conversation_locks")
