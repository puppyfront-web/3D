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
