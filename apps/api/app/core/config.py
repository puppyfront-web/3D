"""Application configuration loaded from environment variables."""

from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings derived from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "3D Wall API"
    app_version: str = "0.1.0"
    debug: bool = False

    # Database
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/3dwall"
    )

    # LLM
    llm_provider: str = "mock"
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = "gpt-4o"

    # Embedding
    embedding_provider: str = "mock"
    embedding_api_key: str = ""
    embedding_base_url: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # Image generation
    image_provider: str = "mock"
    image_api_key: str = ""
    image_base_url: str = ""
    image_model: str = "dall-e-3"

    # Storage
    storage_path: str = "./storage"

    # Security
    api_key: str = "dev-api-key-change-in-production"
    secret_key: str = "dev-secret-key-change-in-production"

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
