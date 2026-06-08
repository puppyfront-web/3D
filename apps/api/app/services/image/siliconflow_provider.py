"""SiliconFlow image generation provider.

Supports models: Flux, SDXL, Kolors, Stable Diffusion, etc.
API docs: https://docs.siliconflow.cn/api-reference/images/images-generations

Uses the OpenAI-compatible /v1/images/generations endpoint.
"""

import logging
from typing import Optional

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# Popular models on SiliconFlow
MODEL_ALIASES = {
    "flux-dev": "black-forest-labs/FLUX.1-dev",
    "flux-schnell": "black-forest-labs/FLUX.1-schnell",
    "sdxl": "stabilityai/stable-diffusion-xl-base-1.0",
    "kolors": "Kwai-Kolors/Kolors",
    "sd3": "stabilityai/stable-diffusion-3-medium",
}


class SiliconFlowImageService:
    """Image generation via SiliconFlow API."""

    BASE_URL = "https://api.siliconflow.cn/v1"

    def __init__(
        self,
        api_key: str,
        model: str = "flux-schnell",
        base_url: Optional[str] = None,
    ):
        resolved = MODEL_ALIASES.get(model, model)
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url or self.BASE_URL,
        )
        self._model = resolved

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
        """Generate an image via SiliconFlow and return the URL."""
        size = self._map_size(width, height)

        kwargs: dict = {
            "model": self._model,
            "prompt": prompt,
            "image_size": size,
            "num_inference_steps": 20,
            "batch_size": 1,
        }

        if negative_prompt:
            kwargs["negative_prompt"] = negative_prompt

        # SiliconFlow uses a custom endpoint format but compatible with
        # OpenAI SDK when using the right base_url
        response = await self._client.images.generate(**kwargs)
        return response.data[0].url or ""

    @staticmethod
    def _map_size(width: int, height: int) -> str:
        """Map to SiliconFlow supported sizes."""
        # SiliconFlow supports: 1024x1024, 1280x720, 720x1280, etc.
        return f"{width}x{height}"
