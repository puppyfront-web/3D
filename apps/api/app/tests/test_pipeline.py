"""Integration tests for SOP pipeline flow."""

import pytest
from app.services.pipeline_state import PipelineState, STAGE_ORDER, PAUSE_STAGES
from app.services.intent_service import IntentDetector
from app.services.execution_plan import ExecutionPlan, PlanStep


class TestBuildStepInput:
    """_build_step_input must thread project_id from plan.context into the
    proposal_generation / visual_prompt inputs so they run in DB mode (read
    screen_info, write sections_meta, update project.status)."""

    def test_proposal_generation_gets_project_id(self):
        from app.services.plan_executor import _build_step_input

        plan = ExecutionPlan(domain="curtain_wall", context={"project_id": "proj-123", "user_message": "hi"})
        step = PlanStep(skill_id="proposal_generation")
        data = _build_step_input(step, plan)
        assert data["project_id"] == "proj-123"
        assert data["requirement_text"] == "hi"

    def test_visual_prompt_gets_project_id(self):
        from app.services.plan_executor import _build_step_input

        plan = ExecutionPlan(domain="curtain_wall", context={"project_id": "proj-456"})
        step = PlanStep(skill_id="visual_prompt")
        data = _build_step_input(step, plan)
        assert data["project_id"] == "proj-456"

    def test_no_project_id_when_absent(self):
        from app.services.plan_executor import _build_step_input

        plan = ExecutionPlan(domain="curtain_wall", context={"user_message": "hi"})
        step = PlanStep(skill_id="proposal_generation")
        data = _build_step_input(step, plan)
        assert "project_id" not in data


class TestPipelineState:
    def test_initial_state(self):
        state = PipelineState()
        assert state.status == "running"
        assert state.current_stage == "company_analysis"
        assert state.completed_stages == []

    def test_advance(self):
        state = PipelineState()
        nxt = state.advance()
        assert nxt == "proposal_generation"
        assert "company_analysis" in state.completed_stages
        assert state.status == "running"

    def test_advance_to_completion(self):
        state = PipelineState()
        state.advance()  # → proposal
        state.advance()  # → visual
        state.advance()  # → export
        nxt = state.advance()  # → None (completed)
        assert nxt is None
        assert state.status == "completed"

    def test_pause(self):
        state = PipelineState()
        state.pause()
        assert state.status == "paused"

    def test_reset(self):
        state = PipelineState()
        state.advance()
        state.advance()
        state.reset()
        assert state.current_stage == "company_analysis"
        assert state.completed_stages == []
        assert state.status == "running"

    def test_serialization_roundtrip(self):
        state = PipelineState()
        state.project_context = {"company_name": "华为"}
        state.stage_outputs["company_analysis"] = {"summary": "test"}
        d = state.to_dict()
        restored = PipelineState.from_dict(d)
        assert restored.project_context["company_name"] == "华为"
        assert restored.stage_outputs["company_analysis"]["summary"] == "test"
        assert restored.status == state.status
        assert restored.current_stage == state.current_stage

    def test_pause_stages(self):
        assert "company_analysis" in PAUSE_STAGES
        assert "proposal_generation" in PAUSE_STAGES
        assert "visual_generation" in PAUSE_STAGES
        assert "export" not in PAUSE_STAGES


class TestIntentDetection:
    """Intent detection is now ReAct-first. These tests verify:
    - Fast-path keywords (unambiguous only)
    - Fallback behavior when LLM is unavailable
    - classify_pipeline_action (pure keyword-based, no LLM)
    """

    @pytest.fixture
    def detector(self):
        return IntentDetector()

    def test_fast_path_export(self, detector):
        """Unambiguous keyword: '导出文档' → run_skill: export."""
        import asyncio
        result = asyncio.run(
            detector.detect("导出文档", [], db=None)
        )
        assert result.intent == "run_skill"
        assert result.skill_id == "export"
        assert result.confidence >= 0.8

    def test_fast_path_case_retrieval(self, detector):
        """Unambiguous keyword: '案例检索' → run_skill: case_retrieval."""
        import asyncio
        result = asyncio.run(
            detector.detect("案例检索", [], db=None)
        )
        assert result.intent == "run_skill"
        assert result.skill_id == "case_retrieval"

    def test_fast_path_short_confirm(self, detector):
        """Short confirm message → action: confirm."""
        import asyncio
        result = asyncio.run(
            detector.detect("确认", [], db=None)
        )
        assert result.intent == "action"

    def test_react_classifies_pipeline(self, detector):
        """ReAct (via MockLLM) should classify '设计一套方案' as sop_pipeline."""
        import asyncio
        result = asyncio.run(
            detector.detect("给华为设计一套3D幕墙方案", [], db=None)
        )
        # With MockLLM, ReAct correctly identifies pipeline intent
        assert result.intent == "sop_pipeline"

    def test_react_classifies_skill(self, detector):
        """ReAct (via MockLLM) should classify single-skill requests correctly."""
        import asyncio
        result = asyncio.run(
            detector.detect("帮我进行企业解析", [], db=None)
        )
        assert result.intent == "run_skill"
        assert result.skill_id == "company_analysis"

    def test_not_pipeline_for_fast_path_skills(self, detector):
        """Fast-path export should not be mis-routed as pipeline."""
        import asyncio
        result = asyncio.run(
            detector.detect("导出pdf", [], db=None)
        )
        assert result.intent != "sop_pipeline"
        assert result.skill_id == "export"


class TestPipelineActionClassification:
    def test_confirm_action(self):
        assert IntentDetector.classify_pipeline_action("确认") == "confirm"
        assert IntentDetector.classify_pipeline_action("继续") == "confirm"
        assert IntentDetector.classify_pipeline_action("没问题") == "confirm"

    def test_restart_action(self):
        assert IntentDetector.classify_pipeline_action("重新开始") == "restart"
        assert IntentDetector.classify_pipeline_action("从头来") == "restart"

    def test_modify_action(self):
        assert IntentDetector.classify_pipeline_action("第三章改一下") == "modify"
        assert IntentDetector.classify_pipeline_action("色调再冷一点") == "modify"
        assert IntentDetector.classify_pipeline_action("我觉得视觉方案可以更科技感一些") == "modify"
