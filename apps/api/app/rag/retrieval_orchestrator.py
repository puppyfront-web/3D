"""Retrieval provider abstraction — local pgvector vs external FastGPT.

Indexing (document upload/chunk/embed) stays in DocumentService.
Search/retrieve for Q&A goes through RetrievalOrchestrator so backends are swappable.
"""

from __future__ import annotations

import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.rag.retriever import HybridRetriever
from app.services.settings_service import SettingsService

logger = logging.getLogger(__name__)


@dataclass
class NormalizedHit:
    """Provider-agnostic retrieval hit for Q&A and admin search."""

    chunk_id: str
    document_id: str
    content: str
    score: float
    source: str  # chunk | case | fastgpt
    title: Optional[str] = None
    page_number: Optional[int] = None
    provider: str = "local"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "content": self.content,
            "score": self.score,
            "source": self.source,
            "title": self.title,
            "page_number": self.page_number,
            "provider": self.provider,
        }


@dataclass
class TracedRetrieval:
    """Hits plus optional retrieval_logs.id from the local hybrid path."""

    hits: List[NormalizedHit]
    log_id: Optional[uuid.UUID] = None


def _results_to_hits(results: List[Any], provider_id: str) -> List[NormalizedHit]:
    return [
        NormalizedHit(
            chunk_id=r.chunk_id,
            document_id=r.document_id or "",
            content=r.content,
            score=r.score,
            source=getattr(r, "source", "chunk") or "chunk",
            title=getattr(r, "title", None),
            page_number=r.page_number,
            provider=provider_id,
        )
        for r in results
    ]


class BaseRetrievalProvider(ABC):
    @property
    @abstractmethod
    def provider_id(self) -> str:
        ...

    @abstractmethod
    async def search(
        self,
        db: AsyncSession,
        query: str,
        *,
        top_k: int = 8,
        project_id: Optional[uuid.UUID] = None,
        triggered_by: str = "retrieval_orchestrator",
        conversation_id: Optional[uuid.UUID] = None,
        message_id: Optional[uuid.UUID] = None,
        eval_run_id: Optional[uuid.UUID] = None,
    ) -> TracedRetrieval:
        ...


class LocalRetrievalProvider(BaseRetrievalProvider):
    """Default: HybridRetriever over PostgreSQL/pgvector + cases."""

    provider_id = "local"

    def __init__(self, retriever: Optional[HybridRetriever] = None) -> None:
        self._retriever = retriever or HybridRetriever()

    async def search(
        self,
        db: AsyncSession,
        query: str,
        *,
        top_k: int = 8,
        project_id: Optional[uuid.UUID] = None,
        triggered_by: str = "retrieval_orchestrator",
        conversation_id: Optional[uuid.UUID] = None,
        message_id: Optional[uuid.UUID] = None,
        eval_run_id: Optional[uuid.UUID] = None,
    ) -> TracedRetrieval:
        from app.services.embedding_service import get_embedding_service

        try:
            embedding = await get_embedding_service(db)
            self._retriever = HybridRetriever(embedding_service=embedding)
        except Exception:
            logger.debug("LocalRetrievalProvider: embedding unavailable, keyword path only")

        results, log_id = await self._retriever.search(
            query=query,
            top_k=top_k,
            project_id=project_id,
            db=db,
            triggered_by=triggered_by,
            conversation_id=conversation_id,
            message_id=message_id,
            eval_run_id=eval_run_id,
        )
        return TracedRetrieval(
            hits=_results_to_hits(results, self.provider_id),
            log_id=log_id,
        )


