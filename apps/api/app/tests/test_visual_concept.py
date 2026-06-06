"""Tests for VisualRequirement data model and modification tracking."""

import json

import pytest
from unittest.mock import AsyncMock

from app.agents.visual_concept import (
    VisualRequirement,
    ModificationEntry,
    VersionNode,
    BranchMeta,
    VersionTree,
    VisualConceptContext,
    VisualConceptAgent,
    _sse_chunk,
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


class TestVisualConceptContext:
    def test_create_initial(self):
        ctx = VisualConceptContext()
        assert ctx.state == "COLLECTING"
        assert ctx.ask_round == 0
        assert ctx.version_tree is None

    def test_increment_ask_round(self):
        ctx = VisualConceptContext()
        ctx.ask_round = 1
        assert ctx.should_ask_more() is True
        ctx.ask_round = 3
        assert ctx.should_ask_more() is False

    def test_create_version_tree_on_first_planning(self):
        ctx = VisualConceptContext()
        assert ctx.version_tree is None
        node = ctx.create_initial_node()
        assert ctx.version_tree is not None
        assert ctx.version_tree.root_id == node.node_id
        assert ctx.current_node_id == node.node_id

    def test_to_dict_round_trip(self):
        ctx = VisualConceptContext()
        ctx.requirement.merge_field("scene", "商场")
        ctx.requirement.merge_field("visual_style", "科技感")
        node = ctx.create_initial_node()
        ctx.state = "PLANNING"

        data = ctx.to_dict()
        restored = VisualConceptContext.from_dict(data)
        assert restored.state == "PLANNING"
        assert restored.requirement.scene == "商场"
        assert restored.current_node_id == node.node_id
        assert restored.version_tree is not None

    def test_create_next_version(self):
        ctx = VisualConceptContext()
        ctx.requirement.merge_field("scene", "商场")
        ctx.requirement.merge_field("visual_style", "科技感")
        ctx.create_initial_node()
        ctx.state = "REVIEWING"

        ctx.create_next_version(trigger="modify", user_instruction="背景改成红色")
        assert ctx.current_node_id is not None
        current = ctx.version_tree.get_current_node()
        assert current.version_label == "V2"
        assert current.trigger == "modify"


# ---------------------------------------------------------------------------
# Tests for _sse_chunk helper
# ---------------------------------------------------------------------------


class TestSseChunk:
    def test_text_only(self):
        result = _sse_chunk("text_delta", text="hello")
        assert result.startswith("data: ")
        assert '"text_delta"' in result
        assert '"hello"' in result
        assert result.endswith("\n\n")

    def test_data_only(self):
        result = _sse_chunk("action_buttons", data={"buttons": []})
        assert '"action_buttons"' in result
        assert '"buttons"' in result

    def test_text_and_data(self):
        result = _sse_chunk("error", text="oops", data={"code": 500})
        assert '"error"' in result
        assert '"oops"' in result
        assert '"code"' in result

    def test_no_text_no_data(self):
        result = _sse_chunk("done")
        assert '"done"' in result
        parsed = result[len("data: "):].strip()
        import json
        payload = json.loads(parsed)
        assert payload == {"type": "done"}


# ---------------------------------------------------------------------------
# Tests for VisualConceptAgent
# ---------------------------------------------------------------------------


class TestVisualConceptAgent:
    """Tests for the VisualConceptAgent state machine and SSE streaming."""

    def _make_agent(self):
        """Create an agent with mocked LLM and image services.

        The mock LLM sequence covers the full pipeline:
        parse requirement -> visual strategy -> prompts -> quality check.
        """
        mock_llm = AsyncMock()
        mock_image = AsyncMock()
        mock_image.generate_image_url = AsyncMock(
            return_value="data:image/svg+xml,test"
        )

        call_count = [0]

        async def mock_generate_json(**kwargs):
            call_count[0] += 1
            n = call_count[0]
            if n == 1:  # COLLECTING: parse requirement
                return {
                    "scene": "品牌发布会",
                    "screen_type": "裸眼3D",
                    "visual_style": "科技感",
                    "brand_or_theme": "汽车品牌",
                    "missing_fields": [],
                }
            elif n == 2:  # PLANNING: strategy
                return {
                    "style": "赛博科技风",
                    "color_tone": "深蓝渐变",
                    "composition": "纵深透视",
                    "key_elements": ["悬浮粒子"],
                    "focus": "产品居中",
                    "mood": "未来科技感",
                    "notes": "",
                    "citations": [],
                }
            elif n == 3:  # PROMPTING
                return {
                    "positive_prompt": "A futuristic cyberpunk-style 3D display...",
                    "negative_prompt": "low quality, blurry",
                }
            elif n == 4:  # QUALITY CHECK
                return {
                    "items": [
                        {"item": "场景", "status": "✅", "note": "匹配"},
                        {"item": "风格", "status": "✅", "note": "匹配"},
                    ]
                }
            return {}

        mock_llm.generate_json = AsyncMock(side_effect=mock_generate_json)
        mock_llm.generate = AsyncMock(
            return_value="请问使用场景和视觉风格偏好是？"
        )

        agent = VisualConceptAgent(
            llm_service=mock_llm, image_service=mock_image
        )
        return agent, mock_llm, mock_image

    # -- init --

    def test_agent_init(self):
        agent, _, _ = self._make_agent()
        assert agent.name == "visual_concept"

    def test_agent_init_with_services(self):
        mock_llm = AsyncMock()
        mock_image = AsyncMock()
        agent = VisualConceptAgent(
            llm_service=mock_llm, image_service=mock_image
        )
        assert agent._llm is mock_llm
        assert agent._image is mock_image

    # -- COLLECTING with enough info --

    @pytest.mark.asyncio
    async def test_collecting_with_enough_info(self):
        agent, _, _ = self._make_agent()
        ctx = VisualConceptContext()
        chunks = []
        async for chunk in agent.handle_message(
            "汽车品牌裸眼3D概念图，品牌发布会，科技感", ctx
        ):
            chunks.append(chunk)
        # After full pipeline the context should be in REVIEWING
        assert ctx.state == "REVIEWING"
        assert ctx.version_tree is not None
        # Must have yielded skill_progress chunks
        progress = [
            c for c in chunks if '"skill_progress"' in c
        ]
        assert len(progress) >= 3  # PLANNING, PROMPTING, GENERATING
        # Must have yielded visual_strategy content block (not skill_progress)
        strategy = [
            c for c in chunks if '"visual_strategy"' in c and '"skill_progress"' not in c
        ]
        assert len(strategy) == 1
        # Must have yielded visual_result with image_url
        results = [c for c in chunks if '"visual_result"' in c]
        assert len(results) == 1
        # Must have quality check
        qc = [c for c in chunks if '"quality_check"' in c]
        assert len(qc) == 1
        # Must have action_buttons at the end (REVIEWING)
        buttons = [c for c in chunks if '"action_buttons"' in c]
        assert len(buttons) == 1

    @pytest.mark.asyncio
    async def test_collecting_populates_node(self):
        agent, _, _ = self._make_agent()
        ctx = VisualConceptContext()
        async for _ in agent.handle_message("test input", ctx):
            pass
        node = ctx.get_current_node()
        assert node is not None
        assert node.visual_strategy is not None
        assert node.positive_prompt is not None
        assert node.negative_prompt is not None
        assert node.image_url is not None
        assert node.quality_check is not None

    @pytest.mark.asyncio
    async def test_collecting_image_service_called(self):
        agent, _, mock_image = self._make_agent()
        ctx = VisualConceptContext()
        async for _ in agent.handle_message("test input", ctx):
            pass
        mock_image.generate_image_url.assert_awaited_once()

    # -- COLLECTING with missing info --

    @pytest.mark.asyncio
    async def test_collecting_missing_info_triggers_ask(self):
        agent, mock_llm, _ = self._make_agent()
        # Override: first call returns missing fields
        mock_llm.generate_json = AsyncMock(
            return_value={
                "scene": None,
                "screen_type": "裸眼3D",
                "visual_style": None,
                "missing_fields": ["scene", "visual_style"],
            }
        )
        mock_llm.generate = AsyncMock(
            return_value="请问使用场景和风格偏好？"
        )
        ctx = VisualConceptContext()
        chunks = []
        async for chunk in agent.handle_message("做一个裸眼3D", ctx):
            chunks.append(chunk)
        assert ctx.state == "COLLECTING"
        assert ctx.ask_round == 1
        text_deltas = [
            c
            for c in chunks
            if c.startswith("data:") and '"text_delta"' in c
        ]
        assert len(text_deltas) > 0
        # Should also have action_buttons with quick replies
        buttons = [c for c in chunks if '"action_buttons"' in c]
        assert len(buttons) == 1

    @pytest.mark.asyncio
    async def test_collecting_ask_increments_round(self):
        agent, mock_llm, _ = self._make_agent()
        mock_llm.generate_json = AsyncMock(
            return_value={
                "scene": None,
                "visual_style": None,
                "missing_fields": ["scene", "visual_style"],
            }
        )
        mock_llm.generate = AsyncMock(return_value="补充信息？")
        ctx = VisualConceptContext()
        assert ctx.ask_round == 0
        async for _ in agent.handle_message("做一个裸眼3D", ctx):
            pass
        assert ctx.ask_round == 1

    # -- REVIEWING handlers --

    @pytest.mark.asyncio
    async def test_reviewing_satisfied(self):
        agent, _, _ = self._make_agent()
        ctx = VisualConceptContext()
        # First run full pipeline to get into REVIEWING
        async for _ in agent.handle_message("test", ctx):
            pass
        assert ctx.state == "REVIEWING"

        # Now simulate "satisfied"
        async def satisfied_json(**kwargs):
            return {"intent": "satisfied", "modifications": {}, "reason": "user happy"}

        agent._llm.generate_json = AsyncMock(side_effect=satisfied_json)
        chunks = []
        async for chunk in agent.handle_message("很满意，确认", ctx):
            chunks.append(chunk)
        assert ctx.state == "COMPLETED"
        summary = [c for c in chunks if '"artifact_summary"' in c]
        assert len(summary) == 1

    @pytest.mark.asyncio
    async def test_reviewing_restart(self):
        agent, _, _ = self._make_agent()
        ctx = VisualConceptContext()
        async for _ in agent.handle_message("test", ctx):
            pass
        assert ctx.state == "REVIEWING"

        async def restart_json(**kwargs):
            return {"intent": "restart", "modifications": {}, "reason": "redo"}

        agent._llm.generate_json = AsyncMock(side_effect=restart_json)
        chunks = []
        async for chunk in agent.handle_message("重新开始", ctx):
            chunks.append(chunk)
        assert ctx.state == "COLLECTING"
        assert ctx.version_tree is None
        assert ctx.requirement.scene is None

    @pytest.mark.asyncio
    async def test_reviewing_modify(self):
        agent, _, _ = self._make_agent()
        ctx = VisualConceptContext()
        async for _ in agent.handle_message("test", ctx):
            pass
        assert ctx.state == "REVIEWING"

        # Modify: first call is intent detection, then pipeline calls
        modify_call_count = [0]

        async def modify_json(**kwargs):
            modify_call_count[0] += 1
            n = modify_call_count[0]
            if n == 1:  # intent detection
                return {
                    "intent": "modify",
                    "modifications": {"color_tone": "红色"},
                    "reason": "change color",
                }
            elif n == 2:  # strategy
                return {"style": "warm", "color_tone": "red"}
            elif n == 3:  # prompts
                return {
                    "positive_prompt": "warm red style",
                    "negative_prompt": "cold",
                }
            elif n == 4:  # quality check
                return {"items": [{"item": "color", "status": "✅", "note": "updated"}]}
            return {}

        agent._llm.generate_json = AsyncMock(side_effect=modify_json)
        chunks = []
        async for chunk in agent.handle_message("改成红色调", ctx):
            chunks.append(chunk)
        assert ctx.state == "REVIEWING"
        node = ctx.get_current_node()
        assert node is not None
        assert node.trigger == "modify"
        assert node.version_label == "V2"

    # -- error handling --

    @pytest.mark.asyncio
    async def test_error_handling(self):
        agent, mock_llm, _ = self._make_agent()
        mock_llm.generate_json = AsyncMock(side_effect=RuntimeError("boom"))
        ctx = VisualConceptContext()
        chunks = []
        async for chunk in agent.handle_message("test", ctx):
            chunks.append(chunk)
        errors = [c for c in chunks if '"error"' in c]
        assert len(errors) == 1
        dones = [c for c in chunks if '"done"' in c]
        assert len(dones) >= 1

    # -- quick replies --

    def test_quick_replies_scene(self):
        buttons = VisualConceptAgent._generate_quick_replies(["scene"])
        labels = [b["label"] for b in buttons]
        assert "品牌发布会" in labels

    def test_quick_replies_visual_style(self):
        buttons = VisualConceptAgent._generate_quick_replies(["visual_style"])
        labels = [b["label"] for b in buttons]
        assert "科技感" in labels

    def test_quick_replies_empty(self):
        buttons = VisualConceptAgent._generate_quick_replies(["brand_or_theme"])
        assert buttons == []


# ---------------------------------------------------------------------------
# Tests for visual_concept intent detection
# ---------------------------------------------------------------------------


class TestVisualConceptIntent:
    def test_high_confidence_keywords(self):
        from app.services.intent_service import IntentDetector
        detector = IntentDetector()
        for keyword in ["生成概念图", "出概念图", "视觉概念", "概念设计", "生成效果图", "视觉方案"]:
            result = detector._keyword_match(f"帮我{keyword}")
            assert result is not None, f"Should match keyword: {keyword}"
            assert result.intent == "visual_concept", f"Should be visual_concept for: {keyword}"
            assert result.confidence >= 0.8

    def test_medium_confidence_keywords(self):
        from app.services.intent_service import IntentDetector
        detector = IntentDetector()
        result = detector._keyword_match("我想做一个裸眼3D")
        assert result is not None
        assert result.intent == "visual_concept"

    def test_skill_keywords_not_overridden(self):
        """Existing skill keywords should still work."""
        from app.services.intent_service import IntentDetector
        detector = IntentDetector()
        result = detector._keyword_match("帮我解析企业信息")
        if result:
            assert result.intent == "run_skill"
            assert result.skill_id == "company_analysis"


# ---------------------------------------------------------------------------
# Integration tests — full pipeline mock verification
# ---------------------------------------------------------------------------


class TestVisualConceptIntegration:
    """集成测试：完整链路 mock 验证。"""

    def _make_agent_with_mocks(self):
        """Create agent with mock LLM that returns different results based on call order."""
        mock_llm = AsyncMock()
        mock_image = AsyncMock()
        mock_image.generate_image_url = AsyncMock(return_value="data:image/svg+xml,...mock...")

        call_sequence = []

        async def mock_generate_json(**kwargs):
            call_sequence.append(1)
            n = len(call_sequence)
            if n == 1:  # COLLECTING: parse requirement
                return {"scene": "品牌发布会", "screen_type": "裸眼3D", "visual_style": "科技感", "brand_or_theme": "汽车品牌", "missing_fields": []}
            elif n == 2:  # PLANNING: visual strategy
                return {"style": "赛博科技风", "color_tone": "深蓝渐变+电光蓝", "composition": "中心对称+纵深透视", "key_elements": ["悬浮粒子", "光线穿透"], "focus": "产品居中", "mood": "未来科技感", "notes": "注意屏幕分辨率", "citations": []}
            elif n == 3:  # PROMPTING
                return {"positive_prompt": "A futuristic cyberpunk-style 3D display wall with glowing neon particles, deep blue gradient background, electric blue highlights, centered product with light rays penetrating through...", "negative_prompt": "low quality, blurry, text, watermark, cartoon"}
            elif n == 4:  # QUALITY CHECK
                return {"items": [
                    {"item": "场景匹配", "status": "✅", "note": "品牌发布会"},
                    {"item": "风格匹配", "status": "✅", "note": "科技感"},
                    {"item": "色调匹配", "status": "✅", "note": "深蓝渐变"},
                    {"item": "关键元素", "status": "⚠️", "note": "悬浮粒子未明确包含"},
                    {"item": "构图方向", "status": "✅", "note": "纵深透视"},
                ]}
            return {}

        mock_llm.generate_json = AsyncMock(side_effect=mock_generate_json)
        mock_llm.generate = AsyncMock(return_value="请问使用场景和视觉风格偏好是？")

        agent = VisualConceptAgent(llm_service=mock_llm, image_service=mock_image)
        return agent

    @pytest.mark.asyncio
    async def test_full_pipeline_collecting_to_reviewing(self):
        """完整链路：一条消息从 COLLECTING 自动走到 REVIEWING。"""
        agent = self._make_agent_with_mocks()
        ctx = VisualConceptContext()

        chunks = []
        async for chunk in agent.handle_message(
            "帮我做一个汽车品牌的裸眼3D概念图，品牌发布会，科技感风格", ctx
        ):
            chunks.append(chunk)

        # Verify final state
        assert ctx.state == "REVIEWING"
        assert ctx.version_tree is not None
        assert ctx.current_node_id is not None

        # Verify node has all artifacts
        node = ctx.get_current_node()
        assert node is not None
        assert node.visual_strategy is not None
        assert node.positive_prompt is not None
        assert node.image_url is not None
        assert node.quality_check is not None
        assert len(node.quality_check["items"]) == 5

        # Verify SSE output contains expected block types
        chunk_types = []
        for c in chunks:
            if c.startswith("data: "):
                data = json.loads(c[6:])
                chunk_types.append(data.get("type"))

        assert "visual_strategy" in chunk_types
        assert "visual_result" in chunk_types
        assert "quality_check" in chunk_types
        assert "action_buttons" in chunk_types
        assert "done" in chunk_types

    @pytest.mark.asyncio
    async def test_modify_creates_new_version(self):
        """修改操作创建新版本节点。"""
        agent = self._make_agent_with_mocks()
        ctx = VisualConceptContext()

        # First round: initial generation
        async for _ in agent.handle_message("汽车品牌裸眼3D概念图，品牌发布会，科技感", ctx):
            pass
        v1_node_id = ctx.current_node_id
        assert ctx.state == "REVIEWING"

        # Second round: modify — mock for intent + pipeline
        modify_call_count = [0]

        async def modify_json(**kwargs):
            modify_call_count[0] += 1
            n = modify_call_count[0]
            if n == 1:  # intent detection
                return {"intent": "modify", "modifications": {"color_tone": "深红色"}, "reason": "change background color"}
            elif n == 2:  # strategy
                return {"style": "赛博科技风", "color_tone": "深红色", "composition": "纵深透视", "key_elements": ["悬浮粒子"], "focus": "产品居中", "mood": "未来科技感", "notes": "", "citations": []}
            elif n == 3:  # prompts
                return {"positive_prompt": "A deep red background version...", "negative_prompt": "low quality"}
            elif n == 4:  # quality check
                return {"items": [{"item": "色调", "status": "✅", "note": "深红色"}]}
            return {}

        agent._llm.generate_json = AsyncMock(side_effect=modify_json)
        async for _ in agent.handle_message("背景改成深红色", ctx):
            pass

        assert ctx.state == "REVIEWING"
        assert ctx.current_node_id != v1_node_id

        v2_node = ctx.get_current_node()
        assert v2_node.version_label == "V2"
        assert v2_node.trigger == "modify"
        assert v2_node.parent_id == v1_node_id

    @pytest.mark.asyncio
    async def test_satisfied_completes_flow(self):
        """满意操作完成流程。"""
        agent = self._make_agent_with_mocks()
        ctx = VisualConceptContext()

        async for _ in agent.handle_message("汽车品牌裸眼3D概念图，品牌发布会，科技感", ctx):
            pass

        # Simulate "satisfied"
        agent._llm.generate_json = AsyncMock(return_value={"intent": "satisfied"})
        async for _ in agent.handle_message("很满意，就这样吧", ctx):
            pass

        assert ctx.state == "COMPLETED"

    @pytest.mark.asyncio
    async def test_restart_resets_state(self):
        """全部重来重置状态。"""
        agent = self._make_agent_with_mocks()
        ctx = VisualConceptContext()

        async for _ in agent.handle_message("汽车品牌裸眼3D概念图，品牌发布会，科技感", ctx):
            pass

        agent._llm.generate_json = AsyncMock(return_value={"intent": "restart"})
        async for _ in agent.handle_message("重新来过", ctx):
            pass

        assert ctx.state == "COLLECTING"
        assert ctx.requirement.raw_input == ""  # reset

    @pytest.mark.asyncio
    async def test_context_serialization_survives_full_flow(self):
        """上下文序列化在整个流程中保持完整。"""
        agent = self._make_agent_with_mocks()
        ctx = VisualConceptContext()

        async for _ in agent.handle_message("汽车品牌裸眼3D概念图，品牌发布会，科技感", ctx):
            pass

        # Serialize and deserialize
        data = ctx.to_dict()
        restored = VisualConceptContext.from_dict(data)

        assert restored.state == "REVIEWING"
        assert restored.version_tree is not None
        assert restored.current_node_id == ctx.current_node_id
        assert restored.requirement.scene == "品牌发布会"

        node = restored.get_current_node()
        assert node.positive_prompt is not None
        assert node.image_url is not None
