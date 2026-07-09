"""Add PRD §9.4 traceability fields to retrieval_logs.

Adds structured_query_json, retrieved_items_json, selected_context_json,
final_output_id, and triggered_by so every retrieval is fully traceable
(raw query → structured query → retrieved items → selected context → the
generation output that consumed it).

Revision ID: 008_retrieval_log
Revises: 007
"""
from alembic import op
import sqlalchemy as sa

revision = "008_retrieval_log"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "retrieval_logs",
        sa.Column("structured_query_json", sa.JSON(), nullable=True),
    )
    op.add_column(
        "retrieval_logs",
        sa.Column("retrieved_items_json", sa.JSON(), nullable=True),
    )
    op.add_column(
        "retrieval_logs",
        sa.Column("selected_context_json", sa.JSON(), nullable=True),
    )
    op.add_column(
        "retrieval_logs",
        sa.Column("final_output_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "retrieval_logs",
        sa.Column("triggered_by", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("retrieval_logs", "triggered_by")
    op.drop_column("retrieval_logs", "final_output_id")
    op.drop_column("retrieval_logs", "selected_context_json")
    op.drop_column("retrieval_logs", "retrieved_items_json")
    op.drop_column("retrieval_logs", "structured_query_json")
