"""OpenAI DALL-E image generation provider.

Works with any OpenAI-compatible API that follows the /v1/images/generations endpoint.
Supports: OpenAI DALL-E 2/3, and any compatible service via base_url override.
"""

import logging
from typing import Optional

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class DallEImageGenerationService:
    """Image generation service backed by OpenAI's DALL-E API."""

    def __init__(
        self,
        api_key: str,
        base_url: Optional[str] = None,
        model: str = "dall-e-3",
    ):
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url or None,
        )
        self._model = model

    async def generate_image(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 768,
        style: Optional[str] = None,
        negative_prompt: Optional[str] = None,
    ) -> bytes:
        """Generate an image and return its bytes."""
        import httpx

        url = await self.generate_image_url(prompt, width, height, style, negative_prompt)
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.content

    async def generate_image_url(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 768,
        style: Optional[str] = None,
        negative_prompt: Optional[str] = None,
    ) -> str:
        """Generate an image and return its URL."""
        size = self._map_size(width, height)

        # Build the full prompt (append negative prompt if provided)
        full_prompt = prompt
        if negative_prompt:
            full_prompt = f"{prompt}\n\nAvoid: {negative_prompt}"

        kwargs = {
            "model": self._model,
            "prompt": full_prompt,
            "size": size,
            "quality": "standard",
            "n": 1,
            "response_format": "url",
        }
        if style and self._model.startswith("dall-e-3"):
            kwargs["style"] = style

        response = await self._client.images.generate(**kwargs)
        return response.data[0].url or ""

    @staticmethod
    def _map_size(width: int, height: int) -> str:
        """Map pixel dimensions to DALL-E supported size strings."""
        size_map = {
            (1024, 1024): "1024x1024",
            (1792, 1024): "1792x1024",
            (1024, 1792): "1024x1792",
        }
        key = (width, height)
        if key in size_map:
            return size_map[key]
        if width > height:
            return "1792x1024"
        elif height > width:
            return "1024x1792"
        return "1024x1024"
