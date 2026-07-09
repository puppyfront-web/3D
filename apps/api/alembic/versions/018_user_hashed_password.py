"""Add hashed_password column to users table.

Revision ID: 018_user_hashed_password
Revises: 017_conversation_locks
"""
from alembic import op
import sqlalchemy as sa

revision = "018_user_hashed_password"
down_revision = "017_conversation_locks"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("users", sa.Column("hashed_password", sa.String(length=255), nullable=True))

def downgrade() -> None:
    op.drop_column("users", "hashed_password")
