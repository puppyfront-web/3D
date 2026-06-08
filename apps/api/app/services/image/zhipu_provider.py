"""Zhipu AI (CogView) image generation provider.

API docs: https://open.bigmodel.cn/dev/api/image/cogview

Uses the Zhipu AI REST API for CogView image generation.
"""

import base64
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

MODEL_ALIASES = {
    "cogview-4": "cogview-4",
    "cogview-3-plus": "cogview-3-plus",
    "cogview-3": "cogview-3",
}


class ZhipuImageService:
    """Image generation via Zhipu AI CogView API."""

    BASE_URL = "https://open.bigmodel.cn/api/paas/v4/images/generations"

    def __init__(
        self,
        api_key: str,
        model: str = "cogview-4",
    ):
        self._api_key = api_key
        self._model = MODEL_ALIASES.get(model, model)

    async def generate_image(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 768,
        style: Optional[str] = None,
        negative_prompt: Optional[str] = None,
    ) -> bytes:
        """Generate an image and return its bytes."""
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
        """Generate an image via Zhipu CogView and return the URL."""
        size = self._map_size(width, height)

        payload: dict = {
            "model": self._model,
            "prompt": prompt,
            "size": size,
        }

        if style:
            payload["style"] = style

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(self.BASE_URL, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        # Zhipu returns { "data": [{ "url": "..." }] }
        images = data.get("data", [])
        if images and images[0].get("url"):
            return images[0]["url"]

        # Fallback: some models return base64
        if images and images[0].get("b64_json"):
            return f"data:image/png;base64,{images[0]['b64_json']}"

        raise RuntimeError(f"Zhipu API returned no image: {data}")

    @staticmethod
    def _map_size(width: int, height: int) -> str:
        """Map to CogView supported sizes.

        CogView-4: 1024x1024, 768x1344, 1344x768, 720x1440, 1440x720
        """
        size_map = {
            (1024, 1024): "1024x1024",
            (1344, 768): "1344x768",
            (768, 1344): "768x1344",
            (1440, 720): "1440x720",
            (720, 1440): "720x1440",
        }
        key = (width, height)
        if key in size_map:
            return size_map[key]
        # Default to landscape or portrait
        if width > height:
            return "1344x768"
        elif height > width:
            return "768x1344"
        return "1024x1024"
