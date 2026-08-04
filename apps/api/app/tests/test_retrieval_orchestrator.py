"""Tests for retrieval orchestrator (local provider)."""

import uuid
from datetime import datetime, timezone

import pytest

from app.models.document import Document, DocumentChunk
from app.rag.retrieval_orchestrator import retrieval_orchestrator


async def _seed_chunk(db_session, project_id: uuid.UUID, text: str) -> None:
    doc = Document(
        id=uuid.uuid4(),
        project_id=project_id,
        filename="t.txt",
        original_filename="t.txt",
        content_type="text/plain",
        file_size=10,
        file_path="/tmp/t.txt",
        title="测试文档",
        status="indexed",
        parse_status="parsed",
        chunk_count=1,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(doc)
    await db_session.flush()
    db_session.add(
        DocumentChunk(
            id=uuid.uuid4(),
            document_id=doc.id,
            content=text,
            chunk_index=0,
            page_number=1,
            token_count=10,
            created_at=datetime.now(timezone.utc),
        )
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_orchestrator_local_search(db_session, sample_project_id):
    proj = sample_project_id if isinstance(sample_project_id, uuid.UUID) else uuid.UUID(str(sample_project_id))
    await _seed_chunk(db_session, proj, "企业知识库支持混合检索与可追溯问答")

    hits = await retrieval_orchestrator.search(
        db_session,
        "混合检索",
        top_k=5,
        project_id=proj,
        triggered_by="test",
    )
    assert len(hits) >= 1
    assert hits[0].provider == "local"
