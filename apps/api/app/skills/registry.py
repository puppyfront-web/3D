"""Skill Registry — manages registration and lookup of skill instances."""

import importlib
import inspect
import logging
import pkgutil
from typing import Dict, List, Optional

from app.skills.base import BaseSkill, SkillManifest

logger = logging.getLogger(__name__)


class SkillRegistry:
    """Central registry for all available skills."""

    _instance: Optional["SkillRegistry"] = None
    _skills: Dict[str, BaseSkill]

    def __init__(self) -> None:
        self._skills: Dict[str, BaseSkill] = {}

    @classmethod
    def get_instance(cls) -> "SkillRegistry":
        """Get the singleton registry instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, skill: BaseSkill) -> None:
        """Register a skill instance by its manifest skill_id."""
        skill_id = skill.manifest.skill_id
        if skill_id in self._skills:
            logger.warning("Overwriting already-registered skill: %s", skill_id)
        self._skills[skill_id] = skill
        logger.info("Registered skill: %s (%s)", skill_id, skill.manifest.name)

    def get(self, skill_id: str) -> Optional[BaseSkill]:
        """Look up a skill by its ID."""
        return self._skills.get(skill_id)

    def list_skills(self) -> List[SkillManifest]:
        """Return manifests for all registered skills."""
        return [skill.manifest for skill in self._skills.values()]

    def has(self, skill_id: str) -> bool:
        """Check if a skill is registered."""
        return skill_id in self._skills

    def auto_register(self) -> None:
        """Discover and register all built-in skills from the builtins package.

        Uses ``pkgutil.iter_modules`` to scan ``app/skills/builtins/`` so newly
        added skills are picked up automatically instead of being silently
        missing when forgotten in a hard-coded import list.

        The previous hard-coded list (company_analysis, case_retrieval,
        proposal_generation, visual_prompt, image_generation, export) is kept
        below as a reference; discovery replaces it.

        Discovery rules:
          * Every module in the builtins package is imported.
          * ``BaseSkill`` subclasses are located via ``inspect.getmembers``.
          * A class is registered only when it is a concrete subclass of
            ``BaseSkill`` *and* actually defined in that module (its
            ``__module__`` equals the module name) — this prevents the imported
            ``BaseSkill`` base class itself from being registered and avoids
            double-registration of a class re-exported by another module.
          * Each module is wrapped in its own try/except so one broken import
            doesn't prevent the rest from loading.
        """
        import app.skills.builtins as builtins_pkg

        pkg_path = builtins_pkg.__path__
        pkg_prefix = builtins_pkg.__name__ + "."

        for _finder, mod_name, _is_pkg in pkgutil.iter_modules(pkg_path, pkg_prefix):
            try:
                module = importlib.import_module(mod_name)
            except Exception:  # noqa: BLE001 — don't let one module kill startup
                logger.exception("Failed to import skill module: %s", mod_name)
                continue

            found_in_module = 0
            for _attr, cls in inspect.getmembers(module, inspect.isclass):
                if not (inspect.isclass(cls) and issubclass(cls, BaseSkill)):
                    continue
                if cls is BaseSkill:
                    continue
                # Only register classes actually defined in *this* module —
                # skips re-exported imports and the base class itself.
                if cls.__module__ != mod_name:
                    continue
                try:
                    self.register(cls())
                    found_in_module += 1
                except Exception:  # noqa: BLE001
                    logger.exception(
                        "Failed to instantiate skill %s from %s", cls.__name__, mod_name
                    )

            logger.debug("Module %s contributed %d skill(s)", mod_name, found_in_module)

        self._validate_required_services()
        logger.info("Auto-registered %d built-in skills", len(self._skills))

    def _validate_required_services(self) -> None:
        """Validate that each skill's required_services map to registered tools.

        For every registered skill we map each ``required_services`` entry to a
        concrete tool_id via :data:`app.skills.base.REQUIRED_SERVICE_TO_TOOL`.
        When a required service maps to a tool that is NOT present in the
        :class:`ToolRegistry`, we emit an ``error`` log.

        This never raises — a missing optional tool should not block startup,
        but the operator must be warned.

        NOTE: skills can be auto-registered before tools (several module-level
        call sites like ``routers/skills.py`` run at import time, ahead of the
        app lifespan that registers tools). When the ToolRegistry is still
        empty we SKIP validation rather than spamming false-positive errors;
        the lifespan registers tools right after, and any genuinely missing
        tool surfaces at execution time via the skill's own guard.
        """
        # Local import avoids a circular dependency at module load time.
        from app.skills.base import REQUIRED_SERVICE_TO_TOOL
        from app.tools.registry import ToolRegistry

        tool_registry = ToolRegistry.get_instance()
        # Tools not registered yet (early auto-register) → nothing to validate.
        if not tool_registry.list_tools():
            return

        for skill in self._skills.values():
            skill_id = skill.manifest.skill_id
            for svc in skill.manifest.required_services:
                tool_id = REQUIRED_SERVICE_TO_TOOL.get(svc)
                if tool_id is None:
                    # None => injected service (LLM/embedding/export), not a tool.
                    continue
                if not tool_registry.has(tool_id):
                    logger.error(
                        "Skill '%s' requires tool '%s' (from required_service '%s') "
                        "which is not registered",
                        skill_id,
                        tool_id,
                        svc,
                    )
