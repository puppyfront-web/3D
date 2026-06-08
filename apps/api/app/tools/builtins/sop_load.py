"""SOP Load Tool — load SOP workflow by ID or industry."""

from typing import Any, Dict

from sqlalchemy import select

from app.models.workflow import SOPWorkflow
from app.tools.base import BaseTool, ToolContext, ToolManifest, ToolResult


class SOPLoadTool(BaseTool):
    """Load a SOP workflow definition by ID or find the best match by name."""

    manifest = ToolManifest(
        tool_id="sop_load",
        name="SOP 工作流加载",
        description="按 ID 或名称加载 SOP 工作流定义，返回步骤和阶段",
        category="loader",
        input_schema={
            "type": "object",
            "properties": {
                "sop_id": {"type": "string", "description": "SOP 工作流 UUID"},
                "name_contains": {"type": "string", "description": "按名称模糊匹配"},
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "sop": {"type": "object", "description": "SOP 工作流定义（steps, pipeline_stages）"},
            },
        },
    )

    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        if context.db is None:
            return ToolResult(success=False, error="No database session")

        import uuid as _uuid

        sop_id = params.get("sop_id")
        name_contains = params.get("name_contains")

        sop = None
        if sop_id:
            sop = await context.db.get(SOPWorkflow, _uuid.UUID(sop_id))
        elif name_contains:
            stmt = (
                select(SOPWorkflow)
                .where(
                    SOPWorkflow.is_active == True,  # noqa: E712
                    SOPWorkflow.name.ilike(f"%{name_contains}%"),
                )
                .limit(1)
            )
            result = await context.db.execute(stmt)
            sop = result.scalar_one_or_none()

        if not sop:
            return ToolResult(success=True, data={"sop": None})

        return ToolResult(
            success=True,
            data={
                "sop": {
                    "id": str(sop.id),
                    "name": sop.name,
                    "description": sop.description,
                    "version": sop.version,
                    "steps": sop.steps or [],
                    "pipeline_stages": sop.pipeline_stages or [],
                },
            },
        )
