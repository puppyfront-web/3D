"""Canvas service — default topology, version snapshots, restore.

Implements the snapshot-based version model (technical design §5, PRD §16):

  - ``create_default_canvas_for_project`` lays out the three-board topology
    (company_intro / product_tech_scenarios / future_social_responsibility)
    with 21 default nodes — a fresh project's V1.
  - ``create_version`` snapshots the current canvas state into a new
    ProjectVersion, demotes the previous current version, and points the
    project at the new version. Runs in the caller's transaction so the
    router can enforce a single-transaction boundary (§20.2).
  - ``restore_version`` reads a historical snapshot and branches a new current
    version from it — the old current is NOT overwritten (§5.3).

The default topology mirrors PRD §10.2. Cultural-tourism (文旅) nodes are
intentionally excluded per the project's industry scope decision.
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.models.canvas import (
    Canvas,
    CanvasEdge,
    CanvasGroup,
    CanvasNode,
    NodeSource,
    ProjectVersion,
)
from app.models.project import Project

logger = logging.getLogger(__name__)

# ─── Default topology definition (PRD §10.2) ────────────────────────────────
# Each group carries an ordered list of (node_key, title) leaf nodes. Node
# keys are stable identifiers used by the AI-fill orchestrator (phase 2) to
# route each node to the right skill. Cultural-tourism nodes excluded.

_DEFAULT_GROUPS: List[Dict[str, Any]] = [
    {
        "group_key": "company_intro",
        "title": "企业介绍",
        "description": "企业基本情况、规模、历程与资质",
        "nodes": [
            ("company_profile", "企业简介"),
            ("company_scale", "企业规模"),
            ("development_history", "发展历程"),
            ("honors_qualifications", "荣誉资质"),
            ("enterprise_spirit", "企业精神"),
            ("team_capability", "团队能力"),
            ("core_value", "核心价值"),
        ],
    },
    {
        "group_key": "product_tech_scenarios",
        "title": "产品 / 技术 / 应用场景",
        "description": "产品体系、技术能力、应用场景与典型案例",
        "nodes": [
            ("product_system", "产品体系"),
            ("technology_capability", "技术能力"),
            ("application_scenarios", "应用场景"),
            ("typical_cases", "典型案例"),
            ("solutions", "解决方案"),
            ("delivery_capability", "交付能力"),
            ("customer_value", "客户价值"),
        ],
    },
    {
        "group_key": "future_social_responsibility",
        "title": "未来 / 社会责任",
        "description": "未来布局、发展战略、社会责任与品牌愿景",
        "nodes": [
            ("future_layout", "未来布局"),
            ("development_strategy", "发展战略"),
            ("social_responsibility", "社会责任"),
            ("public_welfare", "公益价值"),
            ("party_building", "党建内容"),
            ("sustainable_development", "可持续发展"),
            ("brand_vision", "品牌愿景"),
        ],
    },
]

# Layout constants — three columns side by side, nodes stacked within a group.
_GROUP_WIDTH = 360
_GROUP_GAP_X = 80
_GROUP_START_X = 40
_GROUP_START_Y = 40
_NODE_OFFSET_Y = 40  # gap between consecutive node positions inside a group


class CanvasService:
    """Manages canvas creation, version snapshots, and restore."""

    # ─── Default topology ──────────────────────────────────────────────────

    async def create_default_canvas(
        self,
        db: AsyncSession,
        project_version_id: uuid.UUID,
    ) -> Canvas:
        """Lay out the default three-board topology for a fresh version.

        Creates the Canvas, three CanvasGroups, 21 default CanvasNodes (all
        ``status=draft``), and the intra-group sequential edges. Does not
        commit — caller controls the transaction.
        """
        canvas = Canvas(
            id=uuid.uuid4(),
            project_version_id=project_version_id,
            viewport={"x": 0, "y": 0, "zoom": 0.8},
            layout_config={"algo": "fixed-three-column", "theme": "blue"},
        )
        db.add(canvas)
        await db.flush()  # populate canvas.id

        group_position_x = _GROUP_START_X
        node_id_by_key: Dict[str, uuid.UUID] = {}

        for col_idx, gdef in enumerate(_DEFAULT_GROUPS):
            group = CanvasGroup(
                id=uuid.uuid4(),
                canvas_id=canvas.id,
                group_key=gdef["group_key"],
                title=gdef["title"],
                description=gdef.get("description"),
                position={"x": group_position_x, "y": _GROUP_START_Y},
                style={"theme": "blue", "column": col_idx},
            )
            db.add(group)
            await db.flush()

            prev_node_id: Optional[uuid.UUID] = None
            for row_idx, (node_key, title) in enumerate(gdef["nodes"]):
                node = CanvasNode(
                    id=uuid.uuid4(),
                    canvas_id=canvas.id,
                    group_id=group.id,
                    node_key=node_key,
                    title=title,
                    node_type="module_node",
                    status="draft",
                    position={
                        "x": group_position_x + 20,
                        "y": _GROUP_START_Y + 80 + row_idx * _NODE_OFFSET_Y * 3,
                    },
                    content={
                        "extracted": [],
                        "planning": [],
                        "ui_suggestion": [],
                        "pending_questions": [],
                    },
                )
                db.add(node)
                await db.flush()
                node_id_by_key[node_key] = node.id

                # Sequential edge within the group (prev → cur).
                if prev_node_id is not None:
                    edge = CanvasEdge(
                        id=uuid.uuid4(),
                        canvas_id=canvas.id,
                        source_node_id=prev_node_id,
                        target_node_id=node.id,
                        edge_type="sequence",
                        label=None,
                        metadata_json={"group_key": gdef["group_key"]},
                    )
                    db.add(edge)
                prev_node_id = node.id

            group_position_x += _GROUP_WIDTH + _GROUP_GAP_X

        await db.flush()
        return canvas

    async def relayout_canvas(
        self,
        db: AsyncSession,
        project_id: uuid.UUID,
    ) -> int:
        """Recompute and persist the fixed three-column layout for the project's
        current version canvas. Returns the number of nodes repositioned.

        Resets group + node positions to the canonical grid so a user can
        recover from a chaotic drag state. Does not touch node content,
        sources, or edges — only positions.
        """
        project = await db.get(Project, project_id)
        if not project or not project.current_version_id:
            raise ValueError("项目尚无当前版本")
        canvas = await self._get_canvas_for_version(db, project.current_version_id)
        if not canvas:
            raise ValueError("当前版本没有画布")

        groups = (
            (await db.execute(
                select(CanvasGroup)
                .where(CanvasGroup.canvas_id == canvas.id)
                .order_by(CanvasGroup.created_at)
            ))
            .scalars()
            .all()
        )
        nodes = (
            (await db.execute(
                select(CanvasNode)
                .where(CanvasNode.canvas_id == canvas.id)
                .order_by(CanvasNode.created_at)
            ))
            .scalars()
            .all()
        )

        group_by_id = {g.id: g for g in groups}
        # Index groups by creation order to assign columns left→right.
        ordered_group_ids = [g.id for g in groups]
        col_by_group_id = {gid: idx for idx, gid in enumerate(ordered_group_ids)}

        # Bucket nodes by group, preserve their created_at order within a group.
        nodes_by_group: Dict[uuid.UUID, List[CanvasNode]] = {g.id: [] for g in groups}
        for n in nodes:
            if n.group_id in nodes_by_group:
                nodes_by_group[n.group_id].append(n)

        moved = 0
        for group_id, grp_nodes in nodes_by_group.items():
            col_idx = col_by_group_id.get(group_id, 0)
            group_position_x = _GROUP_START_X + col_idx * (_GROUP_WIDTH + _GROUP_GAP_X)
            # Reset the group position too.
            group = group_by_id.get(group_id)
            if group is not None:
                group.position = {"x": group_position_x, "y": _GROUP_START_Y}
            for row_idx, node in enumerate(grp_nodes):
                new_pos = {
                    "x": group_position_x + 20,
                    "y": _GROUP_START_Y + 80 + row_idx * _NODE_OFFSET_Y * 3,
                }
                if node.position != new_pos:
                    node.position = new_pos
                    moved += 1

        await db.flush()
        return moved

    async def _get_canvas_for_version(
        self, db: AsyncSession, version_id: uuid.UUID
    ) -> Optional[Canvas]:
        result = await db.execute(
            select(Canvas).where(Canvas.project_version_id == version_id)
        )
        return result.scalars().first()

    # ─── Version creation ─────────────────────────────────────────────────

    async def create_version(
        self,
        db: AsyncSession,
        project_id: uuid.UUID,
        version_name: Optional[str] = None,
        change_summary: Optional[str] = None,
        based_on_version_id: Optional[uuid.UUID] = None,
        created_by: Optional[uuid.UUID] = None,
    ) -> ProjectVersion:
        """Snapshot the project's current canvas into a new ProjectVersion.

        Flow (single transaction, owned by the caller):
          1. compute next version_no
          2. create ProjectVersion + snapshot blob
          3. if there is an existing current canvas, copy groups/nodes/edges
             into the new version's canvas (the snapshot point)
          4. demote the previous is_current version
          5. mark the new version is_current=True
          6. point project.current_version_id at the new version

        On a brand-new project (no current version yet) we instead lay out the
        default three-board topology.
        """
        project = await db.get(Project, project_id)
        if project is None:
            raise NotFoundException("Project", str(project_id))

        next_no = await self._next_version_no(db, project_id)

        version = ProjectVersion(
            id=uuid.uuid4(),
            project_id=project_id,
            version_no=next_no,
            version_name=version_name or f"V{next_no}",
            change_summary=change_summary or "初始版本",
            based_on_version_id=based_on_version_id,
            is_current=True,
            snapshot={},  # filled after canvas build
            created_by=created_by,
        )
        db.add(version)
        await db.flush()

        prev_canvas = await self._get_canvas_for_version_id(
            db, project.current_version_id
        ) if project.current_version_id else None

        if prev_canvas is not None:
            new_canvas = await self._clone_canvas_into_version(
                db, version.id, prev_canvas
            )
        else:
            new_canvas = await self.create_default_canvas(db, version.id)

        # Force relationships to reload — newly-added children aren't visible
        # on the parent's collection until the parent is expired/refreshed,
        # and accessing them lazily here would trip MissingGreenlet in async.
        await db.refresh(new_canvas, ["groups", "nodes", "edges"])

        # 版本总结 Agent (PRD §13.2 step 9 / §16.1): when the caller did not
        # pass an explicit change_summary, derive a data-grounded one from the
        # actual canvas state instead of stamping the generic "初始版本". The
        # first version (no previous canvas) keeps the default; subsequent
        # saves get a fill-rate + related-assets sentence the user can read in
        # the version-detail panel.
        if change_summary is None and prev_canvas is not None:
            change_summary = self._summarize_version(new_canvas)

        # PRD §16.3 changed_nodes: diff the new snapshot against the PREVIOUS
        # version's snapshot so the version-detail panel can list exactly
        # which nodes changed (added / removed / content / status). The first
        # version (no previous) gets an empty list.
        prev_snapshot: Optional[Dict[str, Any]] = None
        if project.current_version_id:
            prev_version = await db.get(ProjectVersion, project.current_version_id)
            if prev_version is not None:
                prev_snapshot = prev_version.snapshot or None

        version.snapshot = self._build_snapshot(
            new_canvas, change_summary, prev_snapshot=prev_snapshot,
        )
        if change_summary:
            version.change_summary = change_summary

        # Demote previous current versions of this project.
        await db.execute(
            update(ProjectVersion)
            .where(
                ProjectVersion.project_id == project_id,
                ProjectVersion.id != version.id,
                ProjectVersion.is_current.is_(True),
            )
            .values(is_current=False)
        )
        project.current_version_id = version.id

        await db.flush()
        return version

    # ─── Version restore ──────────────────────────────────────────────────

    async def restore_version(
        self,
        db: AsyncSession,
        version_id: uuid.UUID,
        created_by: Optional[uuid.UUID] = None,
    ) -> ProjectVersion:
        """Branch a new current version from a historical snapshot.

        The historical version stays read-only; we create a NEW version whose
        canvas is rebuilt from the snapshot (PRD §5.3: "恢复历史版本后再次编辑
        → 生成新版本，不覆盖当前"). Returns the new current version.
        """
        src = await db.get(ProjectVersion, version_id)
        if src is None:
            raise NotFoundException("ProjectVersion", str(version_id))

        return await self.create_version(
            db,
            project_id=src.project_id,
            version_name=None,
            change_summary=f"从 {src.version_name or 'V' + str(src.version_no)} 恢复",
            based_on_version_id=src.id,
            created_by=created_by,
        )

    # ─── Read helpers ─────────────────────────────────────────────────────

    async def ensure_initial_version(
        self, db: AsyncSession, project_id: uuid.UUID
    ) -> ProjectVersion:
        """Create V1 with default topology if the project has no version yet.

        Used at project-creation time (wizard) so a fresh project lands in the
        Canvas workspace with a usable V1 — the frontend's first paint no
        longer has to POST ``/versions`` to bootstrap. Idempotent: if the
        project already has a current version, return it untouched.
        """
        project = await db.get(Project, project_id)
        if project is None:
            raise NotFoundException("Project", str(project_id))
        if project.current_version_id:
            return await self.get_current_version(db, project_id)
        return await self.create_version(
            db,
            project_id=project_id,
            version_name="V1",
            change_summary="项目创建初始版本",
        )

    async def get_current_version(
        self, db: AsyncSession, project_id: uuid.UUID
    ) -> ProjectVersion:
        project = await db.get(Project, project_id)
        if project is None:
            raise NotFoundException("Project", str(project_id))
        if project.current_version_id is None:
            raise BadRequestException(
                "Project has no version yet — create one first"
            )
        version = await db.get(ProjectVersion, project.current_version_id)
        if version is None:
            raise NotFoundException("ProjectVersion", str(project.current_version_id))
        return version

    async def list_versions(
        self, db: AsyncSession, project_id: uuid.UUID
    ) -> List[ProjectVersion]:
        result = await db.execute(
            select(ProjectVersion)
            .where(ProjectVersion.project_id == project_id)
            .order_by(ProjectVersion.version_no.desc())
        )
        return list(result.scalars().all())

    async def get_canvas(
        self, db: AsyncSession, version_id: uuid.UUID
    ) -> Canvas:
        # selectinload groups/nodes/edges so the serialized output reflects the
        # live table (including nodes just added/deleted in the same session)
        # rather than a stale relationship cached in the identity map.
        # populate_existing() forces SQLAlchemy to overwrite the cached canvas
        # row + its relationships with fresh DB state.
        result = await db.execute(
            select(Canvas)
            .options(
                selectinload(Canvas.groups),
                selectinload(Canvas.nodes).selectinload(CanvasNode.sources),
                selectinload(Canvas.edges),
            )
            .execution_options(populate_existing=True)
            .where(Canvas.project_version_id == version_id)
        )
        canvas = result.scalar_one_or_none()
        if canvas is None:
            raise NotFoundException("Canvas for version", str(version_id))
        return canvas

    async def add_node(
        self,
        db: AsyncSession,
        project_id: uuid.UUID,
        group_id: uuid.UUID,
        title: str,
        node_key: Optional[str] = None,
        node_type: str = "module_node",
        position: Optional[Dict[str, Any]] = None,
    ) -> CanvasNode:
        """Add a custom node to a board (PRD P1 #2: 节点新增).

        Validates the group belongs to the project's current (mutable)
        version, then stacks the node below the board's existing nodes.
        Returns the created node with sources eager-loaded.
        """
        # Resolve the group + its canvas/version, enforce project + currency.
        result = await db.execute(
            select(CanvasGroup)
            .options(selectinload(CanvasGroup.canvas))
            .where(CanvasGroup.id == group_id)
        )
        group = result.scalar_one_or_none()
        if group is None:
            raise NotFoundException("CanvasGroup", str(group_id))
        canvas = group.canvas
        version = await db.get(ProjectVersion, canvas.project_version_id)
        if version is None or version.project_id != project_id:
            raise ForbiddenException("Group does not belong to the requested project")
        if not version.is_current:
            raise ForbiddenException("Historical versions are read-only")

        # Auto-position: stack below the lowest existing node in this group.
        if position is None:
            existing = (
                await db.execute(
                    select(CanvasNode)
                    .where(CanvasNode.group_id == group_id)
                    .order_by(CanvasNode.position["y"].asc())
                )
            ).scalars().all()
            base_y = _GROUP_START_Y + 80
            step = _NODE_OFFSET_Y * 3
            max_y = max(
                (float((n.position or {}).get("y", base_y)) for n in existing),
                default=base_y,
            )
            position = {
                "x": (group.position or {}).get("x", _GROUP_START_X) + 20,
                "y": max_y + step,
            }

        # Synthetic node_key if the caller did not supply one — keep it stable
        # and unique-ish so the AI-fill orchestrator can still address it.
        if not node_key:
            node_key = f"custom_{uuid.uuid4().hex[:8]}"

        node = CanvasNode(
            id=uuid.uuid4(),
            canvas_id=canvas.id,
            group_id=group_id,
            node_key=node_key,
            title=title,
            node_type=node_type,
            status="draft",
            position=position,
            content={
                "extracted": [],
                "planning": [],
                "ui_suggestion": [],
                "pending_questions": [],
            },
        )
        db.add(node)
        await db.flush()
        await db.refresh(node, ["sources"])
        return node

    async def delete_node(
        self,
        db: AsyncSession,
        project_id: uuid.UUID,
        node_id: uuid.UUID,
    ) -> None:
        """Remove a node and its edges (PRD P1 #2: 节点删除).

        Group-header nodes (the three boards) are protected from deletion —
        only leaf ``module_node`` rows may be removed. Edges referencing the
        node are cleaned up so the canvas stays consistent.
        """
        node = await self.get_node(db, node_id)
        version = await self.get_version_for_node(db, node_id)
        if version.project_id != project_id:
            raise ForbiddenException("Node does not belong to the requested project")
        if not version.is_current:
            raise ForbiddenException("Historical versions are read-only")
        if node.node_type != "module_node":
            raise BadRequestException("板块节点不可删除，仅可删除模块节点")

        # Remove edges that touch this node, then the node itself.
        await db.execute(
            CanvasEdge.__table__.delete().where(
                (CanvasEdge.source_node_id == node_id)
                | (CanvasEdge.target_node_id == node_id)
            )
        )
        await db.delete(node)
        await db.flush()

    async def get_node(
        self, db: AsyncSession, node_id: uuid.UUID
    ) -> CanvasNode:
        # Use selectinload via refresh to populate the sources relationship —
        # db.get() alone leaves selectin relationships unloaded and the router
        # serializes node.sources, which would trip MissingGreenlet.
        result = await db.execute(
            select(CanvasNode)
            .options(selectinload(CanvasNode.sources))
            .where(CanvasNode.id == node_id)
        )
        node = result.scalar_one_or_none()
        if node is None:
            raise NotFoundException("CanvasNode", str(node_id))
        return node

    async def get_version_for_node(
        self, db: AsyncSession, node_id: uuid.UUID
    ) -> ProjectVersion:
        """Resolve which project version owns a node."""
        result = await db.execute(
            select(ProjectVersion)
            .join(Canvas, Canvas.project_version_id == ProjectVersion.id)
            .join(CanvasNode, CanvasNode.canvas_id == Canvas.id)
            .where(CanvasNode.id == node_id)
        )
        version = result.scalar_one_or_none()
        if version is None:
            raise NotFoundException("ProjectVersion for node", str(node_id))
        return version

    async def update_node(
        self,
        db: AsyncSession,
        project_id: uuid.UUID,
        node_id: uuid.UUID,
        title: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        position: Optional[Dict[str, Any]] = None,
        content: Optional[Dict[str, Any]] = None,
    ) -> CanvasNode:
        """Apply a partial manual edit to a node (no auto-version here — the
        router decides whether to snapshot)."""
        node = await self.get_node(db, node_id)
        version = await self.get_version_for_node(db, node_id)
        if version.project_id != project_id:
            raise ForbiddenException("Node does not belong to the requested project")
        if not version.is_current:
            raise ForbiddenException("Historical versions are read-only")
        if title is not None:
            node.title = title
        if status is not None:
            node.status = status
        if priority is not None:
            node.priority = priority
        if position is not None:
            node.position = position
        if content is not None:
            node.content = content
        await db.flush()
        # Refresh the sources relationship so serialization in the router does
        # not trigger a lazy load outside an async greenlet.
        await db.refresh(node, ["sources"])
        return node

    # ─── Internals ────────────────────────────────────────────────────────

    async def _next_version_no(
        self, db: AsyncSession, project_id: uuid.UUID
    ) -> int:
        result = await db.execute(
            select(func.max(ProjectVersion.version_no)).where(
                ProjectVersion.project_id == project_id
            )
        )
        current_max = result.scalar()
        return (current_max or 0) + 1

    async def _get_canvas_for_version_id(
        self, db: AsyncSession, version_id: Optional[uuid.UUID]
    ) -> Optional[Canvas]:
        if version_id is None:
            return None
        # Eager-load groups/nodes/edges + populate_existing so a fresh node
        # added to the canvas earlier in the SAME session is visible here.
        # Without populate_existing, the identity-map cache returns the stale
        # relationship collection (missing the new node), and create_version's
        # clone would silently drop it — the V3-after-adding-a-node case.
        result = await db.execute(
            select(Canvas)
            .options(
                selectinload(Canvas.groups),
                selectinload(Canvas.nodes).selectinload(CanvasNode.sources),
                selectinload(Canvas.edges),
            )
            .execution_options(populate_existing=True)
            .where(Canvas.project_version_id == version_id)
        )
        return result.scalar_one_or_none()

    async def _clone_canvas_into_version(
        self,
        db: AsyncSession,
        new_version_id: uuid.UUID,
        src: Canvas,
    ) -> Canvas:
        """Deep-copy a source canvas (groups/nodes/edges/sources) into a new
        version.

        Node sources are cloned too so a historical version's provenance is
        preserved and the version-detail panel can list related materials /
        SOPs / cases / templates for any version, not just the live current
        canvas (PRD §16.3 / §23.6).
        """
        new_canvas = Canvas(
            id=uuid.uuid4(),
            project_version_id=new_version_id,
            viewport=src.viewport,
            layout_config=src.layout_config,
        )
        db.add(new_canvas)
        await db.flush()

        # Map old node ids → new node ids so edges + sources can be re-pointed.
        old_to_new_node: Dict[uuid.UUID, uuid.UUID] = {}
        old_to_new_group: Dict[uuid.UUID, uuid.UUID] = {}

        for g in src.groups:
            new_g = CanvasGroup(
                id=uuid.uuid4(),
                canvas_id=new_canvas.id,
                group_key=g.group_key,
                title=g.title,
                description=g.description,
                position=g.position,
                style=g.style,
            )
            db.add(new_g)
            await db.flush()
            old_to_new_group[g.id] = new_g.id

        for n in src.nodes:
            new_n = CanvasNode(
                id=uuid.uuid4(),
                canvas_id=new_canvas.id,
                group_id=old_to_new_group.get(n.group_id) if n.group_id else None,
                node_key=n.node_key,
                title=n.title,
                node_type=n.node_type,
                status=n.status,
                priority=n.priority,
                position=n.position,
                content=n.content,
            )
            db.add(new_n)
            await db.flush()
            old_to_new_node[n.id] = new_n.id
            # Clone provenance so historical versions keep their source list.
            for s in (n.sources or []):
                db.add(NodeSource(
                    id=uuid.uuid4(),
                    node_id=new_n.id,
                    source_type=s.source_type,
                    source_name=s.source_name,
                    source_ref_id=s.source_ref_id,
                    confidence=s.confidence,
                    quote=s.quote,
                    metadata_json=s.metadata_json,
                ))

        for e in src.edges:
            new_e = CanvasEdge(
                id=uuid.uuid4(),
                canvas_id=new_canvas.id,
                source_node_id=old_to_new_node[e.source_node_id],
                target_node_id=old_to_new_node[e.target_node_id],
                edge_type=e.edge_type,
                label=e.label,
                metadata_json=e.metadata_json,
            )
            db.add(new_e)

        await db.flush()
        return new_canvas

    def _summarize_version(self, canvas: Canvas) -> str:
        """版本总结 Agent — derive a human-readable change summary (PRD §16.1).

        Aggregates the canvas's node fill state and referenced knowledge
        assets into one sentence, so the version-detail panel shows something
        meaningful instead of the generic "初始版本". Pure data roll-up — no
        LLM call, deterministic, safe to run inside the version transaction.
        """
        nodes = list(canvas.nodes or [])
        total = len(nodes)
        filled = sum(1 for n in nodes if n.status == "filled")
        pending = sum(1 for n in nodes if n.status == "pending_review")

        # Roll up referenced materials + internal assets from node sources.
        materials: List[str] = []
        sop: List[str] = []
        cases: List[str] = []
        templates: List[str] = []
        for n in nodes:
            for s in (n.sources or []):
                name = s.source_name or s.source_ref_id
                if not name:
                    continue
                if s.source_type == "uploaded_file" and name not in materials:
                    materials.append(name)
                elif s.source_type == "internal_sop" and name not in sop:
                    sop.append(name)
                elif s.source_type == "internal_case" and name not in cases:
                    cases.append(name)
                elif s.source_type == "internal_template" and name not in templates:
                    templates.append(name)

        parts: List[str] = []
        if total:
            parts.append(f"共 {total} 个节点，其中 {filled} 个已填充")
            if pending:
                parts.append(f"{pending} 个待确认")
        if materials:
            parts.append(f"引用资料 {len(materials)} 份")
        ref_knowledge = []
        if sop:
            ref_knowledge.append(f"{len(sop)} 个 SOP")
        if cases:
            ref_knowledge.append(f"{len(cases)} 个案例")
        if templates:
            ref_knowledge.append(f"{len(templates)} 个模板")
        if ref_knowledge:
            parts.append("引用" + "、".join(ref_knowledge))
        return "，".join(parts) + "。" if parts else "保存当前画布快照"

    @staticmethod
    def _diff_nodes(
        prev_snapshot: Optional[Dict[str, Any]],
        cur_nodes: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Compute the per-node change set between two snapshots (PRD §16.3).

        Indexes both sides by ``node_key`` (falls back to title) and classifies
        each node as added / removed / content / status / title. A node whose
        extracted/planning/ui_suggestion/pending_questions slots all match the
        prior version is unchanged and excluded. First version (no prev) → [].

        Returns ``[{"nodeKey", "title", "change": "added|removed|content|status|title"}]``
        ordered added → content/status/title → removed for stable display.
        """
        if not prev_snapshot:
            return []
        prev_nodes_list = prev_snapshot.get("nodes") or []
        # Index by node_key, falling back to title for custom nodes without one.
        def _key(n: Dict[str, Any]) -> str:
            return (n.get("node_key") or n.get("title") or "") or ""

        prev_by_key: Dict[str, Dict[str, Any]] = {}
        for n in prev_nodes_list:
            k = _key(n)
            if k:
                prev_by_key[k] = n
        cur_by_key: Dict[str, Dict[str, Any]] = {}
        for n in cur_nodes:
            k = _key(n)
            if k:
                cur_by_key[k] = n

        def _slots(n: Dict[str, Any]) -> Dict[str, Any]:
            c = n.get("content") or {}
            return {
                "extracted": c.get("extracted") or [],
                "planning": c.get("planning") or [],
                "ui_suggestion": c.get("ui_suggestion") or [],
                "pending_questions": c.get("pending_questions") or [],
            }

        changes: List[Dict[str, Any]] = []
        for k, cur in cur_by_key.items():
            prev = prev_by_key.get(k)
            if prev is None:
                changes.append({"nodeKey": k, "title": cur.get("title"), "change": "added"})
                continue
            # Changed: content slots, status, or title.
            if _slots(cur) != _slots(prev):
                changes.append({"nodeKey": k, "title": cur.get("title"), "change": "content"})
            elif (cur.get("status") or "") != (prev.get("status") or ""):
                changes.append({"nodeKey": k, "title": cur.get("title"), "change": "status"})
            elif (cur.get("title") or "") != (prev.get("title") or ""):
                changes.append({"nodeKey": k, "title": cur.get("title"), "change": "title"})
        for k, prev in prev_by_key.items():
            if k not in cur_by_key:
                changes.append({"nodeKey": k, "title": prev.get("title"), "change": "removed"})
        return changes

    def _build_snapshot(
        self,
        canvas: Canvas,
        change_summary: Optional[str],
        prev_snapshot: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Serialize the canvas into a self-contained snapshot blob.

        Includes per-node sources so the version-detail panel can surface the
        related materials / SOP / cases / templates a version used (PRD §16.3)
        without re-resolving against the live canvas.

        When ``prev_snapshot`` is supplied (the immediately-prior version's
        snapshot), also computes ``changed_nodes`` — the per-node diff (added /
        removed / content / status / title) so PRD §16.3's "变更节点" panel
        can list exactly what this version changed.
        """
        # Aggregate related assets across all node sources for quick display.
        related_materials: List[str] = []
        related_internal: Dict[str, List[str]] = {
            "internal_sop": [],
            "internal_case": [],
            "internal_template": [],
            "internal_ui": [],
        }
        for n in canvas.nodes:
            for s in (n.sources or []):
                name = s.source_name or s.source_ref_id or s.source_type
                if s.source_type == "uploaded_file":
                    if name not in related_materials:
                        related_materials.append(name)
                elif s.source_type in related_internal:
                    if name not in related_internal[s.source_type]:
                        related_internal[s.source_type].append(name)

        nodes_blob = [
            {
                "node_key": n.node_key,
                "title": n.title,
                "node_type": n.node_type,
                "status": n.status,
                "priority": n.priority,
                "position": n.position,
                "content": n.content,
                "sources": [
                    {
                        "source_type": s.source_type,
                        "source_name": s.source_name,
                        "confidence": s.confidence,
                    }
                    for s in (n.sources or [])
                ],
            }
            for n in canvas.nodes
        ]

        return {
            "viewport": canvas.viewport,
            "layout_config": canvas.layout_config,
            "groups": [
                {
                    "group_key": g.group_key,
                    "title": g.title,
                    "description": g.description,
                    "position": g.position,
                    "style": g.style,
                }
                for g in canvas.groups
            ],
            "nodes": nodes_blob,
            "edges_count": len(canvas.edges),
            # PRD §16.3 变更节点 — diff against the prior version's snapshot.
            "changed_nodes": self._diff_nodes(prev_snapshot, nodes_blob),
            "change_logs": [{"summary": change_summary or "初始版本"}],
            # PRD §16.3 / §23.6 — surfaced in the version-detail panel.
            "related_materials": related_materials,
            "related_internal_assets": related_internal,
        }


canvas_service = CanvasService()
