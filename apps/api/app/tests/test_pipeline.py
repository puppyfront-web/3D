"""Integration tests for SOP pipeline flow."""

import pytest
from app.services.pipeline_state import PipelineState, STAGE_ORDER, PAUSE_STAGES
from app.services.intent_service import IntentDetector


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
    @pytest.fixture
    def detector(self):
        return IntentDetector()

    def test_pipeline_intent_high_confidence(self, detector):
        import asyncio
        result = asyncio.run(
            detector.detect("给华为设计一套3D幕墙方案", [], db=None)
        )
        assert result.intent == "sop_pipeline"
        assert result.confidence >= 0.8

    def test_pipeline_intent_medium_confidence(self, detector):
        import asyncio
        result = asyncio.run(
            detector.detect("LED方案设计", [], db=None)
        )
        assert result.intent == "sop_pipeline"

    def test_not_pipeline_intent(self, detector):
        import asyncio
        result = asyncio.run(
            detector.detect("帮我进行企业解析", [], db=None)
        )
        assert result.intent != "sop_pipeline"


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
