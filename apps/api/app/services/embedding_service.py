"""Abstract embedding service interface and MockEmbeddingService."""

import hashlib
import math
from abc import ABC, abstractmethod
from typing import List

from app.core.config import settings

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


def get_embedding_service() -> EmbeddingService:
    """Factory function to create the appropriate embedding service."""
    if settings.embedding_provider == "openai":
        from app.services.embedding.openai_provider import OpenAIEmbeddingService

        return OpenAIEmbeddingService(
            api_key=settings.embedding_api_key,
            base_url=settings.embedding_base_url or None,
            model=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
        )
    return MockEmbeddingService()
