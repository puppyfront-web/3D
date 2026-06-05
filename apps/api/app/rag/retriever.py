"""Hybrid retrieval implementation combining keyword and vector search."""

import time
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentChunk
from app.models.retrieval import RetrievalLog
from app.services.embedding_service import EmbeddingService, get_embedding_service


class RetrievalResult:
    """Single retrieval result item."""

    def __init__(
        self,
        chunk_id: str,
        document_id: str,
        content: str,
        score: float,
        page_number: Optional[int] = None,
    ):
        self.chunk_id = chunk_id
        self.document_id = document_id
        self.content = content
        self.score = score
        self.page_number = page_number

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "content": self.content,
            "score": self.score,
            "page_number": self.page_number,
        }


class HybridRetriever:
    """Hybrid retriever that blends keyword and vector similarity scores."""

    def __init__(
        self,
        embedding_service: Optional[EmbeddingService] = None,
        keyword_weight: float = 0.6,
        vector_weight: float = 0.4,
    ):
        self._embedding_service = embedding_service or get_embedding_service()
        self.keyword_weight = keyword_weight
        self.vector_weight = vector_weight

    async def search(
        self,
        query: str,
        top_k: int = 5,
        project_id: Optional[uuid.UUID] = None,
        retrieval_type: str = "hybrid",
        db: Optional[AsyncSession] = None,
    ) -> List[RetrievalResult]:
        """Perform hybrid search over document chunks.

        When a database session is provided, queries real data.
        Otherwise returns mock results for development.
        """
        start = time.monotonic()

        if db is not None:
            results = await self._db_search(query, top_k, project_id, retrieval_type, db)
        else:
            results = self._mock_search(query, top_k, retrieval_type)

        elapsed_ms = int((time.monotonic() - start) * 1000)

        # Log the retrieval if we have a db session
        if db is not None:
            log = RetrievalLog(
                id=uuid.uuid4(),
                query=query,
                retrieval_type=retrieval_type,
                results_count=len(results),
                top_scores=[r.score for r in results[:5]],
                document_ids=list({r.document_id for r in results}),
                latency_ms=elapsed_ms,
            )
            db.add(log)
            await db.flush()

        return results

    async def _db_search(
        self,
        query: str,
        top_k: int,
        project_id: Optional[uuid.UUID],
        retrieval_type: str,
        db: AsyncSession,
    ) -> List[RetrievalResult]:
        """Search against the database with real document chunks."""
        # Keyword search
        keywords = query.split()[:5]
        keyword_conditions = [
            DocumentChunk.content.ilike(f"%{kw}%") for kw in keywords
        ]

        query_obj = select(DocumentChunk).where(or_(*keyword_conditions))

        if project_id:
            query_obj = query_obj.join(Document).where(Document.project_id == project_id)

        query_obj = query_obj.limit(top_k * 2)  # Fetch extra for re-ranking
        result = await db.execute(query_obj)
        chunks = result.scalars().all()

        # Score and rank results
        results = []
        for idx, chunk in enumerate(chunks[:top_k]):
            # Calculate keyword relevance (simple word match count)
            keyword_score = sum(
                1.0 for kw in keywords if kw.lower() in chunk.content.lower()
            ) / max(len(keywords), 1)

            # Mock vector score (would use pgvector cosine similarity in production)
            vector_score = 0.95 - (idx * 0.08)

            if retrieval_type == "keyword":
                final_score = keyword_score
            elif retrieval_type == "vector":
                final_score = vector_score
            else:  # hybrid
                final_score = (
                    self.keyword_weight * keyword_score
                    + self.vector_weight * vector_score
                )

            results.append(
                RetrievalResult(
                    chunk_id=str(chunk.id),
                    document_id=str(chunk.document_id),
                    content=chunk.content[:500],
                    score=round(final_score, 3),
                    page_number=chunk.page_number,
                )
            )

        results.sort(key=lambda r: r.score, reverse=True)
        return results

    @staticmethod
    def _mock_search(query: str, top_k: int, retrieval_type: str) -> List[RetrievalResult]:
        """Generate mock retrieval results for development."""
        mock_items = [
            (
                "Cloud migration best practices recommend a phased approach starting with non-critical workloads. Organizations should assess application dependencies, establish network connectivity, and implement monitoring before migrating production systems.",
                0.95,
            ),
            (
                "The company's digital transformation strategy focuses on three pillars: infrastructure modernization, data-driven decision making, and customer experience enhancement. Key initiatives include cloud adoption, AI integration, and omnichannel platform development.",
                0.88,
            ),
            (
                "Successful enterprise transformations require executive sponsorship, clear communication plans, and dedicated change management resources. Studies show that projects with formal change management are six times more likely to meet objectives.",
                0.82,
            ),
            (
                "Technology stack evaluation criteria should include scalability, security compliance, integration capabilities, total cost of ownership, and vendor support quality. Our assessment framework covers 47 distinct evaluation dimensions.",
                0.76,
            ),
            (
                "Implementation methodology follows agile principles with two-week sprints, daily standups, and regular stakeholder demos. Risk mitigation includes automated testing, blue-green deployments, and rollback procedures for all major releases.",
                0.71,
            ),
        ]

        results = []
        for i, (content, score) in enumerate(mock_items[:top_k]):
            results.append(
                RetrievalResult(
                    chunk_id=str(uuid.uuid4()),
                    document_id=str(uuid.uuid4()),
                    content=content,
                    score=round(score, 3),
                    page_number=i + 1,
                )
            )
        return results
