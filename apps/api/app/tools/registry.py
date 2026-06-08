"""Tool Registry — singleton store for all registered Tools.

Mirrors skills/registry.py for consistency.
"""

import logging
from typing import Dict, List, Optional

from app.tools.base import BaseTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Singleton registry that holds all available Tools."""

    _instance: Optional["ToolRegistry"] = None

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}

    @classmethod
    def get_instance(cls) -> "ToolRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, tool: BaseTool) -> None:
        tool_id = tool.manifest.tool_id
        if tool_id in self._tools:
            logger.warning("Tool %s already registered, overwriting", tool_id)
        self._tools[tool_id] = tool
        logger.debug("Registered tool: %s", tool_id)

    def get(self, tool_id: str) -> Optional[BaseTool]:
        return self._tools.get(tool_id)

    def has(self, tool_id: str) -> bool:
        return tool_id in self._tools

    def list_tools(self) -> List[dict]:
        return [
            {
                "tool_id": t.manifest.tool_id,
                "name": t.manifest.name,
                "description": t.manifest.description,
                "category": t.manifest.category,
            }
            for t in self._tools.values()
        ]

    def auto_register(self) -> None:
        """Import and register all built-in Tools."""
        from app.tools.builtins.case_search import CaseSearchTool
        from app.tools.builtins.sop_load import SOPLoadTool
        from app.tools.builtins.prompt_template_load import PromptTemplateLoadTool
        from app.tools.builtins.template_load import TemplateLoadTool
        from app.tools.builtins.visual_style_match import VisualStyleMatchTool
        from app.tools.builtins.rule_query import TechRuleQueryTool, QualityRuleQueryTool
        from app.tools.builtins.company_profile_load import CompanyProfileLoadTool
        from app.tools.builtins.knowledge_search import KnowledgeSearchTool

        for cls in [
            CaseSearchTool,
            SOPLoadTool,
            PromptTemplateLoadTool,
            TemplateLoadTool,
            VisualStyleMatchTool,
            TechRuleQueryTool,
            QualityRuleQueryTool,
            CompanyProfileLoadTool,
            KnowledgeSearchTool,
        ]:
            self.register(cls())
        logger.info("Auto-registered %d tools", len(self._tools))
