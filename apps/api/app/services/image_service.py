"""Abstract image generation service and MockImageGenerationService."""

from abc import ABC, abstractmethod
from typing import Optional

from app.core.config import settings


class ImageGenerationService(ABC):
    """Abstract base class for image generation."""

    @abstractmethod
    async def generate_image(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 768,
        style: Optional[str] = None,
    ) -> bytes:
        """Generate an image from a text prompt."""

    @abstractmethod
    async def generate_image_url(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 768,
        style: Optional[str] = None,
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


def get_image_service() -> ImageGenerationService:
    """Factory function to create the appropriate image generation service."""
    if settings.image_provider == "mock":
        return MockImageGenerationService()
    return MockImageGenerationService()
