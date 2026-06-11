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
        provider = await SettingsService.get_raw(db, "embedding_provider", settings.embedding_provider)
    else:
        provider = settings.embedding_provider

    if provider == "openai":
        try:
            from app.services.embedding.openai_provider import OpenAIEmbeddingService
        except ImportError as exc:
            logger.warning("OpenAI embedding provider unavailable, falling back to mock: %s", exc)
            return MockEmbeddingService()

        if db is not None:
            from app.services.settings_service import SettingsService
            api_key = await SettingsService.get_raw(db, "embedding_api_key", settings.embedding_api_key)
            base_url = await SettingsService.get_raw(db, "embedding_base_url", settings.embedding_base_url)
            model = await SettingsService.get_raw(db, "embedding_model", settings.embedding_model)
            # 维度也走 DB（DB 存 text，需 int 转换）；空则回退 .env
            dim_raw = await SettingsService.get_raw(
                db, "embedding_dimensions", str(settings.embedding_dimensions)
            )
            try:
                dimensions = int(dim_raw)
            except (TypeError, ValueError):
                dimensions = settings.embedding_dimensions
        else:
            api_key = settings.embedding_api_key
            base_url = settings.embedding_base_url
            model = settings.embedding_model
            dimensions = settings.embedding_dimensions

        return OpenAIEmbeddingService(
            api_key=api_key,
            base_url=base_url or None,
            model=model,
            dimensions=dimensions,
        )
    return MockEmbeddingService()