class FastGPTRetrievalProvider(BaseRetrievalProvider):
    """External vector search via FastGPT dataset searchTest API."""

    provider_id = "fastgpt"

    async def _config(self, db: AsyncSession) -> Dict[str, str]:
        async def g(key: str, default: str = "") -> str:
            v = await SettingsService.get(db, key, "")
            if v:
                return v
            return getattr(settings, key, default) or default

        base = (await g("fastgpt_base_url", settings.fastgpt_base_url)).rstrip("/")
        if base.endswith("/api"):
            base = base[:-4]
        return {
            "base_url": base,
            "api_key": await g("fastgpt_api_key", settings.fastgpt_api_key),
            "dataset_id": await g("fastgpt_dataset_id", settings.fastgpt_dataset_id),
            "search_mode": await g("fastgpt_search_mode", settings.fastgpt_search_mode) or "embedding",
        }

    async def search(
        self,
        db: AsyncSession,
        query: str,
        *,
        top_k: int = 8,
        project_id: Optional[uuid.UUID] = None,
        triggered_by: str = "retrieval_orchestrator",
        conversation_id: Optional[uuid.UUID] = None,
        message_id: Optional[uuid.UUID] = None,
        eval_run_id: Optional[uuid.UUID] = None,
    ) -> TracedRetrieval:
        del conversation_id, message_id, eval_run_id, project_id
        cfg = await self._config(db)
        if not cfg["base_url"] or not cfg["api_key"] or not cfg["dataset_id"]:
            logger.warning("FastGPT retrieval skipped: missing base_url/api_key/dataset_id")
            return TracedRetrieval(hits=[])

        url = f"{cfg['base_url']}/api/core/dataset/searchTest"
        payload = {
            "datasetId": cfg["dataset_id"],
            "text": query,
            "limit": min(top_k * 800, 8000),
            "similarity": 0,
            "searchMode": cfg["search_mode"],
            "usingReRank": False,
        }
        headers = {
            "Authorization": f"Bearer {cfg['api_key']}",
            "Content-Type": "application/json",
        }

        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                body = resp.json()
        except Exception:
            logger.exception("FastGPT searchTest failed for query=%r", query[:80])
            return TracedRetrieval(hits=[])

        elapsed_ms = int((time.monotonic() - start) * 1000)
        items = (body.get("data") or {}).get("list") or []

        hits: List[NormalizedHit] = []
        for item in items[:top_k]:
            text = (item.get("q") or item.get("a") or "").strip()
            if not text:
                continue
            scores = item.get("score") or []
            emb_score = 0.5
            if isinstance(scores, list):
                for s in scores:
                    if isinstance(s, dict) and s.get("type") == "embedding":
                        emb_score = float(s.get("value") or 0.5)
                        break
            hits.append(
                NormalizedHit(
                    chunk_id=str(item.get("id") or uuid.uuid4()),
                    document_id=str(item.get("collectionId") or ""),
                    content=text[:2000],
                    score=emb_score,
                    source="fastgpt",
                    title=item.get("sourceName") or item.get("collectionName") or "FastGPT",
                    page_number=None,
                    provider=self.provider_id,
                )
            )

        logger.info(
            "FastGPT retrieval: query=%r hits=%d latency_ms=%d triggered_by=%s",
            query[:60],
            len(hits),
            elapsed_ms,
            triggered_by,
        )
        return TracedRetrieval(hits=hits)


class RetrievalOrchestrator:
    """Route retrieval to configured provider(s)."""

    def __init__(self) -> None:
        self._local = LocalRetrievalProvider()
        self._fastgpt = FastGPTRetrievalProvider()

    async def _provider_name(self, db: AsyncSession) -> str:
        raw = await SettingsService.get_safe(
            db, "retrieval_provider", settings.retrieval_provider or "local"
        )
        return (raw or "local").strip().lower()

    async def search(
        self,
        db: AsyncSession,
        query: str,
        *,
        top_k: int = 8,
        project_id: Optional[uuid.UUID] = None,
        triggered_by: str = "knowledge_qa",
        conversation_id: Optional[uuid.UUID] = None,
        message_id: Optional[uuid.UUID] = None,
        eval_run_id: Optional[uuid.UUID] = None,
    ) -> TracedRetrieval:
        trace_kw = {
            "conversation_id": conversation_id,
            "message_id": message_id,
            "eval_run_id": eval_run_id,
        }
        provider = await self._provider_name(db)

        if provider == "fastgpt":
            traced = await self._fastgpt.search(
                db,
                query,
                top_k=top_k,
                project_id=project_id,
                triggered_by=triggered_by,
                **trace_kw,
            )
            if traced.hits:
                return traced
            logger.info("FastGPT returned no hits; falling back to local retriever")
            return await self._local.search(
                db,
                query,
                top_k=top_k,
                project_id=project_id,
                triggered_by=triggered_by,
                **trace_kw,
            )

        if provider == "dual":
            local_traced = await self._local.search(
                db,
                query,
                top_k=top_k,
                project_id=project_id,
                triggered_by=f"{triggered_by}_local",
                **trace_kw,
            )
            fg_traced = await self._fastgpt.search(
                db,
                query,
                top_k=top_k,
                project_id=project_id,
                triggered_by=f"{triggered_by}_fastgpt",
                **trace_kw,
            )
            merged: Dict[str, NormalizedHit] = {}
            for h in local_traced.hits + fg_traced.hits:
                key = h.chunk_id or h.content[:80]
                if key not in merged or h.score > merged[key].score:
                    merged[key] = h
            hits = sorted(merged.values(), key=lambda x: x.score, reverse=True)[:top_k]
            return TracedRetrieval(hits=hits, log_id=local_traced.log_id)

        return await self._local.search(
            db,
            query,
            top_k=top_k,
            project_id=project_id,
            triggered_by=triggered_by,
            **trace_kw,
        )


retrieval_orchestrator = RetrievalOrchestrator()
