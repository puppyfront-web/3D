"""OCR service — PaddleOCR wrapper with graceful degradation.

Used by DocumentParser as a fallback when PyMuPDF extracts almost no text
from a PDF (a strong signal the PDF is a scanned image).

Design notes:
  * Lazy + cached: PaddleOCR loads ML models on first use (~2-5s). We build
    the instance on first call and reuse it — constructing per-request would
    dominate latency.
  * Import-tolerant: if paddleocr/paddlepaddle aren't installed (the `ocr`
    optional extra), `extract_text` returns "" and callers fall back to
    whatever text was already extracted. No exception bubbles up.
  * Config-gated: `settings.ocr_enabled` lets operators disable OCR without
    uninstalling packages.
"""

import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class OCRService:
    """Thin singleton wrapper around PaddleOCR."""

    _instance: Optional["OCRService"] = None
    _engine: Optional[object] = None  # PaddleOCR instance, lazily built

    def __new__(cls) -> "OCRService":
        # Singleton — share the model-loaded engine across requests.
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def extract_text(self, file_path: str) -> str:
        """Extract text from an image or image-like PDF.

        Returns "" on any failure or when OCR is disabled/unavailable.
        Never raises — callers rely on this to be a soft fallback.
        """
        if not settings.ocr_enabled:
            return ""

        engine = self._get_engine()
        if engine is None:
            return ""

        try:
            # PaddleOCR v2.x: ocr() returns a list (one entry per page/image).
            # Each entry is a list of [bbox, (text, confidence)] pairs.
            results = engine.ocr(file_path, cls=True)
        except Exception as e:  # noqa: BLE001 — OCR is best-effort
            logger.warning("OCR failed on %s: %s", file_path, e)
            return ""

        texts: list[str] = []
        min_conf = settings.ocr_min_confidence
        for page in results or []:
            for line in page or []:
                try:
                    _bbox, (text, conf) = line
                except (TypeError, ValueError):
                    continue
                if text and conf >= min_conf:
                    texts.append(text)
        return "\n".join(texts)

    def _get_engine(self) -> Optional[object]:
        """Lazily build and cache the PaddleOCR engine.

        Any import / init failure is logged once and pinned to None via the
        `_engine_unavailable` flag so we don't retry on every request.
        """
        if self._engine is not None:
            return self._engine
        if getattr(self, "_engine_unavailable", False):
            return None

        try:
            from paddleocr import PaddleOCR
        except ImportError:
            logger.info(
                "PaddleOCR not installed — OCR fallback disabled. "
                "Install with: pip install -e .[ocr]"
            )
            self._engine_unavailable = True
            return None

        try:
            self._engine = PaddleOCR(use_angle_cls=True, lang="ch")
            logger.info("PaddleOCR engine initialized (lang=ch)")
        except Exception as e:  # noqa: BLE001 — model load can fail many ways
            logger.warning("PaddleOCR init failed: %s", e)
            self._engine_unavailable = True
            return None

        return self._engine
