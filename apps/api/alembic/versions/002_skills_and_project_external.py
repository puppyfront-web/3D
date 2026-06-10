"""Add skills table, skill_executions table, and project external fields.

Revision ID: 002_skills_external
Revises: 001_initial
Create Date: 2024-06-05 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision: str = "002_skills_external"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add skills, skill_executions tables and project external portal fields."""

    # --- skills table ---
    op.create_table(
        "skills",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("skill_id", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("manifest_json", sa.JSON(), nullable=True),
        sa.Column("input_schema_json", sa.JSON(), nullable=True),
        sa.Column("output_schema_json", sa.JSON(), nullable=True),
        sa.Column("required_services_json", sa.JSON(), nullable=True),
        sa.Column("permissions_json", sa.JSON(), nullable=True),
        sa.Column("visibility", sa.String(50), server_default="internal", nullable=False),
        sa.Column("version", sa.String(50), server_default="1.0.0", nullable=False),
        sa.Column("status", sa.String(50), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- skill_executions table ---
    op.create_table(
        "skill_executions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("skill_id", sa.Uuid(), sa.ForeignKey("skills.id"), nullable=False, index=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=True, index=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True, index=True),
        sa.Column("input_json", sa.JSON(), nullable=True),
        sa.Column("output_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(50), server_default="running", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("used_cases", sa.JSON(), nullable=True),
        sa.Column("used_documents", sa.JSON(), nullable=True),
        sa.Column("used_chunks", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- project external portal fields ---
    op.add_column("projects", sa.Column("external_token", sa.String(255), nullable=True, unique=True))
    op.add_column("projects", sa.Column("external_status", sa.String(50), nullable=True))
    op.add_column("projects", sa.Column("shared_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("projects", sa.Column("approved_for_external", sa.Boolean(), server_default="false", nullable=False))

    # --- pgvector HNSW index (PostgreSQL only) ---
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "CREATE INDEX IF NOT EXISTS idx_chunks_embedding "
            "ON document_chunks USING hnsw (embedding vector_cosine_ops)"
        )


def downgrade() -> None:
    """Remove skills, skill_executions and project external fields."""
    op.drop_table("skill_executions")
    op.drop_table("skills")
    op.drop_column("projects", "approved_for_external")
    op.drop_column("projects", "shared_at")
    op.drop_column("projects", "external_status")
    op.drop_column("projects", "external_token")
