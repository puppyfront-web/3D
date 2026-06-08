"""Rule Query Tools — query technical rules and quality rules."""

from typing import Any, Dict

from sqlalchemy import select

from app.models.rule import TechnicalRule, QualityRule
from app.tools.base import BaseTool, ToolContext, ToolManifest, ToolResult


class TechRuleQueryTool(BaseTool):
    """Query active technical rules, optionally filtered by category and severity."""

    manifest = ToolManifest(
        tool_id="tech_rule_query",
        name="技术规则查询",
        description="查询活跃的技术规则，用于方案生成时的技术约束校验",
        category="validator",
        input_schema={
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "规则类别筛选"},
                "severity": {"type": "string", "description": "严重程度筛选"},
                "limit": {"type": "integer", "description": "返回数量上限", "default": 10},
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "rules": {"type": "array"},
                "total": {"type": "integer"},
            },
        },
    )

    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        if context.db is None:
            return ToolResult(success=False, error="No database session")

        category = params.get("category")
        severity = params.get("severity")
        limit = min(params.get("limit", 10), 50)

        stmt = select(TechnicalRule).where(TechnicalRule.is_active == True)  # noqa: E712
        if category:
            stmt = stmt.where(TechnicalRule.category == category)
        if severity:
            stmt = stmt.where(TechnicalRule.severity == severity)
        stmt = stmt.limit(limit)

        result = await context.db.execute(stmt)
        rules = result.scalars().all()

        rule_list = [
            {
                "id": str(r.id),
                "name": r.name,
                "category": r.category,
                "description": r.description,
                "rule_text": r.rule_text,
                "severity": r.severity,
            }
            for r in rules
        ]

        return ToolResult(success=True, data={"rules": rule_list, "total": len(rule_list)})


class QualityRuleQueryTool(BaseTool):
    """Query active quality rules, optionally filtered by category."""

    manifest = ToolManifest(
        tool_id="quality_rule_query",
        name="质量标准查询",
        description="查询活跃的质量标准规则，用于生成内容的质量校验",
        category="validator",
        input_schema={
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "规则类别筛选"},
                "limit": {"type": "integer", "description": "返回数量上限", "default": 5},
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "rules": {"type": "array"},
                "total": {"type": "integer"},
            },
        },
    )

    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        if context.db is None:
            return ToolResult(success=False, error="No database session")

        category = params.get("category")
        limit = min(params.get("limit", 5), 50)

        stmt = select(QualityRule).where(QualityRule.is_active == True)  # noqa: E712
        if category:
            stmt = stmt.where(QualityRule.category == category)
        stmt = stmt.limit(limit)

        result = await context.db.execute(stmt)
        rules = result.scalars().all()

        rule_list = [
            {
                "id": str(r.id),
                "name": r.name,
                "category": r.category,
                "description": r.description,
                "rule_text": r.rule_text,
                "weight": r.weight,
            }
            for r in rules
        ]

        return ToolResult(success=True, data={"rules": rule_list, "total": len(rule_list)})
