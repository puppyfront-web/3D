"""Canvas router — version snapshot, topology, node CRUD.

Endpoints (all under /api/v1, registered in app.main):
  GET    /projects/{pid}/versions          list versions
  POST   /projects/{pid}/versions          snapshot current canvas → new version
  GET    /projects/{pid}/versions/{vid}    version detail
  GET    /projects/{pid}/versions/{vid}/canvas    canvas of a specific version
  POST   /versions/{vid}/restore           restore a historical version (branch)
  GET    /projects/{pid}/canvas            current version's canvas
  GET    /nodes/{nid}                      node detail (with sources)
  PATCH  /nodes/{nid}                      manual node edit

The agent-runs (AI fill) endpoints live in the phase-2 orchestrator and are
not registered here yet (plan §3).
"""

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

logger = logging.getLogger(__name__)
from app.models.canvas import ProjectVersion
from app.models.skill import SkillExecution
from app.models.skill import Skill as SkillModel
from app.schemas.canvas import (
    CanvasNodeCreate,
    CanvasNodeOut,
    CanvasNodeUpdate,
    CanvasOut,
    ProjectVersionCreate,
    ProjectVersionOut,
    VersionRestoreOut,
)
from app.schemas.common import Response
from app.services.canvas_agent_orchestrator import canvas_agent_orchestrator
from app.services.canvas_service import canvas_service

router = APIRouter(tags=["canvas"])


def _to_node_out(node) -> CanvasNodeOut:
    # Sources are loaded eagerly via relationship(lazy="selectin")
    from app.schemas.canvas import NodeSourceOut

    return CanvasNodeOut(
        id=node.id,
        canvas_id=node.canvas_id,
        group_id=node.group_id,
        node_key=node.node_key,
        title=node.title,
        node_type=node.node_type,
        status=node.status,
        priority=node.priority,
        position=node.position,
        content=node.content,
        sources=[NodeSourceOut.model_validate(s) for s in (node.sources or [])],
        created_at=node.created_at,
        updated_at=node.updated_at,
    )


def _to_canvas_out(canvas, is_read_only: bool = False) -> CanvasOut:
    from app.schemas.canvas import CanvasEdgeOut, CanvasGroupOut

    return CanvasOut(
        id=canvas.id,
        project_version_id=canvas.project_version_id,
        viewport=canvas.viewport,
        layout_config=canvas.layout_config,
        groups=[CanvasGroupOut.model_validate(g) for g in canvas.groups],
        nodes=[_to_node_out(n) for n in canvas.nodes],
        edges=[CanvasEdgeOut.model_validate(e) for e in canvas.edges],
        created_at=canvas.created_at,
        is_read_only=is_read_only,
    )


# ─── Versions ────────────────────────────────────────────────────────────────


def _version_to_out(v) -> ProjectVersionOut:
    """Build ProjectVersionOut, merging related-asset aggregates + changed_nodes
    from the version snapshot (PRD §16.3). Falls back to empty when the
    snapshot predates these fields."""
    out = ProjectVersionOut.model_validate(v)
    snapshot = getattr(v, "snapshot", None)
    if isinstance(snapshot, dict):
        rel_mats = snapshot.get("related_materials")
        rel_internal = snapshot.get("related_internal_assets")
        if rel_mats is not None:
            out.related_materials = list(rel_mats)
        if rel_internal is not None:
            out.related_internal_assets = dict(rel_internal)
        changed = snapshot.get("changed_nodes")
        if changed is not None:
            out.changed_nodes = list(changed)
    return out


