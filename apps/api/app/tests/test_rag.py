"""Tests for RAG retrieval endpoints."""

import pytest


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
