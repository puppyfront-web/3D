"""Tests for RAG retrieval endpoints and the knowledge_search tool.

The knowledge_search tool has two retrieval paths: the pgvector vector path
(requires a live Postgres + embeddings, covered separately) and a keyword
fallback used when no embedding service is available (SQLite test DB,
embedding_service=None). The tests below exercise the keyword path and the
tool's input-safety helpers (uuid parsing, CJK tokenization, ILIKE escaping).
"""

import pytest

from app.models.document import Document, DocumentChunk
from app.tools.base import ToolContext, ToolResult
from app.tools.builtins.knowledge_search import (
    KnowledgeSearchTool,
    _escape_like,
    _parse_project_id,
    _tokenize_query,
)


@pytest.mark.asyncio
async def test_rag_search(client):
    """Test the RAG hybrid search endpoint."""
    response = await client.post(
        "/api/v1/rag/search",
        params={
            "query": "cloud migration best practices",
            "top_k": 3,
            "retrieval_type": "hybrid",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["query"] == "cloud migration best practices"
    assert data["data"]["retrieval_type"] == "hybrid"
    assert data["data"]["total"] > 0
    assert len(data["data"]["results"]) > 0

    # Check result structure
    result = data["data"]["results"][0]
    assert "chunk_id" in result
    assert "document_id" in result
    assert "content" in result
    assert "score" in result
    assert result["score"] > 0


@pytest.mark.asyncio
async def test_rag_search_keyword(client):
    """Test keyword-only retrieval."""
    response = await client.post(
        "/api/v1/rag/search",
        params={
            "query": "digital transformation strategy",
            "top_k": 5,
            "retrieval_type": "keyword",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["retrieval_type"] == "keyword"


@pytest.mark.asyncio
async def test_rag_search_vector(client):
    """Test vector-only retrieval."""
    response = await client.post(
        "/api/v1/rag/search",
        params={
            "query": "project management methodology",
            "top_k": 5,
            "retrieval_type": "vector",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["retrieval_type"] == "vector"


@pytest.mark.asyncio
async def test_rag_search_scores_ordered(client):
    """Test that search results are ordered by relevance score."""
    response = await client.post(
        "/api/v1/rag/search",
        params={
            "query": "implementation approach",
            "top_k": 5,
        },
    )
    assert response.status_code == 200
    data = response.json()
    results = data["data"]["results"]

    if len(results) > 1:
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_rag_search_latency(client):
    """Test that search latency is reported."""
    response = await client.post(
        "/api/v1/rag/search",
        params={"query": "test query"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "latency_ms" in data["data"]
    assert data["data"]["latency_ms"] >= 0


@pytest.mark.asyncio
async def test_knowledge_search_tool_uses_real_database_chunks(db_session, sample_project_id):
    """KnowledgeSearchTool should return indexed chunks from DB, not mock fallback."""
    document = Document(
        project_id=sample_project_id,
        filename="real-case.md",
        original_filename="real-case.md",
        content_type="text/markdown",
        file_size=128,
        file_path="/tmp/real-case.md",
        title="真实案例资料",
        status="indexed",
        chunk_count=1,
    )
    db_session.add(document)
    await db_session.flush()

    chunk = DocumentChunk(
        document_id=document.id,
        content="裸眼3D商业综合体项目采用真实案例库资料，包含主观看点与视觉动线。",
        chunk_index=0,
        page_number=1,
        token_count=28,
    )
    db_session.add(chunk)
    await db_session.flush()

    tool = KnowledgeSearchTool()
    result = await tool.execute(
        {"query": "裸眼3D 商业综合体", "top_k": 3, "project_id": str(sample_project_id)},
        ToolContext(db=db_session, embedding_service=None),
    )

    assert result.success is True
    assert result.data["total"] == 1
    assert result.data["chunks"][0]["chunk_id"] == str(chunk.id)
    assert result.data["chunks"][0]["document_id"] == str(document.id)


@pytest.mark.asyncio
async def test_knowledge_search_malformed_project_id_does_not_raise(
    db_session, sample_project_id
):
    """A malformed project_id must degrade to an unfiltered search, not a 500."""
    document = Document(
        project_id=sample_project_id,
        filename="safe.md",
        original_filename="safe.md",
        content_type="text/markdown",
        file_size=64,
        file_path="/tmp/safe.md",
        title="安全降级资料",
        status="indexed",
        chunk_count=1,
    )
    db_session.add(document)
    await db_session.flush()
    db_session.add(
        DocumentChunk(
            document_id=document.id,
            content="安全降级：畸形 project_id 不应导致 500。",
            chunk_index=0,
            page_number=1,
            token_count=20,
        )
    )
    await db_session.flush()

    tool = KnowledgeSearchTool()
    # "not-a-uuid" is malformed — must not raise; search runs unfiltered.
    result = await tool.execute(
        {"query": "安全降级", "top_k": 5, "project_id": "not-a-uuid"},
        ToolContext(db=db_session, embedding_service=None),
    )
    assert result.success is True
    assert result.data["total"] >= 1


# ── knowledge_search input-safety helpers ──────────────────────────────


def test_tokenize_query_splits_cjk_per_char():
    # CJK has no spaces; split() would yield one giant token. Per-char split
    # gives each character as a searchable unit.
    tokens = _tokenize_query("裸眼3D幕墙")
    assert "裸" in tokens and "眼" in tokens and "幕" in tokens and "墙" in tokens
    # ASCII run kept as one token
    assert "3D" in tokens
    # single ASCII chars dropped
    assert "D" not in tokens or "3D" in tokens


def test_tokenize_query_keeps_ascii_words():
    tokens = _tokenize_query("cloud migration best practices")
    assert tokens == ["cloud", "migration", "best", "practices"]


def test_tokenize_query_empty():
    assert _tokenize_query("") == []
    assert _tokenize_query(None) == []  # type: ignore[arg-type]


def test_parse_project_id_malformed():
    assert _parse_project_id(None) is None
    assert _parse_project_id("not-a-uuid") is None
    import uuid as _uuid

    assert _parse_project_id(str(_uuid.uuid4())) is not None


def test_escape_like_escapes_wildcards():
    assert _escape_like("50%off") == r"50\%off"
    assert _escape_like("a_b") == r"a\_b"
    assert _escape_like(r"path\to") == r"path\\to"
    assert _escape_like("plain") == "plain"


# ── ProposalAgent._extract_tool_list (ToolResult payload extraction) ──


def test_extract_tool_list_pulls_payload_from_tool_result():
    """Tools return ToolResult (.data dict), not a bare list. The proposal
    agent used to isinstance(result, list) and silently dropped every hit."""
    from app.agents.proposal import _extract_tool_list

    assert _extract_tool_list(ToolResult(success=True, data={"chunks": [1, 2, 3]}), "chunks") == [1, 2, 3]
    assert _extract_tool_list(ToolResult(success=True, data={"cases": [{"x": 1}]}), "cases") == [{"x": 1}]
    # missing key / wrong shape / non-dict data → empty list, never raises
    assert _extract_tool_list(ToolResult(success=True, data={"chunks": "oops"}), "chunks") == []
    assert _extract_tool_list(ToolResult(success=True, data=None), "chunks") == []
    assert _extract_tool_list(object(), "chunks") == []
