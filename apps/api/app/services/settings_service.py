"""Settings service — runtime configuration from database with .env fallback."""

import re
from typing import Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.app_setting import AppSetting

# All known setting keys and their .env fallback field names
_SETTING_KEYS: Dict[str, str] = {
    "llm_provider": "llm_provider",
    "llm_api_key": "llm_api_key",
    "llm_base_url": "llm_base_url",
    "llm_model": "llm_model",
    "embedding_provider": "embedding_provider",
    "embedding_api_key": "embedding_api_key",
    "embedding_base_url": "embedding_base_url",
    "embedding_model": "embedding_model",
    "image_provider": "image_provider",
    "image_api_key": "image_api_key",
    "image_base_url": "image_base_url",
    "image_model": "image_model",
}

# Keys that contain sensitive data
_SENSITIVE_KEYS = {"llm_api_key", "embedding_api_key", "image_api_key"}

_MASK_PATTERN = re.compile(r"^\*{4}")


class SettingsService:
    """Read/write application settings with DB-first, .env-fallback strategy."""

    @staticmethod
    async def get(db: AsyncSession, key: str, default: Optional[str] = None) -> str:
        """Get a single setting value. DB -> .env -> default."""
        result = await db.execute(select(AppSetting).where(AppSetting.key == key))
        row = result.scalar_one_or_none()
        if row is not None:
            return row.value
        # Fallback to .env
        fallback = getattr(settings, key, None)
        if fallback is not None:
            return str(fallback)
        return default or ""

    @staticmethod
    async def get_all(db: AsyncSession) -> Dict[str, str]:
        """Get all known settings with DB-first, .env-fallback. Masks sensitive keys."""
        # Load all DB rows at once
        result = await db.execute(select(AppSetting))
        db_map = {row.key: row.value for row in result.scalars().all()}

        output: Dict[str, str] = {}
        for key, env_attr in _SETTING_KEYS.items():
            if key in db_map:
                value = db_map[key]
            else:
                value = str(getattr(settings, env_attr, ""))
            # Mask sensitive values
            if key in _SENSITIVE_KEYS and value and len(value) > 4:
                output[key] = "****" + value[-4:]
            else:
                output[key] = value
        return output

    @staticmethod
    async def get_raw(db: AsyncSession, key: str, default: Optional[str] = None) -> str:
        """Get raw (unmasked) value. Used internally by service factories."""
        result = await db.execute(select(AppSetting).where(AppSetting.key == key))
        row = result.scalar_one_or_none()
        if row is not None:
            return row.value
        fallback = getattr(settings, key, None)
        if fallback is not None:
            return str(fallback)
        return default or ""

    @staticmethod
    async def update_many(db: AsyncSession, data: Dict[str, str]) -> Dict[str, str]:
        """Update multiple settings. Skips masked API keys. Returns full masked settings."""
        for key, value in data.items():
            if key not in _SETTING_KEYS:
                continue
            # Strip whitespace / control characters
            value = value.strip().replace("\t", "").replace("\n", "").replace("\r", "")
            # Skip masked values — user didn't change the key
            if key in _SENSITIVE_KEYS and _MASK_PATTERN.match(value):
                continue
            result = await db.execute(select(AppSetting).where(AppSetting.key == key))
            row = result.scalar_one_or_none()
            if row:
                row.value = value
            else:
                db.add(AppSetting(key=key, value=value))
        await db.flush()
        return await SettingsService.get_all(db)
