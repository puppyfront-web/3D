"""Skill Registry — manages registration and lookup of skill instances."""

import logging
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
        """Discover and register all built-in skills from the builtins package."""
        from app.skills.builtins import (
            CaseRetrievalSkill,
            CompanyAnalysisSkill,
            ExportSkill,
            ImageGenerationSkill,
            ProposalGenerationSkill,
            VisualPromptSkill,
        )

        for skill_cls in [
            CompanyAnalysisSkill,
            CaseRetrievalSkill,
            ProposalGenerationSkill,
            VisualPromptSkill,
            ImageGenerationSkill,
            ExportSkill,
        ]:
            instance = skill_cls()
            self.register(instance)

        logger.info("Auto-registered %d built-in skills", len(self._skills))
