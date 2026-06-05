"""OpenAI-compatible Embedding provider using the openai Python SDK."""

import logging
from typing import List, Optional

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class OpenAIEmbeddingService:
    """Embedding service backed by an OpenAI-compatible API."""

    def __init__(
        self,
        api_key: str,
        base_url: Optional[str] = None,
        model: str = "text-embedding-3-small",
        dimensions: int = 1536,
    ):
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url or None,
        )
        self._model = model
        self._dimensions = dimensions

    async def embed_text(self, text: str) -> List[float]:
        """Generate an embedding vector for a single text string."""
        response = await self._client.embeddings.create(
            model=self._model,
            input=text,
            dimensions=self._dimensions,
        )
        return response.data[0].embedding

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embedding vectors for a batch of text strings."""
        if not texts:
            return []
        response = await self._client.embeddings.create(
            model=self._model,
            input=texts,
            dimensions=self._dimensions,
        )
        # Results are returned in the same order as input
        return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]

    def get_dimension(self) -> int:
        """Return the dimensionality of the embedding vectors."""
        return self._dimensions
