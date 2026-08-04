"""Production contract: get_llm_service must NOT fall back to MockLLMService.

A missing/unsupported provider fails loudly so misconfiguration surfaces
instead of serving fabricated LLM output. Mock injection in tests is the
conftest autouse fixture's job, never the factory's.
"""

import inspect

# Capture the real factory at import time, BEFORE the conftest autouse fixture
# monkeypatches app.services.llm_service.get_llm_service. The fixture replaces
# the module attribute later, but this reference still points at the original
# function object — which is what we want to audit.
from app.services import llm_service as _llm_mod

_orig_get_llm_service = _llm_mod.get_llm_service


def test_factory_has_no_mock_fallback_path():
    """The factory body must not contain `return MockLLMService()` — the mock
    fallback was removed. It must raise RuntimeError on missing provider."""
    src = inspect.getsource(_orig_get_llm_service)
    assert "return MockLLMService()" not in src, (
        "get_llm_service still returns MockLLMService — mock fallback must be "
        "removed so a missing provider fails loudly"
    )
    assert "raise RuntimeError" in src, (
        "get_llm_service must raise on unconfigured/unsupported provider"
    )


def test_defaults_do_not_seed_mock():
    """Built-in defaults + the Settings class field default must not seed
    'mock' — empty provider is the new 'unconfigured' state that triggers the
    loud failure. Reads the pydantic field default (not the .env-loaded
    settings instance) so a stray LLM_PROVIDER in .env doesn't mask a code
    regression."""
    from app.services import settings_service
    from app.core.config import Settings

    assert settings_service._BUILTIN_DEFAULTS["llm_provider"] == "", (
        "llm_provider default must be empty (was 'mock') so the factory raises"
    )
    field_default = Settings.model_fields["llm_provider"].default
    assert field_default == "", (
        f"Settings.llm_provider field default must be '' (got {field_default!r})"
    )
