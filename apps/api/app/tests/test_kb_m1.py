"""KB-Case-Delivery M1 tests."""

import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, Message
from app.models.document import Document, DocumentChunk
from app.models.retrieval import RetrievalLog
from app.models.user import Role, User
from app.services.knowledge_context_service import acquire_kb_context
from app.services.retrieval_trace_service import link_message_to_retrieval_log


async def _seed_chunk(db_session, project_id: uuid.UUID, text: str) -> None:
    doc = Document(
        id=uuid.uuid4(),
        project_id=project_id,
        filename="t.txt",
        original_filename="t.txt",
        content_type="text/plain",
        file_size=10,
        file_path="/tmp/t.txt",
        title="trace doc",
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
async def test_settings_put_requires_admin(client: AsyncClient, db_session: AsyncSession):
    user_role = Role(
        id=uuid.uuid4(),
        name="user",
        description="standard user",
    )
    db_session.add(user_role)
    await db_session.flush()

    user = User(
        id=uuid.uuid4(),
        email="user-only@example.com",
        name="User",
        role_id=user_role.id,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    from app.core.security import get_current_user
    from app.main import create_app

    app = create_app()

    async def as_user():
        await db_session.refresh(user, ["role"])
        return user

    app.dependency_overrides[get_current_user] = as_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        resp = await ac.put("/api/v1/settings", json={"llm_model": "gpt-4o-mini"})
        assert resp.status_code == 403

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_retrieval_log_message_link_after_kb_context(db_session, sample_project_id):
    conv = Conversation(title="kb trace test", status="active")
    db_session.add(conv)
    await db_session.flush()

    proj_id = (
        sample_project_id
        if isinstance(sample_project_id, uuid.UUID)
        else uuid.UUID(str(sample_project_id))
    )
    await _seed_chunk(db_session, proj_id, "混合检索与可追溯问答是核心能力")

    citations, _block, meta = await acquire_kb_context(
        db_session,
        "混合检索",
        project_id=str(proj_id),
        conversation_id=conv.id,
    )
    log_id_str = meta.get("retrieval_log_id")
    assert log_id_str

    msg = Message(
        id=uuid.uuid4(),
        conversation_id=conv.id,
        role="assistant",
        content="answer",
        metadata_json={"retrieval_log_ids": [log_id_str], "citations": citations},
    )
    db_session.add(msg)
    await db_session.flush()

    await link_message_to_retrieval_log(
        db_session,
        uuid.UUID(log_id_str),
        msg.id,
        conv.id,
        project_id=proj_id,
    )
    await db_session.commit()

    log = (
        await db_session.execute(
            select(RetrievalLog).where(RetrievalLog.id == uuid.UUID(log_id_str))
        )
    ).scalar_one()
    assert log.message_id == msg.id
    assert log.conversation_id == conv.id
    assert log.final_output_id == str(msg.id)


@pytest.mark.asyncio
async def test_rag_search_context_preview(client: AsyncClient, db_session, sample_project_id):
    from datetime import datetime, timezone

    from app.models.document import Document, DocumentChunk

    doc = Document(
        id=uuid.uuid4(),
        project_id=sample_project_id,
        filename="preview.txt",
        original_filename="preview.txt",
        content_type="text/plain",
        file_size=64,
        file_path="/tmp/preview.txt",
        title="预览文档",
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
            content="混合检索 Context Pack 预览验收文本",
            chunk_index=0,
            page_number=1,
            token_count=10,
            created_at=datetime.now(timezone.utc),
        )
    )
    await db_session.commit()

    resp = await client.post(
        "/api/v1/rag/search",
        params={
            "query": "混合检索",
            "top_k": 5,
            "include_context_preview": True,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    preview = data.get("context_preview_text") or data.get("contextPreviewText")
    assert preview
    assert "混合检索" in preview or "预览" in preview
    assert data.get("log_id") or data.get("logId")
