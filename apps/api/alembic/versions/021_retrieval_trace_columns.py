"""Retrieval log trace columns for Q&A and Eval (KB-Case-Delivery)."""

from alembic import op
import sqlalchemy as sa

revision = "021_retrieval_trace"
down_revision = "020_presale_memory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "retrieval_logs",
        sa.Column("project_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "retrieval_logs",
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "retrieval_logs",
        sa.Column("message_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "retrieval_logs",
        sa.Column("eval_run_id", sa.Uuid(), nullable=True),
    )
    op.create_index("ix_retrieval_logs_project_id", "retrieval_logs", ["project_id"])
    op.create_index(
        "ix_retrieval_logs_conversation_id", "retrieval_logs", ["conversation_id"]
    )
    op.create_index("ix_retrieval_logs_message_id", "retrieval_logs", ["message_id"])


def downgrade() -> None:
    op.drop_index("ix_retrieval_logs_message_id", table_name="retrieval_logs")
    op.drop_index("ix_retrieval_logs_conversation_id", table_name="retrieval_logs")
    op.drop_index("ix_retrieval_logs_project_id", table_name="retrieval_logs")
    op.drop_column("retrieval_logs", "eval_run_id")
    op.drop_column("retrieval_logs", "message_id")
    op.drop_column("retrieval_logs", "conversation_id")
    op.drop_column("retrieval_logs", "project_id")
