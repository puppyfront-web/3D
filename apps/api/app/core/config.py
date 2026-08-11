"""Application configuration loaded from environment variables."""

from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env relative to this file (apps/api/app/core/) -> apps/api/.env
_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    """Application settings derived from environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Enterprise Knowledge Assistant API"
    app_version: str = "1.0.0-kb-case"
    debug: bool = False
    app_env: str = "development"
    kb_sku: str = "standard"
    canvas_enabled: bool = False

    # Private deployment seed (KB_PRIVATE_DELIVERY_SPEC M1-1)
    initial_admin_email: str = ""
    initial_admin_password: str = ""
    seed_demo_content: bool = True

    # Database
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/3dwall"
    )

    # LLM — provider defaults empty: mock mode was removed, a missing provider
    # fails loudly at the factory instead of serving fabricated output.
    llm_provider: str = ""
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = "gpt-4o"

    # Embedding
    embedding_provider: str = ""
    embedding_api_key: str = ""
    embedding_base_url: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # Image generation
    image_provider: str = "mock"  # mock | openai | dalle | siliconflow | zhipu | custom
    image_api_key: str = ""
    image_base_url: str = ""
    image_model: str = "dall-e-3"  # Model varies by provider:
    #   openai: dall-e-2, dall-e-3
    #   siliconflow: flux-schnell, flux-dev, sdxl, kolors, sd3
    #   zhipu: cogview-4, cogview-3-plus, cogview-3
    image_quality: str = "high"  # low | medium | high | auto | hd (vendor-specific)

    # Canvas auto-fill on first message is disabled for KB-QA mode (Canvas hidden).
    canvas_auto_fill_enabled: bool = False

    # Retrieval backend for Q&A search (indexing stays local unless synced to FastGPT separately)
    # local | fastgpt | dual
    retrieval_provider: str = "local"
    fastgpt_base_url: str = ""
    fastgpt_api_key: str = ""
    fastgpt_dataset_id: str = ""
    fastgpt_search_mode: str = "embedding"  # embedding | fullTextRecall | mixedRecall

    # Web search — used by WebSearchTool for external information retrieval.
    # All configurable via admin settings UI (DB-first, .env fallback) — see settings_service.py.
    web_search_enabled: bool = True
    web_search_mode: str = "auto"  # auto | tavily | llm_native | disabled
    web_search_tavily_api_key: str = ""
    web_search_max_results: int = 5
    web_search_timeout: int = 15  # seconds, per provider call
    web_search_min_confidence: float = 0.5  # below this → degraded

    # Storage
    storage_path: str = "./storage"

    # Upload limits — reject oversized files before they hit disk.
    max_upload_size: int = 50 * 1024 * 1024  # 50 MB

    # OCR — used by OCRService to extract text from scanned PDFs.
    # When disabled (or paddleocr not installed) parsing degrades gracefully:
    # scanned PDFs fall back to PyMuPDF's native (often empty) text extraction.
    ocr_enabled: bool = True
    ocr_min_confidence: float = 0.5

    # Security
    api_key: str = "dev-api-key-change-in-production"
    # NOTE: the .env file uses `APP_SECRET_KEY` while this reads `SECRET_KEY`.
    # The APP_SECRET_KEY/secret_key naming mismatch is a deployment concern; the
    # default below works for local dev. Production should set SECRET_KEY explicitly.
    secret_key: str = "dev-secret-key-change-in-production"
    access_token_expire_minutes: int = 1440  # 24 hours

    # CORS
    cors_origins: str = (
        "http://localhost:3000,http://localhost:5173"
    )

    @property
    def cors_origin_list(self) -> List[str]:
        """Parse CORS origins into a list."""
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]


settings = Settings()
