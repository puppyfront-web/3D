"""Admin knowledge-base expansion: new columns + 3 new tables.

Adds fields to support richer admin management (PRD §12) and introduces
three new knowledge bases: industry materials, talking points, and
pricing experiences.

Revision ID: 016_admin_kb_expansion
Revises: 015_conversation_threads
"""

from alembic import op
import sqlalchemy as sa

revision = "016_admin_kb_expansion"
down_revision = "015_conversation_threads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Extend existing tables ────────────────────────────────────────────

    # documents: attachment category + finer-grained parse status
    op.add_column("documents", sa.Column("category", sa.String(length=50), nullable=True))
    op.add_column(
        "documents",
        sa.Column("parse_status", sa.String(length=50), nullable=True, server_default="uploaded"),
    )
    op.create_index("ix_documents_category", "documents", ["category"])
    op.create_index("ix_documents_parse_status", "documents", ["parse_status"])

    # cases: project type, style tag, desensitization support
    op.add_column("cases", sa.Column("project_type", sa.String(length=100), nullable=True))
    op.add_column("cases", sa.Column("style_tag", sa.String(length=100), nullable=True))
    op.add_column(
        "cases",
        sa.Column("is_desensitized", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("cases", sa.Column("original_client_name", sa.String(length=255), nullable=True))
    op.create_index("ix_cases_project_type", "cases", ["project_type"])

    # sop_workflows: categorization + agent binding + version note
    op.add_column("sop_workflows", sa.Column("category", sa.String(length=100), nullable=True))
    op.add_column("sop_workflows", sa.Column("bound_agent", sa.String(length=100), nullable=True))
    op.add_column("sop_workflows", sa.Column("version_note", sa.Text(), nullable=True))
    op.create_index("ix_sop_workflows_category", "sop_workflows", ["category"])

    # visual_styles: categorization, active flag, UI sub-type
    op.add_column("visual_styles", sa.Column("category", sa.String(length=100), nullable=True))
    op.add_column(
        "visual_styles",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column("visual_styles", sa.Column("sub_type", sa.String(length=50), nullable=True))
    op.create_index("ix_visual_styles_category", "visual_styles", ["category"])
    op.create_index("ix_visual_styles_is_active", "visual_styles", ["is_active"])

    # proposal_templates: industry classification
    op.add_column("proposal_templates", sa.Column("industry", sa.String(length=100), nullable=True))
    op.create_index("ix_proposal_templates_industry", "proposal_templates", ["industry"])

    # ── New tables ────────────────────────────────────────────────────────

    op.create_table(
        "industry_materials",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("industry", sa.String(length=100), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_industry_materials_industry", "industry_materials", ["industry"])
    op.create_index("ix_industry_materials_category", "industry_materials", ["category"])

    op.create_table(
        "talking_points",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("scenario", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("industry", sa.String(length=100), nullable=True),
        sa.Column("tags", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_talking_points_industry", "talking_points", ["industry"])
    op.create_index("ix_talking_points_scenario", "talking_points", ["scenario"])

    op.create_table(
        "pricing_experiences",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("industry", sa.String(length=100), nullable=True),
        sa.Column("project_type", sa.String(length=100), nullable=True),
        sa.Column("budget_range", sa.String(length=100), nullable=True),
        sa.Column("duration", sa.String(length=100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_pricing_experiences_industry", "pricing_experiences", ["industry"])
    op.create_index("ix_pricing_experiences_project_type", "pricing_experiences", ["project_type"])


def downgrade() -> None:
    # New tables
    op.drop_index("ix_pricing_experiences_project_type", table_name="pricing_experiences")
    op.drop_index("ix_pricing_experiences_industry", table_name="pricing_experiences")
    op.drop_table("pricing_experiences")

    op.drop_index("ix_talking_points_scenario", table_name="talking_points")
    op.drop_index("ix_talking_points_industry", table_name="talking_points")
    op.drop_table("talking_points")

    op.drop_index("ix_industry_materials_category", table_name="industry_materials")
    op.drop_index("ix_industry_materials_industry", table_name="industry_materials")
    op.drop_table("industry_materials")

    # proposal_templates
    op.drop_index("ix_proposal_templates_industry", table_name="proposal_templates")
    op.drop_column("proposal_templates", "industry")

    # visual_styles
    op.drop_index("ix_visual_styles_is_active", table_name="visual_styles")
    op.drop_index("ix_visual_styles_category", table_name="visual_styles")
    op.drop_column("visual_styles", "sub_type")
    op.drop_column("visual_styles", "is_active")
    op.drop_column("visual_styles", "category")

    # sop_workflows
    op.drop_index("ix_sop_workflows_category", table_name="sop_workflows")
    op.drop_column("sop_workflows", "version_note")
    op.drop_column("sop_workflows", "bound_agent")
    op.drop_column("sop_workflows", "category")

    # cases
    op.drop_index("ix_cases_project_type", table_name="cases")
    op.drop_column("cases", "original_client_name")
    op.drop_column("cases", "is_desensitized")
    op.drop_column("cases", "style_tag")
    op.drop_column("cases", "project_type")

    # documents
    op.drop_index("ix_documents_parse_status", table_name="documents")
    op.drop_index("ix_documents_category", table_name="documents")
    op.drop_column("documents", "parse_status")
    op.drop_column("documents", "category")
