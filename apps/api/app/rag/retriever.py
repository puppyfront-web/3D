"""Hybrid retrieval implementation combining keyword and vector search.

Supports pgvector cosine similarity for vector search and PostgreSQL
full-text search for keyword matching, with configurable scoring weights.
"""

import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.ttl_cache import TTLCachedService
from app.models.case import Case
from app.models.document import Document, DocumentChunk
from app.models.retrieval import RetrievalLog
from app.services.embedding_service import EmbeddingService, get_embedding_service

logger = logging.getLogger(__name__)


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
        self._embedding = TTLCachedService(
            factory=get_embedding_service, ttl_seconds=30.0, initial=embedding_service,
        )
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight
        self.quality_weight = quality_weight
        self.reuse_weight = reuse_weight

    async def _get_embedding_service(
        self, db: Optional[AsyncSession] = None
    ) -> EmbeddingService:
        """Resolve the embedding service, refreshing from DB config after TTL.

        The cached service is rebuilt every 30s so admin-UI model-config changes
        take effect without a process restart. See :class:`TTLCachedService`.
        """
        return await self._embedding.get(db)

    async def search(
        self,
        query: str,
        top_k: int = 5,
        project_id: Optional[uuid.UUID] = None,
        retrieval_type: str = "hybrid",
        db: Optional[AsyncSession] = None,
        triggered_by: Optional[str] = None,
        structured_query: Optional[Dict[str, Any]] = None,
        conversation_id: Optional[uuid.UUID] = None,
        message_id: Optional[uuid.UUID] = None,
        eval_run_id: Optional[uuid.UUID] = None,
    ) -> Tuple[List[RetrievalResult], Optional[uuid.UUID]]:
        """Perform hybrid search over document chunks and cases.

        When a database session is provided, queries real data with pgvector.
        Otherwise returns mock results for development.
        """
        start = time.monotonic()

        if db is not None:
            results = await self._db_search(query, top_k, project_id, retrieval_type, db)
        else:
            # No DB session. Historically this returned hardcoded mock
            # cloud-migration text (Defect #14) — a dev footgun that silently
            # injected fabricated results into real pipelines. Now we only use
            # the mock when explicitly opted in (debug mode + TEST_MODE flag);
            # otherwise return empty results + a prominent warning.
            _test_mode = str(os.environ.get("TEST_MODE", "")).strip().lower() in (
                "1", "true", "yes", "on",
            )
            if settings.debug and _test_mode:
                results = self._mock_search(query, top_k, retrieval_type)
            else:
                logger.warning(
                    "HybridRetriever.search called with db=None — returning "
                    "empty results. This usually indicates a missing DB session "
                    "in the call chain."
                )
                results = []

        elapsed_ms = int((time.monotonic() - start) * 1000)
        log_id: Optional[uuid.UUID] = None

        # Log the retrieval if we have a db session (PRD §9.4 traceability).
        if db is not None:
            # Cap the per-item payload so a wide retrieval does not bloat the
            # log row — keep only the traceability essentials.
            retrieved_items = [
                {
                    "id": getattr(r, "chunk_id", None) or getattr(r, "case_id", None),
                    "document_id": getattr(r, "document_id", None),
                    "source": getattr(r, "source", None),
                    "score": getattr(r, "score", None),
                    "title": getattr(r, "title", None),
                }
                for r in results[:20]
            ]
            log = RetrievalLog(
                id=uuid.uuid4(),
                query=query,
                retrieval_type=retrieval_type,
                results_count=len(results),
                top_scores=[r.score for r in results[:5]],
                document_ids=list({r.document_id for r in results if r.source == "chunk"}),
                latency_ms=elapsed_ms,
                triggered_by=triggered_by or "hybrid_retriever",
                project_id=project_id,
                conversation_id=conversation_id,
                message_id=message_id,
                eval_run_id=eval_run_id,
                structured_query_json={
                    "top_k": top_k,
                    "project_id": str(project_id) if project_id else None,
                    "retrieval_type": retrieval_type,
                    **(structured_query or {}),
                },
                retrieved_items_json=retrieved_items,
            )
            db.add(log)
            await db.flush()
            log_id = log.id

        return results, log_id

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
            svc = await self._get_embedding_service(db=db)
            query_embedding = await svc.embed_text(query)
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
                    # Pre-weight by vector_weight so _merge_scores can simply
                    # add vector + keyword contributions for shared chunks.
                    score=round(max(0, similarity) * self.vector_weight, 3),
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
        """Perform keyword search using ILIKE on document chunks.

        Uses the shared CJK-aware tokenizer (see app.rag.tokenizer): CJK text has
        no spaces, so naive ``query.split()`` would yield one giant token that
        ILIKE never matches. CJK runs are split per-character into search units.
        """
        from app.rag.tokenizer import tokenize_query

        keywords = tokenize_query(query, max_tokens=5)
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
                    # Pre-weight by keyword_weight so _merge_scores can simply
                    # add vector + keyword contributions for shared chunks.
                    score=round(keyword_score * self.keyword_weight, 3),
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
        """Merge duplicate chunk results via a weighted score combination.

        ``_vector_search`` and ``_keyword_search`` each already multiply their
        raw 0-1 score by their respective weight (``vector_weight`` /
        ``keyword_weight``). So for a chunk appearing in both result sets we
        simply ADD the two pre-weighted scores, yielding
        ``vector_score * vector_weight + keyword_score * keyword_weight``.
        A chunk appearing in only one set keeps its already-weighted score.
        Cases (``source == "case"``) have unique ``chunk_id``s and their scores
        are already finalized in ``_search_cases``, so they pass through
        unchanged.
        """
        seen: dict[str, RetrievalResult] = {}
        for r in results:
            key = r.chunk_id
            if r.source == "case":
                # Already-finalized case score — keep as-is, never reweighted.
                seen[key] = r
                continue
            if key in seen:
                existing = seen[key]
                # Add the pre-weighted contributions of both retrieval paths.
                existing.score = round(existing.score + r.score, 3)
            else:
                seen[key] = r
        return list(seen.values())

    @staticmethod
    def _mock_search(query: str, top_k: int, retrieval_type: str) -> List[RetrievalResult]:
        """Generate mock retrieval results for development.

        Only invoked when called with ``db=None`` AND ``settings.debug`` is True
        AND the ``TEST_MODE`` env flag is set — otherwise ``search`` returns an
        empty list with a warning (see Defect #14).
        """
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
