"""Hybrid retrieval implementation combining keyword and vector search.

Supports pgvector cosine similarity for vector search and PostgreSQL
full-text search for keyword matching, with configurable scoring weights.
"""

import time
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import Case
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
        source: str = "chunk",
        title: Optional[str] = None,
    ):
        self.chunk_id = chunk_id
        self.document_id = document_id
        self.content = content
        self.score = score
        self.page_number = page_number
        self.source = source  # "chunk" | "case"
        self.title = title

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "content": self.content,
            "score": self.score,
            "page_number": self.page_number,
            "source": self.source,
            "title": self.title,
        }


class HybridRetriever:
    """Hybrid retriever that blends keyword and vector similarity scores.

    Scoring weights (configurable):
    - vector_weight: pgvector cosine similarity score
    - keyword_weight: simple keyword match score
    - quality_weight: case quality score (when searching cases)
    - reuse_weight: case reuse weight (when searching cases)
    """

    def __init__(
        self,
        embedding_service: Optional[EmbeddingService] = None,
        vector_weight: float = 0.4,
        keyword_weight: float = 0.2,
        quality_weight: float = 0.2,
        reuse_weight: float = 0.2,
    ):
        self._embedding_service = embedding_service or get_embedding_service()
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight
        self.quality_weight = quality_weight
        self.reuse_weight = reuse_weight

    async def search(
        self,
        query: str,
        top_k: int = 5,
        project_id: Optional[uuid.UUID] = None,
        retrieval_type: str = "hybrid",
        db: Optional[AsyncSession] = None,
    ) -> List[RetrievalResult]:
        """Perform hybrid search over document chunks and cases.

        When a database session is provided, queries real data with pgvector.
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
                document_ids=list({r.document_id for r in results if r.source == "chunk"}),
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
        """Search against the database with real pgvector and keyword search."""
        results: List[RetrievalResult] = []

        # --- Vector search via pgvector ---
        if retrieval_type in ("hybrid", "vector"):
            vector_results = await self._vector_search(query, top_k, project_id, db)
            results.extend(vector_results)

        # --- Keyword search via ILIKE ---
        if retrieval_type in ("hybrid", "keyword"):
            keyword_results = await self._keyword_search(query, top_k, project_id, db)
            results.extend(keyword_results)

        # --- Case search ---
        case_results = await self._search_cases(query, top_k, db)
        results.extend(case_results)

        # --- Deduplicate and merge scores ---
        if retrieval_type == "hybrid" and len(results) > 0:
            results = self._merge_scores(results)

        # Sort by score descending
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    async def _vector_search(
        self,
        query: str,
        top_k: int,
        project_id: Optional[uuid.UUID],
        db: AsyncSession,
    ) -> List[RetrievalResult]:
        """Perform pgvector cosine similarity search on document chunks."""
        try:
            query_embedding = await self._embedding_service.embed_text(query)
        except Exception:
            # Embedding failed — skip vector search
            return []

        try:
            # Use pgvector cosine distance: embedding <=> query_vector
            # cosine_distance returns 0 for identical, 2 for opposite
            # similarity = 1 - cosine_distance
            stmt = select(
                DocumentChunk,
                (1 - DocumentChunk.embedding.cosine_distance(query_embedding)).label("similarity"),
            ).where(DocumentChunk.embedding.isnot(None))

            if project_id:
                stmt = stmt.join(Document).where(Document.project_id == project_id)

            stmt = stmt.order_by(
                DocumentChunk.embedding.cosine_distance(query_embedding)
            ).limit(top_k)

            result = await db.execute(stmt)
            rows = result.all()

            return [
                RetrievalResult(
                    chunk_id=str(chunk.id),
                    document_id=str(chunk.document_id),
                    content=chunk.content[:500],
                    score=round(max(0, similarity), 3),
                    page_number=chunk.page_number,
                    source="chunk",
                )
                for chunk, similarity in rows
            ]
        except Exception:
            # pgvector not available (e.g. SQLite) — fallback
            return []

    async def _keyword_search(
        self,
        query: str,
        top_k: int,
        project_id: Optional[uuid.UUID],
        db: AsyncSession,
    ) -> List[RetrievalResult]:
        """Perform keyword search using ILIKE on document chunks."""
        keywords = [kw for kw in query.split()[:5] if len(kw) > 1]
        if not keywords:
            return []

        keyword_conditions = [
            DocumentChunk.content.ilike(f"%{kw}%") for kw in keywords
        ]

        query_obj = select(DocumentChunk).where(or_(*keyword_conditions))

        if project_id:
            query_obj = query_obj.join(Document).where(Document.project_id == project_id)

        query_obj = query_obj.limit(top_k * 2)
        result = await db.execute(query_obj)
        chunks = result.scalars().all()

        results = []
        for chunk in chunks:
            keyword_score = sum(
                1.0 for kw in keywords if kw.lower() in chunk.content.lower()
            ) / max(len(keywords), 1)
            results.append(
                RetrievalResult(
                    chunk_id=str(chunk.id),
                    document_id=str(chunk.document_id),
                    content=chunk.content[:500],
                    score=round(keyword_score, 3),
                    page_number=chunk.page_number,
                    source="chunk",
                )
            )
        return results

    async def _search_cases(
        self,
        query: str,
        top_k: int,
        db: AsyncSession,
    ) -> List[RetrievalResult]:
        """Search cases table for relevant case studies."""
        stmt = select(Case).where(Case.is_published == True)
        # Text match on title, challenge, solution
        keywords = [kw for kw in query.split()[:5] if len(kw) > 1]
        if keywords:
            text_conditions = [
                or_(
                    Case.title.ilike(f"%{kw}%"),
                    Case.challenge.ilike(f"%{kw}%"),
                    Case.solution.ilike(f"%{kw}%"),
                )
                for kw in keywords
            ]
            stmt = stmt.where(or_(*text_conditions))

        stmt = stmt.order_by(Case.quality_score.desc()).limit(top_k)
        result = await db.execute(stmt)
        cases = result.scalars().all()

        results = []
        for case in cases:
            # Score based on text match + quality + reuse weight
            text_score = 0.5
            if keywords:
                text = f"{case.title} {case.challenge} {case.solution}".lower()
                text_score = sum(1.0 for kw in keywords if kw.lower() in text) / max(len(keywords), 1)

            quality_score = (case.quality_score or 50) / 100.0
            final_score = (
                self.keyword_weight * text_score
                + self.quality_weight * quality_score
                + self.reuse_weight * quality_score  # reuse proportional to quality for now
            )
            results.append(
                RetrievalResult(
                    chunk_id=str(case.id),
                    document_id="",
                    content=f"{case.challenge}\n{case.solution}\n{case.results}",
                    score=round(final_score, 3),
                    source="case",
                    title=case.title,
                )
            )
        return results

    def _merge_scores(self, results: List[RetrievalResult]) -> List[RetrievalResult]:
        """Merge duplicate chunk results by keeping the highest score."""
        seen: dict[str, RetrievalResult] = {}
        for r in results:
            key = r.chunk_id
            if key in seen:
                existing = seen[key]
                # Keep the higher score
                if r.score > existing.score:
                    seen[key] = r
            else:
                seen[key] = r
        return list(seen.values())

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
                    source="chunk",
                )
            )
        return results
