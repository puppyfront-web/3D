"""Tests for the (ReAct-first) intent detector.

The legacy SOP-pipeline executor (``pipeline_state``, ``execution_plan``,
``plan_executor``) was removed when the canvas + ReAct architecture took over
the orchestration that those modules used to drive. The ``TestBuildStepInput``
and ``TestPipelineState`` classes that exercised them were removed with it;
what remains here covers ``IntentDetector`` itself, which is still in use as
the fast-path / LLM-fallback router in front of the canvas orchestrator.
"""

import pytest
from app.services.intent_service import IntentDetector


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
