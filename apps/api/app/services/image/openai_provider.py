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
        quality: str = "high",
        timeout: float = 120.0,
    ):
        # Bound the request so a hung upstream fails fast (the OpenAI client
        # default of 600s would hang the whole conversation stream indefinitely).
        # max_retries=0 because retrying a timed-out image request just multiplies
        # the wait — better to fail and let the agent/user retry explicitly.
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url or None,
            timeout=timeout,
            max_retries=0,
        )
        self._model = model
        self._quality = quality

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
            "quality": self._quality or "high",
            "n": 1,
            "response_format": "url",
        }
        if style and self._model.startswith("dall-e-3"):
            kwargs["style"] = style

        # OpenAI-compatible vendors vary in which optional params they accept.
        # If the upstream rejects quality/response_format/style, retry without
        # the offending param(s) rather than failing the whole generation.
        return await self._generate_with_fallbacks(kwargs)

    async def _generate_with_fallbacks(self, kwargs: dict) -> str:
        """Call images.generate, progressively dropping optional params on rejection.

        Order of optional params to drop: style → quality → response_format.
        """
        drop_order = ["style", "quality", "response_format"]
        current = dict(kwargs)
        for _ in range(len(drop_order) + 1):
            try:
                response = await self._client.images.generate(**current)
                url = response.data[0].url if response.data else ""
                if not url:
                    # Some vendors return b64_json instead of a url
                    b64 = getattr(response.data[0], "b64_json", None) if response.data else None
                    if b64:
                        return f"data:image/png;base64,{b64}"
                return url or ""
            except Exception as exc:
                msg = str(exc).lower()
                rejected = self._rejected_param(msg, current, drop_order)
                if rejected:
                    logger.warning(
                        "Image provider rejected param '%s' (%s); retrying without it.",
                        rejected, type(exc).__name__,
                    )
                    current.pop(rejected, None)
                    continue
                raise
        return ""

    @staticmethod
    def _rejected_param(msg: str, current: dict, drop_order: list) -> Optional[str]:
        """Return the param name to drop based on the error message, or None."""
        # Prefer an explicit param name mentioned in the error
        for p in drop_order:
            if p in current and p in msg:
                return p
        # Generic "unexpected"/"unrecognized" param errors → drop the most optional first
        if "unexpected" in msg or "unrecognized" in msg or "unknown" in msg:
            for p in drop_order:
                if p in current:
                    return p
        return None

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
