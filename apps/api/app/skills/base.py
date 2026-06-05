"""Base classes for the Skill Runtime system."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SkillManifest:
    """Metadata definition for a skill."""

    skill_id: str
    name: str
    description: str
    category: str
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    required_services: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    visibility: str = "internal"
    version: str = "1.0.0"


@dataclass
class SkillContext:
    """Runtime context injected by the SkillRunner."""

    project_id: Optional[str] = None
    user_id: Optional[str] = None
    db: Any = None  # AsyncSession — use Any to avoid circular imports
    llm_service: Any = None
    embedding_service: Any = None
    image_service: Any = None
    retrieval_service: Any = None


@dataclass
class SkillResult:
    """Structured output from a skill execution."""

    success: bool = True
    output: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    used_cases: List[str] = field(default_factory=list)
    used_documents: List[str] = field(default_factory=list)
    used_chunks: List[str] = field(default_factory=list)
    missing_info: List[str] = field(default_factory=list)
    duration_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "used_cases": self.used_cases,
            "used_documents": self.used_documents,
            "used_chunks": self.used_chunks,
            "missing_info": self.missing_info,
            "duration_ms": self.duration_ms,
        }


class BaseSkill(ABC):
    """Abstract base class for all skills."""

    manifest: SkillManifest

    @abstractmethod
    async def execute(self, input_data: Dict[str, Any], context: SkillContext) -> SkillResult:
        """Execute the skill with validated input. Return structured output."""

    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """Validate input against manifest.input_schema required fields."""
        required = self.manifest.input_schema.get("required", [])
        return all(key in input_data for key in required)

    def get_manifest(self) -> SkillManifest:
        """Return the skill's manifest."""
        return self.manifest
