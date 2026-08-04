"""Add knowledge_asset_revisions table for version history (PRD §23.4.9).

Revision ID: 019_knowledge_asset_revisions
Revises: 018_user_hashed_password
"""
from alembic import op
import sqlalchemy as sa

revision = "019_knowledge_asset_revisions"
down_revision = "018_user_hashed_password"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "knowledge_asset_revisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("asset_type", sa.String(50), nullable=False, comment="case|sop_workflow|proposal_template|prompt_template|visual_style|technical_rule|quality_rule|industry_material|talking_point|pricing_experience"),
        sa.Column("asset_id", sa.Uuid(), nullable=False, comment="Polymorphic FK — not a real FK because asset_type varies"),
        sa.Column("version_no", sa.Integer, nullable=False, default=1),
        sa.Column("snapshot", sa.JSON, nullable=False, comment="Full column snapshot at revision time"),
        sa.Column("change_summary", sa.Text, nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_kar_asset_type", "knowledge_asset_revisions", ["asset_type"])
    op.create_index("ix_kar_asset_id", "knowledge_asset_revisions", ["asset_id"])
    op.create_index("ux_kar_asset_version", "knowledge_asset_revisions", ["asset_type", "asset_id", "version_no"], unique=True)

def downgrade() -> None:
    op.drop_index("ux_kar_asset_version", table_name="knowledge_asset_revisions")
    op.drop_index("ix_kar_asset_id", table_name="knowledge_asset_revisions")
    op.drop_index("ix_kar_asset_type", table_name="knowledge_asset_revisions")
    op.drop_table("knowledge_asset_revisions")
