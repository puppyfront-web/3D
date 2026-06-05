"""Hybrid retrieval service (keyword + vector search)."""

import time
from abc import ABC, abstractmethod
from typing import List, Optional

from app.services.embedding_service import EmbeddingService, get_embedding_service


class RetrievalResult:
    """A single retrieval result with relevance scoring."""

    def __init__(
        self,
        chunk_id: str,
        document_id: str,
        content: str,
        score: float,
        page_number: Optional[int] = None,
        metadata: Optional[dict] = None,
    ):
        self.chunk_id = chunk_id
        self.document_id = document_id
        self.content = content
        self.score = score
        self.page_number = page_number
        self.metadata = metadata or {}


class RetrievalService(ABC):
    """Abstract retrieval service for hybrid search."""

    @abstractmethod
    async def search(
        self,
        query: str,
        top_k: int = 5,
        project_id: Optional[str] = None,
        retrieval_type: str = "hybrid",
    ) -> List[RetrievalResult]:
        """Search for relevant document chunks."""

    @abstractmethod
    async def index_document(
        self,
        document_id: str,
        chunks: List[dict],
    ) -> int:
        """Index document chunks with embeddings. Returns count of indexed chunks."""


class HybridRetrievalService(RetrievalService):
    """Hybrid retrieval combining keyword matching and vector similarity."""

    def __init__(self, embedding_service: Optional[EmbeddingService] = None):
        self._embedding_service = embedding_service or get_embedding_service()

    async def search(
        self,
        query: str,
        top_k: int = 5,
        project_id: Optional[str] = None,
        retrieval_type: str = "hybrid",
    ) -> List[RetrievalResult]:
        """Perform hybrid search over document chunks.

        In production this would query the database with pgvector.
        The mock implementation returns realistic placeholder results.
        """
        start = time.monotonic()

        # Generate query embedding for vector search
        query_embedding = await self._embedding_service.embed_text(query)

        # Mock results — in production these come from the database
        mock_results = self._generate_mock_results(query, top_k)

        elapsed = time.monotonic() - start
        return mock_results

    async def index_document(
        self,
        document_id: str,
        chunks: List[dict],
    ) -> int:
        """Index chunks by generating embeddings for each.

        Returns the number of chunks indexed.
        """
        texts = [chunk.get("content", "") for chunk in chunks]
        if texts:
            embeddings = await self._embedding_service.embed_texts(texts)
            # In production: store embeddings in document_chunks table
            return len(embeddings)
        return 0

    @staticmethod
    def _generate_mock_results(query: str, top_k: int) -> List[RetrievalResult]:
        """Generate realistic mock retrieval results."""
        import uuid

        mock_data = [
            {
                "content": "Cloud migration best practices recommend a phased approach starting with non-critical workloads. Key considerations include data transfer planning, security compliance, and performance benchmarking.",
                "score": 0.95,
            },
            {
                "content": "The company's digital transformation roadmap outlines three strategic pillars: infrastructure modernization, data analytics enhancement, and customer experience optimization.",
                "score": 0.88,
            },
            {
                "content": "Implementation methodology follows agile principles with two-week sprints, daily standups, and regular stakeholder demos to ensure alignment with business objectives.",
                "score": 0.82,
            },
            {
                "content": "Risk mitigation strategies include automated testing, blue-green deployments, and comprehensive rollback procedures. Disaster recovery plans cover all critical systems with RTO under 4 hours.",
                "score": 0.76,
            },
            {
                "content": "Success metrics for the project include: system uptime > 99.9%, API response time < 200ms, customer satisfaction score > 90%, and processing speed improvement > 40%.",
                "score": 0.71,
            },
        ]

        results = []
        for i, item in enumerate(mock_data[:top_k]):
            results.append(
                RetrievalResult(
                    chunk_id=str(uuid.uuid4()),
                    document_id=str(uuid.uuid4()),
                    content=item["content"],
                    score=item["score"],
                    page_number=i + 1,
                )
            )
        return results


def get_retrieval_service() -> RetrievalService:
    """Factory function to create the retrieval service."""
    return HybridRetrievalService()
