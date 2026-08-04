"""Add external-source traceability columns.

Adds used_external_sources + external_search_summary to two tables:
  - generation_outputs  (final artifact provenance)
  - skill_executions    (per-skill-run provenance, mirrors SkillResult)

Both are nullable JSON so existing rows are unaffected. Required for
traceability of any non-internal information per AGENT_SPEC §2.3 and the
web-search-tool-boundary spec (2026-06-25).

Revision ID: 013
Revises: 012
"""
from alembic import op
import sqlalchemy as sa

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # generation_outputs
    op.add_column(
        "generation_outputs",
        sa.Column("used_external_sources", sa.JSON(), nullable=True),
    )
    op.add_column(
        "generation_outputs",
        sa.Column("external_search_summary", sa.JSON(), nullable=True),
    )
    # skill_executions
    op.add_column(
        "skill_executions",
        sa.Column("used_external_sources", sa.JSON(), nullable=True),
    )
    op.add_column(
        "skill_executions",
        sa.Column("external_search_summary", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("skill_executions", "external_search_summary")
    op.drop_column("skill_executions", "used_external_sources")
    op.drop_column("generation_outputs", "external_search_summary")
    op.drop_column("generation_outputs", "used_external_sources")

