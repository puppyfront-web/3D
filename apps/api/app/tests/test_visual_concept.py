"""Tests for VisualRequirement data model and modification tracking."""

import pytest
from app.agents.visual_concept import (
    VisualRequirement,
    ModificationEntry,
)


class TestVisualRequirement:
    def test_create_empty(self):
        req = VisualRequirement(raw_input="test")
        assert req.scene is None
        assert req.key_elements == []
        assert req.modification_log == []

    def test_merge_from_answer(self):
        req = VisualRequirement(raw_input="做一个裸眼3D")
        req.merge_field("scene", "品牌发布会")
        req.merge_field("visual_style", "科技感")
        assert req.scene == "品牌发布会"
        assert req.visual_style == "科技感"

    def test_merge_does_not_overwrite_existing(self):
        req = VisualRequirement(raw_input="test", scene="商场")
        req.merge_field("scene", "品牌发布会")
        assert req.scene == "品牌发布会"  # merge 允许覆盖，因为用户明确说了

    def test_get_missing_fields(self):
        req = VisualRequirement(raw_input="裸眼3D")
        req.screen_type = "裸眼3D"
        req.brand_or_theme = "汽车品牌"
        missing = req.get_missing_critical_fields()
        assert "scene" in missing
        assert "visual_style" in missing

    def test_has_enough_info(self):
        req = VisualRequirement(
            raw_input="test",
            screen_type="裸眼3D",
            scene="品牌发布会",
            visual_style="科技感",
        )
        assert req.has_enough_info() is True

    def test_add_modification(self):
        req = VisualRequirement(raw_input="test")
        req.add_modification(
            round=1,
            instruction="背景改成红色",
            parsed_changes={"color_tone": "红色"},
        )
        assert len(req.modification_log) == 1
        assert req.modification_log[0].user_instruction == "背景改成红色"
        assert req.modification_log[0].previous_requirement is not None
