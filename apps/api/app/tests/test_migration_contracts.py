"""Regression tests for deployment-critical migration contracts."""

from pathlib import Path


API_ROOT = Path(__file__).resolve().parents[2]
VERSIONS_DIR = API_ROOT / "alembic" / "versions"


def test_initial_migration_creates_pgvector_extension_and_embedding_column():
    source = (VERSIONS_DIR / "001_initial.py").read_text(encoding="utf-8")

    assert "CREATE EXTENSION IF NOT EXISTS vector" in source
    assert 'sa.Column("embedding", _embedding_type(), nullable=True)' in source
    assert "return Vector(1536)" in source


def test_embedding_index_is_gated_to_postgresql_only():
    source = (VERSIONS_DIR / "002_skills_and_project_external.py").read_text(encoding="utf-8")

    assert 'if op.get_bind().dialect.name == "postgresql":' in source
    assert "idx_chunks_embedding" in source


def test_conversation_migration_uses_uuid_foreign_keys():
    source = (VERSIONS_DIR / "003_conversations.py").read_text(encoding="utf-8")

    assert 'sa.Column("id", sa.Uuid(), primary_key=True)' in source
    assert 'sa.Column("project_id", sa.Uuid(),' in source
    assert 'sa.Column("conversation_id", sa.Uuid(),' in source
    assert 'sa.Column("skill_execution_id", sa.Uuid(),' in source


def test_prompt_template_fix_migration_binds_jsonb_values():
    source = (VERSIONS_DIR / "010_fix_prompt_templates.py").read_text(encoding="utf-8")

    assert "type_=postgresql.JSONB" in source
