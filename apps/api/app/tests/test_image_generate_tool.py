"""Tests for ImageGenerateTool — verifies the never-raise / degrade contract."""

import pytest

from app.tools.base import ToolContext
from app.tools.builtins.image_generate import ImageGenerateTool


@pytest.fixture
def tool():
    return ImageGenerateTool()


def test_manifest_registered_correctly(tool):
    """tool_id matches AGENTS.md §8 and registry auto_register."""
    assert tool.manifest.tool_id == "image_generate"
    assert tool.manifest.category == "generator"
    assert "prompt" in tool.manifest.input_schema["required"]


@pytest.mark.asyncio
async def test_empty_prompt_returns_error(tool):
    """Missing/blank prompt is a hard error (success=False), not a degrade."""
    result = await tool.execute({"prompt": "  "}, ToolContext())

    assert result.success is False
    assert "prompt is required" in (result.error or "")


@pytest.mark.asyncio
async def test_no_db_session_degrades_not_raises(tool):
    """Without a DB session the tool must NOT raise — it returns status=failed."""
    result = await tool.execute({"prompt": "a giant LED wall"}, ToolContext(db=None))

    assert result.success is True  # tool call itself succeeded
    assert result.data["status"] == "failed"
    assert result.data["degraded_reason"] == "no_db_session"
    assert result.data["image_url"] == ""
    assert result.data["prompt"] == "a giant LED wall"


@pytest.mark.asyncio
async def test_mock_provider_returns_degraded_placeholder(tool, db_session, monkeypatch):
    """When the factory returns MockImageGenerationService, surface status=degraded."""
    from app.services.image_service import MockImageGenerationService
    import app.services.settings_service as ss_mod

    async def fake_get_image_service(db):
        return MockImageGenerationService()

    async def fake_get_raw_many(db, keys, defaults=None):
        return {"image_provider": "mock", "image_api_key": ""}

    monkeypatch.setattr(ss_mod.SettingsService, "get_raw_many", staticmethod(fake_get_raw_many))
    monkeypatch.setattr("app.services.image_service.get_image_service", fake_get_image_service)

    result = await tool.execute(
        {"prompt": "city skyline at night", "width": 1024, "height": 768},
        ToolContext(db=db_session),
    )

    assert result.success is True
    assert result.data["status"] == "degraded"
    assert result.data["degraded_reason"] == "mock_provider"
    assert result.data["provider"] == "mock"
    assert result.data["image_url"].startswith("data:image/svg+xml")


@pytest.mark.asyncio
async def test_missing_api_key_degrades_for_real_provider(tool, db_session, monkeypatch):
    """provider=openai but no key configured → failed + no_api_key, no upstream call."""
    import app.services.settings_service as ss_mod

    async def fake_get_raw_many(db, keys, defaults=None):
        return {"image_provider": "openai", "image_api_key": ""}

    monkeypatch.setattr(ss_mod.SettingsService, "get_raw_many", staticmethod(fake_get_raw_many))

    # If this ever gets called, the test must fail loudly.
    async def boom_get_image_service(db):
        raise AssertionError("get_image_service should not be called without api_key")

    monkeypatch.setattr("app.services.image_service.get_image_service", boom_get_image_service)

    result = await tool.execute({"prompt": "x"}, ToolContext(db=db_session))

    assert result.success is True
    assert result.data["status"] == "failed"
    assert result.data["degraded_reason"] == "no_api_key"
    assert result.data["provider"] == "openai"


@pytest.mark.asyncio
async def test_provider_exception_does_not_propagate(tool, db_session, monkeypatch):
    """If the upstream provider raises, the tool must catch it and degrade."""
    import app.services.settings_service as ss_mod

    async def fake_get_raw_many(db, keys, defaults=None):
        return {"image_provider": "openai", "image_api_key": "sk-test"}

    class _BoomService:
        async def generate_image_url(self, **kwargs):
            raise TimeoutError("upstream timeout")

    async def fake_get_image_service(db):
        return _BoomService()

    monkeypatch.setattr(ss_mod.SettingsService, "get_raw_many", staticmethod(fake_get_raw_many))
    monkeypatch.setattr("app.services.image_service.get_image_service", fake_get_image_service)

    result = await tool.execute({"prompt": "x"}, ToolContext(db=db_session))

    assert result.success is True  # never raise
    assert result.data["status"] == "failed"
    assert result.data["degraded_reason"] == "provider_error: TimeoutError"
    assert result.data["image_url"] == ""


@pytest.mark.asyncio
async def test_real_provider_success_returns_ok(tool, db_session, monkeypatch):
    """Happy path: real provider returns a URL → status=ok, no degrade reason."""
    import app.services.settings_service as ss_mod

    async def fake_get_raw_many(db, keys, defaults=None):
        return {"image_provider": "openai", "image_api_key": "sk-test"}

    class _FakeService:
        _model = "dall-e-3"

        async def generate_image_url(self, **kwargs):
            return "https://example.com/generated.png"

    async def fake_get_image_service(db):
        return _FakeService()

    monkeypatch.setattr(ss_mod.SettingsService, "get_raw_many", staticmethod(fake_get_raw_many))
    monkeypatch.setattr("app.services.image_service.get_image_service", fake_get_image_service)

    result = await tool.execute(
        {"prompt": "neon dragon", "style": "vivid"},
        ToolContext(db=db_session),
    )

    assert result.success is True
    assert result.data["status"] == "ok"
    assert result.data["degraded_reason"] == ""
    assert result.data["image_url"] == "https://example.com/generated.png"
    assert result.data["provider"] == "openai"
    assert result.data["prompt"] == "neon dragon"
