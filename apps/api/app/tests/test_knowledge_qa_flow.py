"""KB-QA-Foundation — knowledge-first Q&A main flow tests."""

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.conversation import Message
from app.models.document import Document, DocumentChunk
from app.services.knowledge_context_service import acquire_kb_context, is_web_search_enabled


async def _seed_kb_document(db_session, project_id: uuid.UUID, keyword: str) -> Document:
    doc = Document(
        id=uuid.uuid4(),
        project_id=project_id,
        filename="product-guide.txt",
        original_filename="product-guide.txt",
        content_type="text/plain",
        file_size=256,
        file_path="/tmp/product-guide.txt",
        title="产品能力说明",
        status="indexed",
        parse_status="parsed",
        chunk_count=1,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(doc)
    await db_session.flush()
    chunk = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc.id,
        content=(
            f"核心产品「智汇云」面向制造与金融行业，提供 {keyword}、"
            "混合检索与可追溯问答能力。适用场景包括售前方案整理与内部制度查询。"
        ),
        chunk_index=0,
        page_number=1,
        token_count=50,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(chunk)
    await db_session.commit()
    return doc


@pytest.mark.asyncio
async def test_acquire_kb_context_finds_project_document(db_session, sample_project_id):
    keyword = "知识库管理"
    proj = sample_project_id if isinstance(sample_project_id, uuid.UUID) else uuid.UUID(str(sample_project_id))
    await _seed_kb_document(db_session, proj, keyword)

    citations, prompt_block, meta = await acquire_kb_context(
        db_session,
        f"智汇云是否支持{keyword}",
        project_id=str(proj),
        top_k=5,
    )

    assert meta["total"] >= 1
    assert len(citations) >= 1
    assert keyword in prompt_block or "智汇云" in prompt_block
    assert citations[0].get("title") or citations[0].get("snippet")


@pytest.mark.asyncio
async def test_conversational_stream_includes_kb_citations(
    client: AsyncClient, db_session, sample_project_id
):
    """Seeded chunk → chat stream emits assistant reply with KB metadata."""
    keyword = "混合检索"
    proj = sample_project_id if isinstance(sample_project_id, uuid.UUID) else uuid.UUID(str(sample_project_id))
    await _seed_kb_document(db_session, proj, keyword)

    conv_resp = await client.get(f"/api/v1/projects/{sample_project_id}/conversation")
    assert conv_resp.status_code == 200, conv_resp.text
    conversation_id = conv_resp.json()["data"]["id"]

    async with client.stream(
        "POST",
        f"/api/v1/conversations/{conversation_id}/chat/stream",
        json={
            "message": f"智汇云有哪些能力？是否支持{keyword}？",
            "forceIntent": "conversational",
        },
        timeout=60.0,
    ) as response:
        assert response.status_code == 200
        body = ""
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                body += line + "\n"

    assert "text_delta" in body
    assert "knowledge_citations" in body or "content_block_data" in body

    result = await db_session.execute(
        select(Message)
        .where(Message.conversation_id == uuid.UUID(conversation_id))
        .where(Message.role == "assistant")
        .order_by(Message.created_at.desc())
    )
    assistant = result.scalars().first()
    assert assistant is not None
    assert assistant.metadata_json.get("intent") == "conversational"
    log_ids = assistant.metadata_json.get("retrieval_log_ids") or []
    assert log_ids, "assistant should link retrieval_log_ids"
    citations = assistant.metadata_json.get("citations") or []
    assert citations, "assistant should include KB citations"


@pytest.mark.asyncio
async def test_web_search_enabled_default_without_db_setting(db_session):
    assert await is_web_search_enabled(db_session) is True