@router.get("/projects/{project_id}/versions", response_model=Response[list[ProjectVersionOut]])
async def list_versions(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    versions = await canvas_service.list_versions(db, project_id)
    return Response(
        data=[_version_to_out(v) for v in versions],
        message="OK",
    )


@router.post(
    "/projects/{project_id}/versions",
    response_model=Response[ProjectVersionOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_version(
    project_id: uuid.UUID,
    body: Optional[ProjectVersionCreate] = None,
    db: AsyncSession = Depends(get_db),
):
    """Snapshot the project's current canvas into a new version.

    If the project has no version yet, the default three-board topology is
    laid out as V1.
    """
    body = body or ProjectVersionCreate()
    version = await canvas_service.create_version(
        db,
        project_id=project_id,
        version_name=body.version_name,
        change_summary=body.change_summary,
    )
    await db.commit()
    return Response(
        data=_version_to_out(version),
        message=f"Version {version.version_name} created",
    )


@router.get(
    "/projects/{project_id}/versions/{version_id}",
    response_model=Response[ProjectVersionOut],
)
async def get_version(
    project_id: uuid.UUID, version_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    from app.models.canvas import ProjectVersion

    version = await db.get(ProjectVersion, version_id)
    if version is None or version.project_id != project_id:
        from app.core.exceptions import NotFoundException

        raise NotFoundException("ProjectVersion", str(version_id))
    return Response(data=_version_to_out(version))


@router.post(
    "/versions/{version_id}/restore",
    response_model=Response[VersionRestoreOut],
)
async def restore_version(
    version_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """Branch a new current version from a historical snapshot.

    The historical version stays read-only; a brand-new version is created
    from its canvas (PRD §5.3).
    """
    new_version = await canvas_service.restore_version(db, version_id)
    await db.commit()
    return Response(
        data=VersionRestoreOut(
            new_version=_version_to_out(new_version),
            message=f"恢复成功，新版本 {new_version.version_name} 已设为当前",
        )
    )


# ─── Canvas reads ────────────────────────────────────────────────────────────


@router.get(
    "/projects/{project_id}/canvas",
    response_model=Response[CanvasOut],
)
async def get_current_canvas(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    version = await canvas_service.get_current_version(db, project_id)
    canvas = await canvas_service.get_canvas(db, version.id)
    return Response(data=_to_canvas_out(canvas, is_read_only=False))


@router.post(
    "/projects/{project_id}/canvas/relayout",
    response_model=Response,
)
async def relayout_canvas(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    """Recompute the fixed three-column layout and persist new node positions.

    Restores a chaotic canvas (after heavy dragging) to the canonical grid.
    Content/sources/edges are untouched — only positions are reset.
    """
    try:
        moved = await canvas_service.relayout_canvas(db, project_id)
    except ValueError as e:
        from app.core.exceptions import BadRequestException

        raise BadRequestException(str(e))
    return Response(data={"repositioned_nodes": moved}, message=f"已重排 {moved} 个节点")


@router.get(
    "/projects/{project_id}/versions/{version_id}/canvas",
    response_model=Response[CanvasOut],
)
async def get_version_canvas(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    requested_version = await db.get(ProjectVersion, version_id)
    if requested_version is None or requested_version.project_id != project_id:
        from app.core.exceptions import NotFoundException

        raise NotFoundException("ProjectVersion", str(version_id))
    version = await canvas_service.get_current_version(db, project_id)
    is_current = version.id == requested_version.id
    canvas = await canvas_service.get_canvas(db, version_id)
    return Response(data=_to_canvas_out(canvas, is_read_only=not is_current))


# ─── Node CRUD ───────────────────────────────────────────────────────────────


@router.get("/nodes/{node_id}", response_model=Response[CanvasNodeOut])
async def get_node(node_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    node = await canvas_service.get_node(db, node_id)
    return Response(data=_to_node_out(node))


@router.patch(
    "/projects/{project_id}/nodes/{node_id}",
    response_model=Response[CanvasNodeOut],
)
async def update_node(
    project_id: uuid.UUID,
    node_id: uuid.UUID,
    body: CanvasNodeUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Apply a manual node edit. Note: this does NOT auto-snapshot; the caller
    (frontend) decides when to promote a new version via POST .../versions.
    """
    node = await canvas_service.update_node(
        db,
        project_id=project_id,
        node_id=node_id,
        title=body.title,
        status=body.status,
        priority=body.priority,
        position=body.position,
        content=body.content,
    )
    await db.commit()
    # Re-fetch with selectinloaded sources so serialization in _to_node_out
    # does not trigger a lazy load (which would trip MissingGreenlet) after
    # the commit potentially expired the relationship state.
    node = await canvas_service.get_node(db, node_id)
    return Response(data=_to_node_out(node), message="节点已更新")


@router.post(
    "/projects/{project_id}/nodes",
    response_model=Response[CanvasNodeOut],
)
async def add_node(
    project_id: uuid.UUID,
    body: CanvasNodeCreate,
    db: AsyncSession = Depends(get_db),
):
    """Add a custom node to a board (PRD P1 #2: 节点新增).

    Creates a draft node under the given group; the caller snapshots a new
    version via POST .../versions when ready. Renaming is just PATCH with a
    new title, so it reuses the update endpoint.
    """
    node = await canvas_service.add_node(
        db,
        project_id=project_id,
        group_id=body.group_id,
        title=body.title,
        node_key=body.node_key,
        node_type=body.node_type or "module_node",
        position=body.position,
    )
    await db.commit()
    node = await canvas_service.get_node(db, node.id)
    return Response(data=_to_node_out(node), message="节点已新增")


@router.delete(
    "/projects/{project_id}/nodes/{node_id}",
    response_model=Response,
)
async def delete_node(
    project_id: uuid.UUID,
    node_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Remove a module node and its edges (PRD P1 #2: 节点删除).

    Board group nodes are protected; only leaf module nodes can be deleted.
    """
    await canvas_service.delete_node(db, project_id=project_id, node_id=node_id)
    await db.commit()
    return Response(message="节点已删除")


# ─── Agent runs (AI fill) ────────────────────────────────────────────────────


async def _stamp_retrieval_logs(db: AsyncSession, execution_id: uuid.UUID) -> None:
    """Stamp the run's id onto recent retrieval_logs that lack a final_output_id.

    PRD §9.4: every retrieval must link to the generation output it fed. The
    internal-knowledge load inside fill_canvas emits retrieval_logs just before
    the fill; this links the most recent unlinked ones (last 30s window) back
    to this execution so the admin 检索日志 view can replay the chain. Best-effort
    — a failure here never blocks the fill result.
    """
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import update

    from app.models.retrieval import RetrievalLog

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=30)
    try:
        await db.execute(
            update(RetrievalLog)
            .where(RetrievalLog.final_output_id.is_(None))
            .where(RetrievalLog.created_at >= cutoff)
            .values(final_output_id=f"exec:{execution_id}")
        )
    except Exception:
        # Traceability stamping must never fail the fill.
        logger.exception("retrieval_log stamping failed for exec %s", execution_id)


async def _run_fill_background(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    execution_id: uuid.UUID,
    skill_db_id: uuid.UUID,
    stage: str = "full",
    agent_role: str = "canvas_fill",
) -> None:
    """Background task: run the orchestrator against a fresh session and
    update the SkillExecution row with the outcome.

    Runs outside the request DB session, so it opens its own. Wrapped in
    try/except/finally so the execution row is ALWAYS moved out of 'running'
    — even if the LLM call hangs (asyncio.wait_for caps at 120s) or the
    commit fails. The poll endpoint surfaces the error to the frontend.

    ``stage`` selects which agents run (full / ui_expert / tone), letting the
    frontend re-trigger a single stage (e.g. UI 建议) on demand (PRD §13.5).
    """
    import asyncio
    from datetime import datetime, timezone

    from app.db.session import async_session_factory

    FILL_TIMEOUT_SECONDS = 120

    async with async_session_factory() as db:
        execution = await db.get(SkillExecution, execution_id)
        if execution is None:
            return
        try:
            result = await asyncio.wait_for(
                canvas_agent_orchestrator.fill_canvas(
                    db, project_id, version_id,
                    user_id=execution.user_id,
                    stage=stage,
                ),
                timeout=FILL_TIMEOUT_SECONDS,
            )
            execution.status = "succeeded" if result.get("success") else "failed"
            execution.output_json = result
            execution.node_ids = result.get("node_ids")
            execution.agent_role = agent_role
            execution.error_message = None
            if not result.get("success"):
                execution.error_message = (
                    "; ".join(result.get("errors", [])) or "unknown"
                )
            else:
                # PRD §9.4 traceability: stamp this run's id onto the recent
                # retrieval_logs that fed it, so the admin 检索日志 view can link
                # a retrieval back to the generation output it produced.
                await _stamp_retrieval_logs(db, execution_id)
        except asyncio.TimeoutError:
            execution.status = "failed"
            execution.error_message = (
                f"AI 填充超时（>{FILL_TIMEOUT_SECONDS}s），请检查 LLM 配置后重试"
            )
        except Exception as e:
            execution.status = "failed"
            execution.error_message = str(e)
        finally:
            execution.completed_at = datetime.now(timezone.utc)
            try:
                await db.commit()
            except Exception:
                await db.rollback()


@router.post(
    "/projects/{project_id}/agent-runs",
    response_model=Response[dict],
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_agent_run(
    project_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    agent_role: Optional[str] = None,
):
    """Trigger an async AI-fill of the project's current canvas.

    Creates a SkillExecution row (status=running) and dispatches the
    orchestrator as a BackgroundTask. The frontend polls
    GET /agent-runs/{id} until status ∈ {succeeded, failed}.

    Optional ``agent_role`` query/body selects which stage runs:
      - ``canvas_fill`` (default): full planner + tone + UI + consistency
      - ``ui_expert``: UI 专家 only (re-run the UI pass)
      - ``tone``: 方案定调 only
      - ``consistency``: 一致性检查 only (re-run the cross-board review)
    """
    version = await canvas_service.get_current_version(db, project_id)

    role = agent_role or "canvas_fill"
    stage_map = {
        "canvas_fill": "full",
        "ui_expert": "ui_expert",
        "tone": "tone",
        "planner": "planner",
        "consistency": "consistency",
        "requirement": "requirement",
        "document_parse": "document_parse",
    }
    stage = stage_map.get(role, "full")

    # Resolve the seeded Skill row for canvas_fill (best-effort; if missing
    # we still record the execution with a synthetic skill reference).
    skill_row = (
        await db.execute(select(SkillModel).where(SkillModel.skill_id == "canvas_fill"))
    ).scalar_one_or_none()
    if skill_row is None:
        # Fall back to any skill row so the FK holds; the agent_role flag
        # distinguishes canvas-fill runs from normal skill executions.
        skill_row = (await db.execute(select(SkillModel).limit(1))).scalar_one_or_none()
    if skill_row is None:
        from app.core.exceptions import BadRequestException
        raise BadRequestException("No skill rows seeded — run init_db first")

    action_label = {"ui_expert": "ui_only", "tone": "tone_only", "planner": "planner_only", "consistency": "consistency_only", "requirement": "requirement_only", "document_parse": "document_parse_only"}.get(role, "canvas_fill")
    execution = SkillExecution(
        id=uuid.uuid4(),
        skill_id=skill_row.id,
        project_id=project_id,
        status="running",
        input_json={"version_id": str(version.id), "action": action_label, "stage": stage},
        agent_role=role,
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    background_tasks.add_task(
        _run_fill_background,
        project_id,
        version.id,
        execution.id,
        skill_row.id,
        stage,
        role,
    )
    return Response(
        data={
            "execution_id": str(execution.id),
            "status": "running",
            "version_id": str(version.id),
            "agent_role": role,
        },
        message="AI 填充已启动，轮询 /agent-runs/{id} 查询进度",
    )


@router.get("/agent-runs/{execution_id}", response_model=Response[dict])
async def get_agent_run(execution_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Poll an AI-fill execution's status."""
    execution = await db.get(SkillExecution, execution_id)
    if execution is None:
        from app.core.exceptions import NotFoundException
        raise NotFoundException("SkillExecution", str(execution_id))
    return Response(
        data={
            "execution_id": str(execution.id),
            "status": execution.status,
            "agent_role": execution.agent_role,
            "node_ids": execution.node_ids,
            "output": execution.output_json,
            "error": execution.error_message,
        }
    )
