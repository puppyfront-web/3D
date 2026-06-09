"""Visual Concept Generation Agent — 多轮对话状态机驱动的视觉概念图生成工作流。"""

from __future__ import annotations

import copy
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Literal, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SSE chunk helper
# ---------------------------------------------------------------------------


def _sse_chunk(
    chunk_type: str,
    text: Optional[str] = None,
    data: Optional[Dict] = None,
) -> str:
    """Build an SSE-formatted string for streaming to the frontend."""
    payload: Dict[str, Any] = {"type": chunk_type}
    if text is not None:
        payload["text"] = text
    if data is not None:
        payload["data"] = data
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@dataclass
class ModificationEntry:
    """修改追踪条目。"""

    round: int
    user_instruction: str
    parsed_changes: Dict[str, Any]
    previous_requirement: Dict[str, Any]


@dataclass
class VisualRequirement:
    """从用户自然语言中提取的结构化需求。"""

    raw_input: str = ""
    scene: Optional[str] = None
    screen_type: Optional[str] = None
    brand_or_theme: Optional[str] = None
    visual_style: Optional[str] = None
    color_tone: Optional[str] = None
    target_audience: Optional[str] = None
    key_elements: List[str] = field(default_factory=list)
    constraints: Optional[str] = None
    reference_case_ids: List[str] = field(default_factory=list)
    modification_log: List[ModificationEntry] = field(default_factory=list)

    # 可合并的需求字段名列表
    _MERGEABLE_FIELDS = [
        "scene",
        "screen_type",
        "brand_or_theme",
        "visual_style",
        "color_tone",
        "target_audience",
        "constraints",
    ]

    def merge_field(self, field_name: str, value: Any) -> None:
        """合并用户回答到需求字段。"""
        if field_name in self._MERGEABLE_FIELDS:
            setattr(self, field_name, value)
        elif field_name == "key_elements":
            if isinstance(value, list):
                self.key_elements.extend(value)
            else:
                self.key_elements.append(str(value))

    def get_missing_critical_fields(self) -> List[str]:
        """返回缺失的关键字段名列表。"""
        critical = ["scene", "visual_style"]
        return [f for f in critical if getattr(self, f) is None]

    def has_enough_info(self) -> bool:
        """判断是否有足够信息开始生成。"""
        has_scene_or_screen = (
            self.scene is not None or self.screen_type is not None
        )
        has_style = self.visual_style is not None
        return has_scene_or_screen and has_style

    def add_modification(
        self, round: int, instruction: str, parsed_changes: Dict[str, Any]
    ) -> None:
        """记录一次修改，保存修改前的需求快照。"""
        snapshot = self.to_dict()
        self.modification_log.append(
            ModificationEntry(
                round=round,
                user_instruction=instruction,
                parsed_changes=parsed_changes,
                previous_requirement=snapshot,
            )
        )
        # 应用修改
        for key, value in parsed_changes.items():
            self.merge_field(key, value)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_input": self.raw_input,
            "scene": self.scene,
            "screen_type": self.screen_type,
            "brand_or_theme": self.brand_or_theme,
            "visual_style": self.visual_style,
            "color_tone": self.color_tone,
            "target_audience": self.target_audience,
            "key_elements": self.key_elements,
            "constraints": self.constraints,
            "reference_case_ids": self.reference_case_ids,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VisualRequirement":
        req = cls(raw_input=data.get("raw_input", ""))
        for f in cls._MERGEABLE_FIELDS:
            if f in data and data[f] is not None:
                setattr(req, f, data[f])
        if "key_elements" in data:
            req.key_elements = data["key_elements"]
        if "constraints" in data:
            req.constraints = data["constraints"]
        if "reference_case_ids" in data:
            req.reference_case_ids = data["reference_case_ids"]
        if "modification_log" in data:
            req.modification_log = [
                ModificationEntry(**e) if isinstance(e, dict) else e
                for e in data["modification_log"]
            ]
        return req


# ---------------------------------------------------------------------------
# Version Tree — 版本树数据模型，支持分支、回滚、序列化
# ---------------------------------------------------------------------------


