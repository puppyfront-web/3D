"""Tests for RAG retrieval endpoints."""

import pytest

from app.models.document import Document, DocumentChunk
from app.tools.base import ToolContext
from app.tools.builtins.knowledge_search import KnowledgeSearchTool


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
