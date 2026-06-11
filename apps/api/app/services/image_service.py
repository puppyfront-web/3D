"""Abstract image generation service and MockImageGenerationService.

Supported providers:
  - mock: SVG placeholder (default for dev)
  - openai / dalle: OpenAI DALL-E API
  - siliconflow: SiliconFlow API (Flux, SDXL, etc.)
  - zhipu: Zhipu AI CogView API
  - custom: Any OpenAI-compatible image API
"""

from abc import ABC, abstractmethod
import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class ImageGenerationService(ABC):
    """Abstract base class for image generation."""

    @abstractmethod
    async def generate_image(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 768,
        style: Optional[str] = None,
        negative_prompt: Optional[str] = None,
    ) -> bytes:
        """Generate an image from a text prompt."""

    @abstractmethod
    async def generate_image_url(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 768,
        style: Optional[str] = None,
        negative_prompt: Optional[str] = None,
    ) -> str:
        """Generate an image and return its URL."""


class MockImageGenerationService(ImageGenerationService):
    """Mock image service that returns placeholder SVG images."""

    async def generate_image(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 768,
        style: Optional[str] = None,
        negative_prompt: Optional[str] = None,
    ) -> bytes:
        """Return a simple SVG placeholder image as bytes."""
        svg = self._create_placeholder_svg(prompt, width, height, style)
        return svg.encode("utf-8")

    async def generate_image_url(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 768,
        style: Optional[str] = None,
        negative_prompt: Optional[str] = None,
    ) -> str:
        """Return a placeholder image URL (using a data URI for mock)."""
        svg = self._create_placeholder_svg(prompt, width, height, style)
        import base64
        encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
        return f"data:image/svg+xml;base64,{encoded}"

    @staticmethod
    def _create_placeholder_svg(
        prompt: str, width: int, height: int, style: Optional[str]
    ) -> str:
        """Create a simple SVG placeholder with prompt text."""
        truncated = prompt[:60] + ("..." if len(prompt) > 60 else "")
        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#1a73e8;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#4285f4;stop-opacity:1" />
    </linearGradient>
  </defs>
  <rect width="{width}" height="{height}" fill="url(#bg)" rx="12" />
  <text x="{width // 2}" y="{height // 2 - 20}" text-anchor="middle" fill="white" font-family="Arial, sans-serif" font-size="24" font-weight="bold">3D Wall Generated Image</text>
  <text x="{width // 2}" y="{height // 2 + 20}" text-anchor="middle" fill="rgba(255,255,255,0.8)" font-family="Arial, sans-serif" font-size="14">{truncated}</text>
  <text x="{width // 2}" y="{height - 30}" text-anchor="middle" fill="rgba(255,255,255,0.5)" font-family="Arial, sans-serif" font-size="12">{width}x{height} | {style or 'default'}</text>
</svg>"""


async def get_image_service(db=None) -> ImageGenerationService:
    """Factory function to create the appropriate image generation service.

    Provider selection via IMAGE_PROVIDER env var:
      - "mock"       : SVG placeholder (default)
      - "openai"     : OpenAI DALL-E API
      - "dalle"      : Alias for openai
      - "siliconflow": SiliconFlow (Flux, SDXL, Kolors, etc.)
      - "zhipu"      : Zhipu AI CogView
      - "custom"     : Any OpenAI-compatible image API

    If db session is provided, reads config from database (priority) then .env fallback.
    """
    if db is not None:
        from app.services.settings_service import SettingsService
        cfg = await SettingsService.get_raw_many(db, [
            "image_provider", "image_api_key", "image_base_url", "image_model", "image_quality",
        ])
        provider = cfg["image_provider"].lower()
        api_key = cfg["image_api_key"]
        base_url = cfg["image_base_url"]
        model = cfg["image_model"]
        quality = cfg["image_quality"]
    else:
        provider = settings.image_provider.lower()
        api_key = settings.image_api_key
        base_url = settings.image_base_url
        model = settings.image_model
        quality = settings.image_quality

    if provider in ("openai", "dalle"):
        # Hard-fail on a missing OpenAI package rather than silently downgrading
        # to the mock (which would render SVG placeholders in production). Use
        # provider="mock" explicitly to get the mock.
        from app.services.image.openai_provider import DallEImageGenerationService
        return DallEImageGenerationService(
            api_key=api_key,
            base_url=base_url or None,
            model=model,
            quality=quality,
        )

    if provider == "siliconflow":
        from app.services.image.siliconflow_provider import SiliconFlowImageService
        return SiliconFlowImageService(
            api_key=api_key,
            model=model,
        )

    if provider == "zhipu":
        from app.services.image.zhipu_provider import ZhipuImageService
        return ZhipuImageService(
            api_key=api_key,
            model=model,
        )

    if provider == "custom":
        from app.services.image.openai_provider import DallEImageGenerationService
        return DallEImageGenerationService(
            api_key=api_key,
            base_url=base_url or None,
            model=model,
            quality=quality,
        )

    return MockImageGenerationService()
