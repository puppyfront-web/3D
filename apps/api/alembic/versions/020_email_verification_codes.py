"""Add email_verification_codes table for code login / password reset.

Revision ID: 020_email_verification_codes
Revises: 019_knowledge_asset_revisions
"""
from alembic import op
import sqlalchemy as sa

revision = "020_email_verification_codes"
down_revision = "019_knowledge_asset_revisions"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "email_verification_codes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("purpose", sa.String(20), nullable=False, comment="login|reset"),
        sa.Column("code_hash", sa.String(128), nullable=False, comment="HMAC digest; plaintext never stored"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_evc_email", "email_verification_codes", ["email"])
    op.create_index("ix_evc_email_purpose", "email_verification_codes", ["email", "purpose"])

def downgrade() -> None:
    op.drop_index("ix_evc_email_purpose", table_name="email_verification_codes")
    op.drop_index("ix_evc_email", table_name="email_verification_codes")
    op.drop_table("email_verification_codes")
