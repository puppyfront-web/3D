"""Settings service — runtime configuration sourced exclusively from the database.

All provider/web-search configuration is managed via the admin settings UI and
persisted in the app_settings table. There is NO .env fallback: a setting not in
the database is treated as unset (callers receive "" or a supplied default).
"""

import re
from typing import Dict, Iterable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_setting import AppSetting

# All known setting keys — the whitelist for get_all enumeration and update
# validation. Only these keys are accepted by PUT /settings and returned by
# GET /settings (everything else is ignored).
_SETTING_KEYS = {
    "llm_provider",
    "llm_api_key",
    "llm_base_url",
    "llm_model",
    "embedding_provider",
    "embedding_api_key",
    "embedding_base_url",
    "embedding_model",
    "image_provider",
    "image_api_key",
    "image_base_url",
    "image_model",
    "image_quality",
    "embedding_dimensions",
    # Web search — Tavily-first, LLM-native fallback, degraded-notice last resort.
    "web_search_enabled",
    "web_search_mode",
    "web_search_tavily_api_key",
    "web_search_max_results",
    "web_search_timeout",
    "web_search_min_confidence",
}

# Keys that contain sensitive data
_SENSITIVE_KEYS = {"llm_api_key", "embedding_api_key", "image_api_key", "web_search_tavily_api_key"}

# Built-in defaults for non-sensitive settings. These are NOT read from .env —
# they are sensible code-level fallbacks shown in the admin UI before the user
# first persists a value. Once a setting is saved to the database, the DB value
# always wins. Sensitive keys (API keys) have no default (empty until configured).
_BUILTIN_DEFAULTS: Dict[str, str] = {
    "llm_provider": "mock",
    "llm_model": "gpt-4o",
    "embedding_provider": "mock",
    "embedding_model": "text-embedding-3-small",
    "embedding_dimensions": "1536",
    "image_provider": "mock",
    "image_model": "dall-e-3",
    "image_quality": "high",
    "web_search_enabled": "true",
    "web_search_mode": "auto",
    "web_search_max_results": "5",
    "web_search_timeout": "15",
    "web_search_min_confidence": "0.5",
}

_MASK_PATTERN = re.compile(r"^\*{4}")


class SettingsService:
    """Read/write application settings sourced exclusively from the database."""

    @staticmethod
    async def get(db: AsyncSession, key: str, default: Optional[str] = None) -> str:
        """Get a single setting value from the database only.

        No .env fallback — all configuration is managed via the admin settings UI
        and persisted in app_settings. Missing keys return the provided default.
        """
        result = await db.execute(select(AppSetting).where(AppSetting.key == key))
        row = result.scalar_one_or_none()
        if row is not None:
            return row.value
        return default or ""

    @staticmethod
    async def get_all(db: AsyncSession) -> Dict[str, str]:
        """Get all known settings from the database only. Masks sensitive keys.

        No .env fallback — only persisted values are returned. Keys with no DB
        row are omitted (the frontend treats absent keys as unset).
        """
        # Load all DB rows at once
        result = await db.execute(select(AppSetting))
        db_map = {row.key: row.value for row in result.scalars().all()}

        output: Dict[str, str] = {}
        for key in _SETTING_KEYS:
            if key in db_map:
                value = db_map[key]
            else:
                # No DB row → built-in default (empty string if none).
                # This is a code-level default, NOT a .env read.
                value = _BUILTIN_DEFAULTS.get(key, "")
            # Mask sensitive values
            if key in _SENSITIVE_KEYS and value and len(value) > 4:
                output[key] = "****" + value[-4:]
            else:
                output[key] = value
        return output

    @staticmethod
    async def get_raw(db: AsyncSession, key: str, default: Optional[str] = None) -> str:
        """Get raw (unmasked) value from the database only. Used by service factories."""
        result = await db.execute(select(AppSetting).where(AppSetting.key == key))
        row = result.scalar_one_or_none()
        if row is not None:
            return row.value
        return default or ""

    @staticmethod
    async def get_raw_many(
        db: AsyncSession,
        keys: Iterable[str],
        defaults: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """Get multiple raw (unmasked) values from the database in a single round-trip.

        No .env fallback — only persisted values are returned. Missing keys fall
        back to the per-key defaults passed by the caller.
        """
        defaults = defaults or {}
        key_list = list(keys)
        result = await db.execute(select(AppSetting).where(AppSetting.key.in_(key_list)))
        db_map = {row.key: row.value for row in result.scalars().all()}

        output: Dict[str, str] = {}
        for key in key_list:
            if key in db_map:
                output[key] = db_map[key]
            else:
                # DB miss → caller default, else built-in default, else "".
                output[key] = defaults.get(key, _BUILTIN_DEFAULTS.get(key, ""))
        return output

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
