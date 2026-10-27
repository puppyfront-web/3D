"""Eval run engine tests."""

import uuid
from datetime import datetime, timezone

import pytest

from app.models.document import Document, DocumentChunk
from app.models.eval import EvalCase, EvalSet
from app.services.eval_service import eval_service


async def _seed_chunk(db_session, project_id: uuid.UUID, text: str) -> uuid.UUID:
    doc = Document(
        id=uuid.uuid4(),
        project_id=project_id,
        filename="e.txt",
        original_filename="e.txt",
        content_type="text/plain",
        file_size=10,
        file_path="/tmp/e.txt",
        title="eval doc",
        status="indexed",
        parse_status="parsed",
        chunk_count=1,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(doc)
    await db_session.flush()
    chunk_id = uuid.uuid4()
    db_session.add(
        DocumentChunk(
            id=chunk_id,
            document_id=doc.id,
            content=text,
            chunk_index=0,
            page_number=1,
            token_count=10,
            created_at=datetime.now(timezone.utc),
        )
    )
    await db_session.commit()
    return chunk_id


@pytest.mark.asyncio
async def test_eval_run_hit_at_k(db_session, sample_project_id):
    proj = (
        sample_project_id
        if isinstance(sample_project_id, uuid.UUID)
        else uuid.UUID(str(sample_project_id))
    )
    chunk_id = await _seed_chunk(db_session, proj, "企业知识库混合检索验收文本")

    es = EvalSet(name="smoke", project_id=proj, status="active")
    db_session.add(es)
    await db_session.flush()

    db_session.add(
        EvalCase(
            set_id=es.id,
            query="混合检索",
            expected_chunk_ids=[str(chunk_id)],
            source="manual",
        )
    )
    await db_session.commit()

    run = await eval_service.run_set(db_session, es.id)
    assert run.status == "completed"
    assert run.metrics_json["total"] == 1
    assert run.metrics_json["passed"] == 1
@pytest.mark.asyncio
async def test_import_smoke_template_idempotent(db_session):
    s1 = await eval_service.import_smoke_template(db_session)
    await db_session.commit()
    s2 = await eval_service.import_smoke_template(db_session)
    await db_session.commit()
    assert s1.id == s2.id
    cases = await eval_service.list_cases(db_session, s1.id)
    assert len(cases) >= 3