@dataclass
class VersionNode:
    """版本树中的单个节点，记录一次生成的完整快照。"""

    node_id: str
    parent_id: Optional[str] = None
    branch_id: str = "main"
    version_label: str = ""
    requirement_snapshot: Dict[str, Any] = field(default_factory=dict)
    visual_strategy: Optional[Dict[str, Any]] = None
    positive_prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    prompt_template_used: Optional[str] = None
    image_url: Optional[str] = None
    image_metadata: Optional[Dict[str, Any]] = None
    quality_check: Optional[Dict[str, Any]] = None
    rag_citations: List[Dict[str, Any]] = field(default_factory=list)
    status: Literal["completed", "active", "abandoned"] = "completed"
    children_ids: List[str] = field(default_factory=list)
    trigger: Literal["initial", "modify", "branch", "rollback"] = "initial"
    user_instruction: Optional[str] = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "parent_id": self.parent_id,
            "branch_id": self.branch_id,
            "version_label": self.version_label,
            "requirement_snapshot": self.requirement_snapshot,
            "visual_strategy": self.visual_strategy,
            "positive_prompt": self.positive_prompt,
            "negative_prompt": self.negative_prompt,
            "prompt_template_used": self.prompt_template_used,
            "image_url": self.image_url,
            "image_metadata": self.image_metadata,
            "quality_check": self.quality_check,
            "rag_citations": self.rag_citations,
            "status": self.status,
            "children_ids": self.children_ids,
            "trigger": self.trigger,
            "user_instruction": self.user_instruction,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VersionNode":
        return cls(
            node_id=data["node_id"],
            parent_id=data.get("parent_id"),
            branch_id=data.get("branch_id", "main"),
            version_label=data.get("version_label", ""),
            requirement_snapshot=data.get("requirement_snapshot", {}),
            visual_strategy=data.get("visual_strategy"),
            positive_prompt=data.get("positive_prompt"),
            negative_prompt=data.get("negative_prompt"),
            prompt_template_used=data.get("prompt_template_used"),
            image_url=data.get("image_url"),
            image_metadata=data.get("image_metadata"),
            quality_check=data.get("quality_check"),
            rag_citations=data.get("rag_citations", []),
            status=data.get("status", "completed"),
            children_ids=data.get("children_ids", []),
            trigger=data.get("trigger", "initial"),
            user_instruction=data.get("user_instruction"),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            completed_at=data.get("completed_at"),
        )


@dataclass
class BranchMeta:
    """分支元数据。"""

    branch_id: str
    branch_name: str
    root_node_id: str
    current_node_id: str
    status: Literal["active", "merged", "abandoned"] = "active"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "branch_id": self.branch_id,
            "branch_name": self.branch_name,
            "root_node_id": self.root_node_id,
            "current_node_id": self.current_node_id,
            "status": self.status,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BranchMeta":
        return cls(
            branch_id=data["branch_id"],
            branch_name=data["branch_name"],
            root_node_id=data["root_node_id"],
            current_node_id=data["current_node_id"],
            status=data.get("status", "active"),
            created_at=data.get(
                "created_at", datetime.now(timezone.utc).isoformat()
            ),
        )


