"""Eval tables for KB-Case-Delivery."""

from alembic import op
import sqlalchemy as sa

revision = "022_eval_tables"
down_revision = "021_retrieval_trace"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "eval_sets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_eval_sets_project_id", "eval_sets", ["project_id"])

    op.create_table(
        "eval_cases",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("set_id", sa.Uuid(), sa.ForeignKey("eval_sets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("expected_chunk_ids", sa.JSON(), nullable=True),
        sa.Column("expected_document_ids", sa.JSON(), nullable=True),
        sa.Column("expected_keywords", sa.JSON(), nullable=True),
        sa.Column("must_not_keywords", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("source", sa.String(32), nullable=False, server_default="manual"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_eval_cases_set_id", "eval_cases", ["set_id"])

    op.create_table(
        "eval_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("set_id", sa.Uuid(), sa.ForeignKey("eval_sets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="running"),
        sa.Column("config_snapshot_json", sa.JSON(), nullable=True),
        sa.Column("metrics_json", sa.JSON(), nullable=True),
        sa.Column("per_case_results_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_eval_runs_set_id", "eval_runs", ["set_id"])


def downgrade() -> None:
    op.drop_index("ix_eval_runs_set_id", table_name="eval_runs")
    op.drop_table("eval_runs")
    op.drop_index("ix_eval_cases_set_id", table_name="eval_cases")
    op.drop_table("eval_cases")
    op.drop_index("ix_eval_sets_project_id", table_name="eval_sets")
    op.drop_table("eval_sets")
