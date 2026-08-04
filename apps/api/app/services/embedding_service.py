"""Abstract embedding service interface and MockEmbeddingService."""

import hashlib
import logging
import math
from abc import ABC, abstractmethod
from typing import List

from app.core.config import settings

logger = logging.getLogger(__name__)

EMBEDDING_DIMENSION = 1536


class EmbeddingService(ABC):
    """Abstract base class for text embedding generation."""

    @abstractmethod
    async def embed_text(self, text: str) -> List[float]:
        """Generate an embedding vector for a single text string."""

    @abstractmethod
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embedding vectors for a batch of text strings."""

    @abstractmethod
    def get_dimension(self) -> int:
        """Return the dimensionality of the embedding vectors."""


class MockEmbeddingService(EmbeddingService):
    """Mock embedding service that returns deterministic pseudo-random vectors.

    The vector values are derived from a hash of the input text so the same
    input always produces the same output, which is useful for testing.
    """

    async def embed_text(self, text: str) -> List[float]:
        """Generate a deterministic pseudo-random embedding for the text."""
        return self._hash_to_vector(text)

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        return [self._hash_to_vector(t) for t in texts]

    def get_dimension(self) -> int:
        return EMBEDDING_DIMENSION

    @staticmethod
    def _hash_to_vector(text: str) -> List[float]:
        """Convert text to a deterministic normalized pseudo-random vector."""
        vector = []
        for i in range(EMBEDDING_DIMENSION):
            # Use SHA-256 chunks to get deterministic float values
            chunk = f"{text}:{i}"
            h = hashlib.sha256(chunk.encode()).hexdigest()
            value = int(h[:8], 16) / 0xFFFFFFFF  # 0..1
            vector.append(value * 2 - 1)  # -1..1

        # Normalize to unit length
        magnitude = math.sqrt(sum(v * v for v in vector))
        if magnitude > 0:
            vector = [v / magnitude for v in vector]
        return vector


async def get_embedding_service(db=None) -> EmbeddingService:
    """Factory function to create the appropriate embedding service.

    If db session is provided, reads config from database (priority) then .env fallback.
    If no db session, falls back to .env only (backward compatible).
    """
    if db is not None:
        from app.services.settings_service import SettingsService
        cfg = await SettingsService.get_raw_many(db, [
            "embedding_provider", "embedding_api_key", "embedding_base_url",
            "embedding_model", "embedding_dimensions",
        ])
        provider = cfg["embedding_provider"]
    else:
        provider = settings.embedding_provider

    if provider == "openai":
        # Hard-fail if the OpenAI package is missing rather than silently
        # downgrading to the mock — a silent downgrade hides a broken install
        # and serves fake embeddings in production. Set provider to a non-openai
        # value explicitly to get MockEmbeddingService.
        from app.services.embedding.openai_provider import OpenAIEmbeddingService

        if db is not None:
            api_key = cfg["embedding_api_key"]
            base_url = cfg["embedding_base_url"]
            model = cfg["embedding_model"]
            # 维度也走 DB（DB 存 text，需 int 转换）；空或非法则回退 .env
            try:
                dimensions = int(cfg["embedding_dimensions"])
            except (TypeError, ValueError):
                dimensions = settings.embedding_dimensions
        else:
            api_key = settings.embedding_api_key
            base_url = settings.embedding_base_url
            model = settings.embedding_model
            dimensions = settings.embedding_dimensions

        # ── Dimension-mismatch guard ───────────────────────────────────────
        # WHY: the document_chunks.embedding column is fixed at Vector(1536) by
        # the ORM model definition (models/document.py) + Alembic migration 001.
        # That dimension is baked into the schema at class-definition time and
        # CANNOT be changed at runtime without a migration. So if an admin picks
        # a model whose dimension != 1536 (e.g. bge-m3 → 768), every embedding
        # written would silently violate the column constraint and vector
        # indexing/search would break with cryptic pgvector errors — or worse,
        # silently store nothing.
        #
        # Rather than serve broken vectors, degrade to MockEmbeddingService so
        # retrieval falls back to keyword search (no embeddings) instead of
        # producing dimension-mismatched vectors that can't be stored/searched.
        # The fix for the admin is to pick a 1536-dim model, or add a migration
        # that reindexes the column at the new dimension.
        if dimensions != EMBEDDING_DIMENSION:
            logger.error(
                "embedding_dimensions=%s but document_chunks.embedding is "
                "Vector(%s); a dimension-mismatched model cannot store/search "
                "vectors. Degrading embedding service to MockEmbeddingService "
                "(retrieval falls back to keyword search). Fix: configure a "
                "%s-dim embedding model, or add a migration to reindex the "
                "column at the new dimension.",
                dimensions, EMBEDDING_DIMENSION, EMBEDDING_DIMENSION,
            )
            return MockEmbeddingService()

        return OpenAIEmbeddingService(
            api_key=api_key,
            base_url=base_url or None,
            model=model,
            dimensions=dimensions,
        )
    return MockEmbeddingService()
