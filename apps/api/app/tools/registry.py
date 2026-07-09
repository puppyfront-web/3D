"""Tool Registry — singleton store for all registered Tools.

Mirrors skills/registry.py for consistency.
"""

import importlib
import inspect
import logging
import pkgutil
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
        """Import and register all built-in Tools via package auto-discovery.

        Uses ``pkgutil.iter_modules`` to scan ``app/tools/builtins/`` so newly
        added tools are picked up automatically instead of being silently
        missing when forgotten in a hard-coded import list.

        The previous hard-coded list (case_search, sop_load,
        prompt_template_load, template_load, visual_style_match, rule_query →
        TechRuleQueryTool & QualityRuleQueryTool, company_profile_load,
        knowledge_search, web_search, image_generate) is kept below as a
        reference; discovery replaces it.

        Discovery rules:
          * Every module in the builtins package is imported.
          * ``BaseTool`` subclasses are located via ``inspect.getmembers``.
          * A class is registered only when it is a concrete subclass of
            ``BaseTool`` *and* actually defined in that module (its
            ``__module__`` equals the module name) — this prevents the imported
            ``BaseTool`` base class itself from being registered and avoids
            double-registration of a class re-exported by another module.
          * Each module is wrapped in its own try/except so one broken import
            doesn't prevent the rest from loading.
        """
        import app.tools.builtins as builtins_pkg

        pkg_path = builtins_pkg.__path__
        pkg_prefix = builtins_pkg.__name__ + "."

        for _finder, mod_name, _is_pkg in pkgutil.iter_modules(pkg_path, pkg_prefix):
            try:
                module = importlib.import_module(mod_name)
            except Exception:  # noqa: BLE001 — don't let one module kill startup
                logger.exception("Failed to import tool module: %s", mod_name)
                continue

            found_in_module = 0
            for _attr, cls in inspect.getmembers(module, inspect.isclass):
                if not (inspect.isclass(cls) and issubclass(cls, BaseTool)):
                    continue
                if cls is BaseTool:
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
                        "Failed to instantiate tool %s from %s", cls.__name__, mod_name
                    )

            logger.debug("Module %s contributed %d tool(s)", mod_name, found_in_module)

        logger.info("Auto-registered %d tools", len(self._tools))
