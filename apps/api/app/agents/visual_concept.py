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
        if data.get("version_tree"):
            ctx.version_tree = VersionTree.from_dict(data["version_tree"])
        return ctx
