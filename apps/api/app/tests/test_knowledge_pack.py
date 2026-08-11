"""Knowledge Pack import tests (M3)."""

import io
import json
import uuid
import zipfile

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.document import Document
from app.models.eval import EvalCase
from app.models.talking_point import TalkingPoint


def _build_pack_zip(keyword: str = "Pack验收专用词") -> bytes:
    manifest = {
        "pack_version": "1.0",
        "name": f"test-pack-{uuid.uuid4().hex[:8]}",
        "documents": [
            {
                "relative_path": "files/guide.txt",
                "title": "Pack 文档",
                "doc_category": "product",
            }
        ],
        "talking_points": [
            {"scene": "首次接洽", "title": "Pack 话术", "content": "欢迎语"}
        ],
        "eval_set": {
            "name": "pack-smoke",
            "cases": [{"query": keyword, "expected_keywords": [keyword]}],
        },
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("knowledge_pack.json", json.dumps(manifest, ensure_ascii=False))
        zf.writestr(
            "files/guide.txt",
            f"智汇云提供 {keyword} 与混合检索能力。\n",
        )
    return buf.getvalue()


@pytest.mark.asyncio
async def test_import_knowledge_pack_zip(client: AsyncClient, db_session):
    raw = _build_pack_zip()
    resp = await client.post(
        "/api/v1/knowledge/packs/import",
        files={"file": ("pack.zip", raw, "application/zip")},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    docs_n = data.get("documents_imported", data.get("documentsImported"))
    tp_n = data.get("talking_points_imported", data.get("talkingPointsImported"))
    assert docs_n == 1
    assert tp_n == 1
    assert data.get("eval_set_id") or data.get("evalSetId")
    assert data.get("skipped") is False

    docs = (await db_session.execute(select(Document))).scalars().all()
    assert any("guide" in (d.original_filename or "") for d in docs)
    tps = (await db_session.execute(select(TalkingPoint))).scalars().all()
    assert any("Pack 话术" in (t.title or "") for t in tps)
    cases = (await db_session.execute(select(EvalCase))).scalars().all()
    assert len(cases) >= 1


@pytest.mark.asyncio
async def test_import_knowledge_pack_skips_same_hash(client: AsyncClient):
    raw = _build_pack_zip(keyword="幂等词")
    r1 = await client.post(
        "/api/v1/knowledge/packs/import",
        files={"file": ("pack.zip", raw, "application/zip")},
    )
    assert r1.status_code == 200
    r2 = await client.post(
        "/api/v1/knowledge/packs/import",
        files={"file": ("pack.zip", raw, "application/zip")},
    )
    assert r2.status_code == 200
    assert r2.json()["data"]["skipped"] is True


@pytest.mark.asyncio
async def test_document_chunks_list(client: AsyncClient, db_session, sample_project_id):
    from datetime import datetime, timezone

    from app.models.document import DocumentChunk

    doc = Document(
        id=uuid.uuid4(),
        project_id=sample_project_id,
        filename="c.txt",
        original_filename="c.txt",
        content_type="text/plain",
        file_size=10,
        file_path="/tmp/c.txt",
        title="chunk preview",
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
            content="预览分块内容",
            chunk_index=0,
            page_number=1,
            token_count=5,
            created_at=datetime.now(timezone.utc),
        )
    )
    await db_session.commit()

    resp = await client.get(f"/api/v1/documents/{doc.id}/chunks")
    assert resp.status_code == 200
    items = resp.json()["data"]
    assert len(items) == 1
    preview = items[0].get("content_preview") or items[0].get("contentPreview") or ""
    assert "预览分块" in preview