@dataclass
class VersionTree:
    """版本树：管理生成历史的分支、回滚与序列化。"""

    nodes: Dict[str, VersionNode] = field(default_factory=dict)
    root_id: Optional[str] = None
    active_branch: str = "main"
    branches: Dict[str, BranchMeta] = field(default_factory=dict)

    def __init__(self, root: VersionNode):
        self.nodes = {root.node_id: root}
        self.root_id = root.node_id
        self.active_branch = "main"
        self.branches = {
            "main": BranchMeta(
                branch_id="main",
                branch_name="主线",
                root_node_id=root.node_id,
                current_node_id=root.node_id,
            )
        }

    def add_node(self, node: VersionNode) -> None:
        """添加子节点，更新父节点的 children_ids 和分支的 current_node_id。"""
        self.nodes[node.node_id] = node
        if node.parent_id and node.parent_id in self.nodes:
            parent = self.nodes[node.parent_id]
            if node.node_id not in parent.children_ids:
                parent.children_ids.append(node.node_id)
        # 更新分支的当前节点
        if node.branch_id in self.branches:
            self.branches[node.branch_id].current_node_id = node.node_id

    def create_branch(
        self, branch_id: str, branch_name: str, root_node: VersionNode
    ) -> None:
        """创建新分支。"""
        self.branches[branch_id] = BranchMeta(
            branch_id=branch_id,
            branch_name=branch_name,
            root_node_id=root_node.node_id,
            current_node_id=root_node.node_id,
        )

    def rollback_to(self, target_node_id: str) -> None:
        """回滚到指定节点，将同分支中的所有后代节点标记为 abandoned。"""
        if target_node_id not in self.nodes:
            return
        target = self.nodes[target_node_id]
        branch_id = target.branch_id

        # 递归收集所有后代节点
        def _collect_descendants(nid: str) -> List[str]:
            node = self.nodes.get(nid)
            if not node:
                return []
            result = []
            for child_id in node.children_ids:
                child = self.nodes.get(child_id)
                if child and child.branch_id == branch_id:
                    result.append(child_id)
                    result.extend(_collect_descendants(child_id))
            return result

        descendants = _collect_descendants(target_node_id)
        for did in descendants:
            self.nodes[did].status = "abandoned"

        # 更新分支当前节点
        if branch_id in self.branches:
            self.branches[branch_id].current_node_id = target_node_id

    def switch_branch(self, branch_id: str) -> None:
        """切换活跃分支。"""
        if branch_id in self.branches:
            self.active_branch = branch_id

    def get_current_node(self) -> Optional[VersionNode]:
        """获取当前活跃分支的最新节点。"""
        branch = self.branches.get(self.active_branch)
        if branch:
            return self.nodes.get(branch.current_node_id)
        return None

    def get_branch_nodes(self, branch_id: str) -> List[VersionNode]:
        """获取指定分支的所有节点，按 created_at 排序。"""
        branch_nodes = [
            n for n in self.nodes.values() if n.branch_id == branch_id
        ]
        branch_nodes.sort(key=lambda n: n.created_at)
        return branch_nodes

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
            "root_id": self.root_id,
            "active_branch": self.active_branch,
            "branches": {
                bid: b.to_dict() for bid, b in self.branches.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VersionTree":
        nodes = {
            nid: VersionNode.from_dict(n)
            for nid, n in data.get("nodes", {}).items()
        }
        branches = {
            bid: BranchMeta.from_dict(b)
            for bid, b in data.get("branches", {}).items()
        }
        root_id = data.get("root_id")
        if not root_id or root_id not in nodes:
            raise ValueError("Invalid VersionTree data: missing or invalid root_id")

        # 重建 VersionTree 实例，绕过 __init__ 以避免重复创建 main 分支
        tree = cls.__new__(cls)
        tree.nodes = nodes
        tree.root_id = root_id
        tree.active_branch = data.get("active_branch", "main")
        tree.branches = branches
        return tree


# ---------------------------------------------------------------------------
# VisualConceptContext — Agent 持有的对话上下文状态机
# ---------------------------------------------------------------------------


@dataclass
class VisualConceptContext:
    """Agent 持有的对话上下文，序列化存储在 Message.metadata_json 中。"""

    state: Literal[
        "COLLECTING", "PLANNING", "PROMPTING",
        "GENERATING", "REVIEWING", "COMPLETED"
    ] = "COLLECTING"

    requirement: VisualRequirement = field(default_factory=VisualRequirement)
    ask_round: int = 0
    max_ask_rounds: int = 3
    missing_info: List[str] = field(default_factory=list)

    version_tree: Optional[VersionTree] = None
    current_node_id: Optional[str] = None
    current_branch_id: str = "main"

    # Auto-filled from project context
    auto_filled: Dict[str, str] = field(default_factory=dict)
    project_context_loaded: bool = False

    def should_ask_more(self) -> bool:
        return self.ask_round < self.max_ask_rounds

    def create_initial_node(self) -> VersionNode:
        """创建第一个版本节点（触发 PLANNING 时调用）。"""
        node = VersionNode(
            node_id=str(uuid.uuid4()),
            branch_id="main",
            version_label="V1",
            trigger="initial",
            requirement_snapshot=self.requirement.to_dict(),
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        self.version_tree = VersionTree(root=node)
        self.current_node_id = node.node_id
        return node

    def create_next_version(
        self,
        trigger: Literal["modify", "branch", "rollback"] = "modify",
        user_instruction: Optional[str] = None,
        branch_id: Optional[str] = None,
        branch_name: Optional[str] = None,
    ) -> VersionNode:
        """创建下一个版本节点。"""
        target_branch = branch_id or self.current_branch_id
        existing_count = len([n for n in self.version_tree.nodes.values() if n.branch_id == target_branch])
        label = f"V{existing_count + 1}"
        if branch_id and branch_id != "main":
            label = f"V{existing_count + 1}'"

        node = VersionNode(
            node_id=str(uuid.uuid4()),
            parent_id=self.current_node_id,
            branch_id=target_branch,
            version_label=label,
            trigger=trigger,
            user_instruction=user_instruction,
            requirement_snapshot=self.requirement.to_dict(),
            completed_at=datetime.now(timezone.utc).isoformat(),
        )

        if branch_id and branch_id not in self.version_tree.branches:
            self.version_tree.create_branch(branch_id, branch_name or branch_id, node)

        self.version_tree.add_node(node)
        self.current_node_id = node.node_id
        self.current_branch_id = target_branch
        return node

    def get_current_node(self) -> Optional[VersionNode]:
        if self.version_tree and self.current_node_id:
            return self.version_tree.nodes.get(self.current_node_id)
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "requirement": self.requirement.to_dict(),
            "ask_round": self.ask_round,
            "max_ask_rounds": self.max_ask_rounds,
            "missing_info": self.missing_info,
            "version_tree": self.version_tree.to_dict() if self.version_tree else None,
            "current_node_id": self.current_node_id,
            "current_branch_id": self.current_branch_id,
            "auto_filled": self.auto_filled,
            "project_context_loaded": self.project_context_loaded,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VisualConceptContext":
        ctx = cls()
        ctx.state = data.get("state", "COLLECTING")
        ctx.requirement = VisualRequirement.from_dict(data.get("requirement", {}))
        ctx.ask_round = data.get("ask_round", 0)
        ctx.max_ask_rounds = data.get("max_ask_rounds", 3)
        ctx.missing_info = data.get("missing_info", [])
        ctx.current_node_id = data.get("current_node_id")
        ctx.current_branch_id = data.get("current_branch_id", "main")
        ctx.auto_filled = data.get("auto_filled", {})
        ctx.project_context_loaded = data.get("project_context_loaded", False)
        if data.get("version_tree"):
            ctx.version_tree = VersionTree.from_dict(data["version_tree"])
        return ctx


# ---------------------------------------------------------------------------
# Parameter card constants — 预定义选项，避免 LLM 追问
# ---------------------------------------------------------------------------

FIELD_LABELS: Dict[str, str] = {
    "scene": "使用场景",
    "visual_style": "视觉风格",
    "screen_type": "屏幕类型",
    "brand_or_theme": "品牌/主题",
    "color_tone": "色调",
    "target_audience": "目标受众",
}

FIELD_OPTIONS: Dict[str, List[Dict[str, str]]] = {
    "scene": [
        {"label": "品牌发布会", "value": "品牌发布会"},
        {"label": "商场展示", "value": "商场展示"},
        {"label": "户外广告", "value": "户外广告"},
        {"label": "展厅互动", "value": "展厅互动"},
        {"label": "企业大堂", "value": "企业大堂"},
    ],
    "visual_style": [
        {"label": "科技感", "value": "科技感"},
        {"label": "国潮风", "value": "国潮风"},
        {"label": "简约商务", "value": "简约商务"},
        {"label": "未来主义", "value": "未来主义"},
        {"label": "自然生态", "value": "自然生态"},
    ],
}


# ---------------------------------------------------------------------------
# VisualConceptAgent — state-machine driven visual concept generation
# ---------------------------------------------------------------------------


class VisualConceptAgent:
    """Agent that drives the full COLLECTING → … → COMPLETED state machine.

    The agent is *stateless* by itself — all per-conversation state lives in a
    ``VisualConceptContext`` instance that the caller persists (e.g. inside
    ``Message.metadata_json``).
    """

    name: str = "visual_concept"

    def __init__(
        self,
        llm_service: Optional[Any] = None,
        image_service: Optional[Any] = None,
        embedding_service: Optional[Any] = None,
    ):
        self._llm = llm_service
        self._image = image_service
        self._embedding = embedding_service

    async def _ensure_services(self, db=None):
        """Lazily initialize services (needed because __init__ cannot be async)."""
        if self._llm is None:
            from app.services.llm_service import get_llm_service
            self._llm = await get_llm_service(db)
        if self._image is None:
            from app.services.image_service import get_image_service
            self._image = await get_image_service(db)
        if self._embedding is None:
            from app.services.embedding_service import get_embedding_service
            self._embedding = await get_embedding_service(db)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def handle_message(
        self,
        user_input: str,
        ctx: VisualConceptContext,
        db: Optional[Any] = None,
        project_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Route *user_input* to the correct handler based on ``ctx.state``.

        Yields SSE-formatted chunks that the frontend can consume directly.
        """
        await self._ensure_services(db)
        try:
            # --- Auto-fill from project context on first COLLECTING entry ---
            if (
                ctx.state == "COLLECTING"
                and not ctx.project_context_loaded
                and project_id
                and db
            ):
                project_ctx = await self._load_project_context(project_id, db)
                if project_ctx:
                    # Emit context card to show user what was auto-loaded
                    yield _sse_chunk("context_card", data=project_ctx)
                    # Merge auto-filled fields into requirement
                    for fname, fval in project_ctx.get("auto_filled", {}).items():
                        ctx.requirement.merge_field(fname, fval)
                    ctx.auto_filled = project_ctx.get("auto_filled", {})
                    ctx.project_context_loaded = True

                    # If context provides all critical fields, skip to pipeline
                    if not ctx.requirement.get_missing_critical_fields():
                        ctx.requirement.raw_input = (
                            f"{ctx.requirement.raw_input}\n{user_input}".strip()
                            if ctx.requirement.raw_input
                            else user_input
                        )
                        ctx.create_initial_node()
                        async for chunk in self._run_full_pipeline(ctx, db):
                            yield chunk
                        return

            if ctx.state == "REVIEWING":
                async for chunk in self._handle_reviewing(user_input, ctx, db):
                    yield chunk
            else:
                # COLLECTING (or any transient state treated as collecting)
                async for chunk in self._handle_collecting(user_input, ctx, db):
                    yield chunk
        except Exception as exc:
            logger.exception("VisualConceptAgent error")
            yield _sse_chunk("error", text=f"Agent error: {exc}")
            yield _sse_chunk("done")

    # ------------------------------------------------------------------
    # COLLECTING handler
    # ------------------------------------------------------------------

    async def _handle_collecting(
        self,
        user_input: str,
        ctx: VisualConceptContext,
        db: Optional[Any],
    ) -> AsyncGenerator[str, None]:
        """Parse user input → merge into requirement → ask more or run pipeline."""
        ctx.requirement.raw_input = (
            f"{ctx.requirement.raw_input}\n{user_input}".strip()
            if ctx.requirement.raw_input
            else user_input
        )

        # Ask LLM to extract structured fields from user input
        parse_result = await self._llm.generate_json(
            prompt=(
                "从以下用户输入中提取视觉概念图需求信息，返回 JSON：\n"
                "字段：scene（使用场景）, screen_type（屏幕类型）, "
                "visual_style（视觉风格）, brand_or_theme（品牌/主题）, "
                "color_tone（色调）, target_audience（目标受众）, "
                "key_elements（关键元素列表）, constraints（约束）, "
                "missing_fields（仍然缺失的字段名列表）\n\n"
                f"用户输入：{user_input}\n\n"
                f"当前已收集的需求：{json.dumps(ctx.requirement.to_dict(), ensure_ascii=False)}"
            ),
            system_prompt=(
                "你是一个视觉概念图需求分析助手。"
                "从用户自然语言中提取结构化需求字段。"
                "只返回 JSON，不要额外解释。"
            ),
        )

        # Merge parsed fields into requirement
        for key in (
            "scene", "screen_type", "visual_style", "brand_or_theme",
            "color_tone", "target_audience", "constraints",
        ):
            val = parse_result.get(key)
            if val is not None:
                ctx.requirement.merge_field(key, val)
        if parse_result.get("key_elements"):
            ctx.requirement.merge_field("key_elements", parse_result["key_elements"])

        # Check if we still need more info
        missing = ctx.requirement.get_missing_critical_fields()
        if missing and ctx.should_ask_more():
            ctx.ask_round += 1
            ctx.missing_info = missing
            # Send a structured parameter card (no LLM question needed)
            yield _sse_chunk("text_delta", text="请补充关键信息：")
            yield _sse_chunk(
                "parameter_card",
                data={
                    "missing_fields": [
                        {
                            "field": f,
                            "label": FIELD_LABELS.get(f, f),
                            "options": FIELD_OPTIONS.get(f, []),
                        }
                        for f in missing
                    ],
                },
            )
            yield _sse_chunk("done")
            return

        # Enough info — create the first version node and run the full pipeline
        ctx.create_initial_node()
        async for chunk in self._run_full_pipeline(ctx, db):
            yield chunk

    # ------------------------------------------------------------------
    # REVIEWING handler
    # ------------------------------------------------------------------

    async def _handle_reviewing(
        self,
        user_input: str,
        ctx: VisualConceptContext,
        db: Optional[Any],
    ) -> AsyncGenerator[str, None]:
        """Detect user intent: satisfied / modify / restart."""
        intent_result = await self._llm.generate_json(
            prompt=(
                "判断用户对当前视觉概念图的意图，返回 JSON：\n"
                '{"intent": "satisfied" | "modify" | "restart", '
                '"modifications": {"field": "value", ...}, '
                '"reason": "解释"}\n\n'
                f"用户输入：{user_input}"
            ),
            system_prompt=(
                "你是一个意图识别助手。用户正在审核一张 AI 生成的视觉概念图。\n"
                '- 如果用户表示满意/确认/可以了，intent 为 "satisfied"\n'
                '- 如果用户要求修改某些方面，intent 为 "modify"，并在 modifications 中提取修改内容\n'
                "- 如果用户要求完全重来/换个方向，intent 为 \"restart\""
            ),
        )

        intent = intent_result.get("intent", "modify")

        if intent == "satisfied":
            ctx.state = "COMPLETED"
            node = ctx.get_current_node()
            summary = (
                f"视觉概念图已确认完成。\n"
                f"版本：{node.version_label if node else 'N/A'}\n"
                f"正向 Prompt：{node.positive_prompt[:100] if node and node.positive_prompt else 'N/A'}…\n"
            ) if node else "视觉概念图已确认完成。"
            yield _sse_chunk("text_delta", text=summary)
            yield _sse_chunk("artifact_summary", data=ctx.get_current_node().to_dict() if node else {})
            yield _sse_chunk("done")
            return

        if intent == "restart":
            ctx.state = "COLLECTING"
            ctx.requirement = VisualRequirement()
            ctx.ask_round = 0
            ctx.missing_info = []
            ctx.version_tree = None
            ctx.current_node_id = None
            yield _sse_chunk("text_delta", text="好的，让我们重新开始。请描述您想要的视觉概念图。")
            yield _sse_chunk("done")
            return

        # modify
        modifications = intent_result.get("modifications", {})
        if modifications:
            ctx.requirement.add_modification(
                round=len(ctx.requirement.modification_log) + 1,
                instruction=user_input,
                parsed_changes=modifications,
            )

        ctx.create_next_version(trigger="modify", user_instruction=user_input)
        async for chunk in self._run_full_pipeline(ctx, db):
            yield chunk

    # ------------------------------------------------------------------
    # Full generation pipeline
    # ------------------------------------------------------------------

    async def _run_full_pipeline(
        self,
        ctx: VisualConceptContext,
        db: Optional[Any],
    ) -> AsyncGenerator[str, None]:
        """Execute PLANNING → PROMPTING → GENERATING → REVIEWING sequence."""
        node = ctx.get_current_node()
        if node is None:
            yield _sse_chunk("error", text="No version node available")
            yield _sse_chunk("done")
            return

        # --- PLANNING ---
        ctx.state = "PLANNING"
        yield _sse_chunk(
            "skill_progress",
            data={"skill_id": "visual_strategy", "status": "running", "message": "正在生成视觉策略…"},
        )
        strategy = await self._generate_visual_strategy(ctx, db)
        node.visual_strategy = strategy
        yield _sse_chunk("visual_strategy", data=strategy)
        yield _sse_chunk(
            "skill_progress",
            data={"skill_id": "visual_strategy", "status": "completed"},
        )

        # --- PROMPTING ---
        ctx.state = "PROMPTING"
        yield _sse_chunk(
            "skill_progress",
            data={"skill_id": "prompt_generation", "status": "running", "message": "正在生成 Prompt…"},
        )
        prompts = await self._generate_prompts(ctx, strategy)
        node.positive_prompt = prompts.get("positive_prompt", "")
        node.negative_prompt = prompts.get("negative_prompt", "")
        yield _sse_chunk("text_delta", text=f"正向 Prompt：{node.positive_prompt}\n\n负向 Prompt：{node.negative_prompt}")
        yield _sse_chunk(
            "skill_progress",
            data={"skill_id": "prompt_generation", "status": "completed"},
        )

        # --- GENERATING ---
        ctx.state = "GENERATING"
        yield _sse_chunk(
            "skill_progress",
            data={"skill_id": "image_generation", "status": "running", "message": "正在生成概念图…"},
        )
        image_url = await self._generate_image(node.positive_prompt, node.negative_prompt)
        node.image_url = image_url
        node.image_metadata = {
            "width": 1024,
            "height": 576,
        }

        # Quality check
        quality = await self._quality_check(ctx, node)
        node.quality_check = quality
        node.completed_at = datetime.now(timezone.utc).isoformat()

        yield _sse_chunk("visual_result", data={"image_url": image_url})
        yield _sse_chunk("quality_check", data=quality)
        yield _sse_chunk(
            "skill_progress",
            data={"skill_id": "image_generation", "status": "completed"},
        )

        # --- REVIEWING ---
        ctx.state = "REVIEWING"
        yield _sse_chunk(
            "action_buttons",
            data={
                "buttons": [
                    {"label": "满意，确认", "action": "satisfied"},
                    {"label": "需要修改", "action": "modify"},
                    {"label": "重新开始", "action": "restart"},
                ],
            },
        )
        yield _sse_chunk("done")

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------

    async def _generate_ask_question(
        self, ctx: VisualConceptContext, missing: List[str]
    ) -> str:
        """Generate a friendly follow-up question for the missing fields."""
        field_labels = {
            "scene": "使用场景",
            "visual_style": "视觉风格",
            "screen_type": "屏幕类型",
            "brand_or_theme": "品牌或主题",
            "color_tone": "色调",
            "target_audience": "目标受众",
        }
        labels = [field_labels.get(f, f) for f in missing]
        ask_text = await self._llm.generate(
            prompt=(
                f"当前已收集需求：{json.dumps(ctx.requirement.to_dict(), ensure_ascii=False)}\n"
                f"还缺少以下关键信息：{', '.join(labels)}\n\n"
                "请用友好的语气，简短地询问用户补充这些信息。一句话即可。"
            ),
            system_prompt="你是一个友好的视觉设计需求收集助手。",
        )
        return ask_text

    @staticmethod
    def _generate_quick_replies(missing: List[str]) -> List[Dict[str, str]]:
        """Return quick-reply button dicts based on missing fields."""
        button_map: Dict[str, List[Dict[str, str]]] = {
            "scene": [
                {"label": "品牌发布会", "value": "品牌发布会"},
                {"label": "商场展示", "value": "商场展示"},
                {"label": "户外广告", "value": "户外广告"},
            ],
            "visual_style": [
                {"label": "科技感", "value": "科技感"},
                {"label": "国潮风", "value": "国潮风"},
                {"label": "简约商务", "value": "简约商务"},
            ],
        }
        buttons: List[Dict[str, str]] = []
        for field_name in missing:
            if field_name in button_map:
                buttons.extend(button_map[field_name])
        return buttons

    async def _generate_visual_strategy(
        self, ctx: VisualConceptContext, db: Optional[Any]
    ) -> Dict[str, Any]:
        """Call LLM to generate a visual strategy from the requirement."""
        strategy = await self._llm.generate_json(
            prompt=(
                "根据以下需求生成视觉策略，返回 JSON：\n"
                "字段：style（视觉风格方向）, color_tone（色调方案）, "
                "composition（构图建议）, key_elements（关键视觉元素列表）, "
                "focus（视觉焦点）, mood（氛围）, notes（注意事项）, "
                "citations（参考案例描述列表）\n\n"
                f"需求：{json.dumps(ctx.requirement.to_dict(), ensure_ascii=False)}"
            ),
            system_prompt=(
                "你是一位 3D 展示幕墙视觉创意专家。"
                "根据客户需求生成专业的视觉策略方案。"
                "只返回 JSON。"
            ),
        )
        return strategy

    async def _generate_prompts(
        self, ctx: VisualConceptContext, strategy: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call LLM to generate positive/negative prompts from the strategy."""
        result = await self._llm.generate_json(
            prompt=(
                "根据以下视觉策略生成文生图 Prompt，返回 JSON：\n"
                '{"positive_prompt": "...", "negative_prompt": "..."}\n\n'
                f"视觉策略：{json.dumps(strategy, ensure_ascii=False)}\n\n"
                f"原始需求：{json.dumps(ctx.requirement.to_dict(), ensure_ascii=False)}"
            ),
            system_prompt=(
                "你是一位专业的 AI 绘图 Prompt 工程师，专注于 3D 展示幕墙和裸眼 3D 概念图。\n"
                "positive_prompt 应该是英文，详细描述画面内容、构图、光影、色调。\n"
                "negative_prompt 应该列出需要排除的元素和低质量标记。\n"
                "只返回 JSON。"
            ),
        )
        return result

    async def _generate_image(
        self, positive_prompt: str, negative_prompt: str
    ) -> str:
        """Call image generation service and return the image URL."""
        image_url = await self._image.generate_image_url(
            prompt=positive_prompt,
            width=1024,
            height=576,
        )
        return image_url

    async def _quality_check(
        self, ctx: VisualConceptContext, node: VersionNode
    ) -> Dict[str, Any]:
        """Call LLM to perform a quality check on the generated output."""
        result = await self._llm.generate_json(
            prompt=(
                "对以下生成结果进行质量检查，返回 JSON：\n"
                '{"items": [{"item": "检查项", "status": "✅或⚠️", "note": "说明"}]}\n\n'
                f"需求：{json.dumps(ctx.requirement.to_dict(), ensure_ascii=False)}\n"
                f"视觉策略：{json.dumps(node.visual_strategy or {}, ensure_ascii=False)}\n"
                f"正向 Prompt：{node.positive_prompt}"
            ),
            system_prompt="你是一位视觉质量审核专家。检查生成结果是否满足需求。只返回 JSON。",
        )
        return result

    # ------------------------------------------------------------------
    # Project context auto-loader
    # ------------------------------------------------------------------

    @staticmethod
    async def _load_project_context(
        project_id: str,
        db: Any,
    ) -> Optional[Dict[str, Any]]:
        """Load company profile + visual style from project to auto-fill requirement.

        Returns a dict suitable for emitting as context_card + merging into requirement,
        or None if no useful context could be loaded.
        """
        from sqlalchemy import select
        from app.models.project import Project
        from app.models.company_profile import CompanyProfile
        from app.models.visual import VisualStyle

        result: Dict[str, Any] = {
            "company_name": None,
            "industry": None,
            "visual_style": None,
            "colors": None,
            "auto_filled": {},
        }

        try:
            # Load project with company
            stmt = select(Project).where(Project.id == uuid.UUID(project_id))
            proj_res = await db.execute(stmt)
            project = proj_res.scalar_one_or_none()
            if not project:
                return None

            company = project.company
            if company:
                result["company_name"] = company.name
                result["industry"] = company.industry
                result["auto_filled"]["brand_or_theme"] = company.name
                if company.industry:
                    result["auto_filled"]["target_audience"] = f"{company.industry}行业目标客户"

            # Load company profile
            if company:
                cp_stmt = select(CompanyProfile).where(
                    CompanyProfile.company_id == company.id
                )
                cp_res = await db.execute(cp_stmt)
                profile = cp_res.scalar_one_or_none()
                if profile:
                    # Derive scene from project background if available
                    pb = profile.project_background
                    if isinstance(pb, dict) and pb.get("project_positioning"):
                        pos = pb["project_positioning"]
                        if isinstance(pos, dict) and pos.get("content"):
                            result["auto_filled"]["scene"] = pos["content"][:30]

            # Load first visual style as default
            vs_stmt = select(VisualStyle).where(VisualStyle.is_active.is_(True)).limit(1)
            vs_res = await db.execute(vs_stmt)
            style = vs_res.scalar_one_or_none()
            if style:
                result["visual_style"] = style.name
                result["auto_filled"]["visual_style"] = style.name
                colors = {}
                if style.primary_color:
                    colors["primary"] = style.primary_color
                if style.secondary_color:
                    colors["secondary"] = style.secondary_color
                if style.accent_color:
                    colors["accent"] = style.accent_color
                if colors:
                    result["colors"] = colors
                    # Derive color_tone from palette
                    result["auto_filled"]["color_tone"] = (
                        f"以{style.primary_color}为主色调"
                    )

            # Default screen type
            result["auto_filled"]["screen_type"] = "裸眼3D"

            # Only return if we got something useful
            if not result["auto_filled"]:
                return None

            return result

        except Exception:
            logger.warning("Failed to load project context for visual concept", exc_info=True)
            return None
