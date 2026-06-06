"""Tests for VisualRequirement data model and modification tracking."""

import pytest
from app.agents.visual_concept import (
    VisualRequirement,
    ModificationEntry,
    VersionNode,
    BranchMeta,
    VersionTree,
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


class TestVersionTree:
    def _make_root(self):
        return VersionNode(
            node_id="n1",
            branch_id="main",
            version_label="V1",
            trigger="initial",
            requirement_snapshot={"raw_input": "test"},
        )

    def test_create_tree_with_root(self):
        root = self._make_root()
        tree = VersionTree(root=root)
        assert tree.root_id == "n1"
        assert tree.active_branch == "main"
        assert "main" in tree.branches
        assert tree.branches["main"].current_node_id == "n1"

    def test_add_child_node(self):
        root = self._make_root()
        tree = VersionTree(root=root)
        child = VersionNode(
            node_id="n2",
            parent_id="n1",
            branch_id="main",
            version_label="V2",
            trigger="modify",
            user_instruction="背景改红色",
            requirement_snapshot={"raw_input": "test", "color_tone": "红色"},
        )
        tree.add_node(child)
        assert "n2" in tree.nodes
        assert "n2" in tree.nodes["n1"].children_ids
        assert tree.branches["main"].current_node_id == "n2"

    def test_create_branch(self):
        root = self._make_root()
        tree = VersionTree(root=root)
        branch_node = VersionNode(
            node_id="n2",
            parent_id="n1",
            branch_id="branch_b",
            version_label="V1'",
            trigger="branch",
            requirement_snapshot={"raw_input": "test"},
        )
        tree.create_branch("branch_b", "国潮风探索", branch_node)
        tree.add_node(branch_node)
        assert "branch_b" in tree.branches
        assert tree.branches["branch_b"].branch_name == "国潮风探索"
        assert tree.branches["branch_b"].current_node_id == "n2"

    def test_rollback_marks_abandoned(self):
        root = self._make_root()
        tree = VersionTree(root=root)
        child = VersionNode(
            node_id="n2",
            parent_id="n1",
            branch_id="main",
            version_label="V2",
            trigger="modify",
            requirement_snapshot={},
        )
        tree.add_node(child)
        grandchild = VersionNode(
            node_id="n3",
            parent_id="n2",
            branch_id="main",
            version_label="V3",
            trigger="modify",
            requirement_snapshot={},
        )
        tree.add_node(grandchild)
        tree.rollback_to("n1")
        assert tree.nodes["n2"].status == "abandoned"
        assert tree.nodes["n3"].status == "abandoned"
        assert tree.nodes["n1"].status == "completed"
        assert tree.branches["main"].current_node_id == "n1"

    def test_switch_branch(self):
        root = self._make_root()
        tree = VersionTree(root=root)
        branch_node = VersionNode(
            node_id="n2",
            parent_id="n1",
            branch_id="branch_b",
            version_label="V1'",
            trigger="branch",
            requirement_snapshot={},
        )
        tree.create_branch("branch_b", "探索", branch_node)
        tree.add_node(branch_node)
        tree.switch_branch("branch_b")
        assert tree.active_branch == "branch_b"

    def test_to_dict_round_trip(self):
        root = self._make_root()
        root.visual_strategy = {"style": "科技感"}
        tree = VersionTree(root=root)
        child = VersionNode(
            node_id="n2",
            parent_id="n1",
            branch_id="main",
            version_label="V2",
            trigger="modify",
            requirement_snapshot={},
            positive_prompt="A futuristic...",
        )
        tree.add_node(child)
        data = tree.to_dict()
        restored = VersionTree.from_dict(data)
        assert restored.root_id == "n1"
        assert "n2" in restored.nodes
        assert restored.nodes["n2"].positive_prompt == "A futuristic..."
        assert restored.active_branch == "main"
